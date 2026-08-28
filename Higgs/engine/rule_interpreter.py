"""Interpret JSON strategy rules into signal columns. Do not import Django."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engine.registry import ensure_ema, merge_params
from engine.rule_schema import validate_definition


def _resolve_param(value: Any, params: dict) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        if key not in params:
            raise ValueError(f"Missing param: {key}")
        return params[key]
    return value


def _resolve_number(value: Any, params: dict) -> float:
    resolved = _resolve_param(value, params)
    return float(resolved)


def _resolve_int(value: Any, params: dict) -> int:
    return int(_resolve_number(value, params))


def _eval_operand(node: Any, df: pd.DataFrame, params: dict) -> pd.Series:
    if isinstance(node, bool):
        return pd.Series(bool(node), index=df.index)
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return pd.Series(float(node), index=df.index)
    if isinstance(node, str):
        if node.startswith("$"):
            val = _resolve_param(node, params)
            return pd.Series(val, index=df.index)
        if node in df.columns:
            return df[node]
        raise ValueError(f"Unknown column or param: {node}")
    if not isinstance(node, dict):
        raise ValueError(f"Invalid operand: {node}")

    fn = node.get("fn")
    if fn == "literal":
        return pd.Series(_resolve_param(node["value"], params), index=df.index)
    if fn == "ema":
        period = _resolve_int(node["period"], params)
        work = ensure_ema(df, period)
        return work[f"ema_{period}"]
    if fn == "rolling_max":
        col = node["col"]
        period = _resolve_int(node["period"], params)
        shift = int(node.get("shift", 1))
        return df[col].rolling(period, min_periods=period).max().shift(shift)
    if fn == "rolling_min":
        col = node["col"]
        period = _resolve_int(node["period"], params)
        shift = int(node.get("shift", 1))
        return df[col].rolling(period, min_periods=period).min().shift(shift)
    if fn == "shift":
        ref = _eval_operand(node["ref"], df, params)
        bars = _resolve_int(node["bars"], params)
        return ref.shift(bars)
    if fn == "subtract":
        left = _eval_operand(node["left"], df, params)
        right = _eval_operand(node["right"], df, params)
        return left - right

    if "col" in node:
        col = node["col"]
        if col not in df.columns:
            raise ValueError(f"Column not found: {col}")
        return df[col]

    if "param" in node:
        val = params.get(node["param"])
        return pd.Series(val, index=df.index)

    raise ValueError(f"Unknown operand fn: {fn}")


def _eval_compare(op: str, left: pd.Series, right: pd.Series) -> pd.Series:
    if op == "gt":
        return left > right
    if op == "lt":
        return left < right
    if op == "gte":
        return left >= right
    if op == "lte":
        return left <= right
    if op == "eq":
        return left == right
    raise ValueError(f"Unknown compare op: {op}")


def _eval_leaf(cond: dict, df: pd.DataFrame, params: dict) -> pd.Series:
    op = cond["op"]
    if op == "volume_filter":
        use_vol = bool(params.get("use_volume_filter", True)) and bool(params.get("volume_usable", True))
        if not use_vol:
            return pd.Series(True, index=df.index)
        vol_ma = int(params.get("volume_ma", 20))
        col = f"volume_ma_{vol_ma}"
        if col not in df.columns:
            work = df.copy()
            work[col] = work["Volume"].rolling(vol_ma, min_periods=vol_ma).mean()
            return work["Volume"] > work[col]
        return df["Volume"] > df[col]
    if op == "rising":
        ref = _eval_operand(cond["ref"], df, params)
        bars = _resolve_int(cond.get("bars", 1), params)
        return ref > ref.shift(bars)
    if op == "falling":
        ref = _eval_operand(cond["ref"], df, params)
        bars = _resolve_int(cond.get("bars", 1), params)
        return ref < ref.shift(bars)
    if op == "touch_in_last_n":
        col = cond["col"]
        ref = _eval_operand(cond["ref"], df, params)
        bars = _resolve_int(cond["bars"], params)
        touched = (df[col] <= ref).rolling(bars, min_periods=1).max().astype(bool)
        return touched
    if op == "squeeze":
        lookback = _resolve_int(cond["lookback"], params)
        median_bars = _resolve_int(cond.get("median_bars", 100), params)
        upper = df["High"].rolling(lookback, min_periods=lookback).max().shift(1)
        lower = df["Low"].rolling(lookback, min_periods=lookback).min().shift(1)
        width = (upper - lower) / df["atr_14"]
        return width < width.rolling(median_bars).median()
    if op == "crosses_above":
        left = _eval_operand(cond["left"], df, params)
        right = _eval_operand(cond["right"], df, params)
        return (left > right) & (left.shift(1) <= right.shift(1))
    if op == "crosses_below":
        left = _eval_operand(cond["left"], df, params)
        right = _eval_operand(cond["right"], df, params)
        return (left < right) & (left.shift(1) >= right.shift(1))
    left = _eval_operand(cond["left"], df, params)
    right = _eval_operand(cond["right"], df, params)
    return _eval_compare(op, left, right)


def _eval_condition(cond: dict, df: pd.DataFrame, params: dict) -> pd.Series:
    op = cond.get("op")
    if op in {"and", "or"}:
        parts = [_eval_condition(c, df, params) for c in cond["conditions"]]
        if not parts:
            return pd.Series(False, index=df.index)
        out = parts[0]
        for part in parts[1:]:
            out = out & part if op == "and" else out | part
        return out
    return _eval_leaf(cond, df, params)


def _eval_side(side: dict | None, df: pd.DataFrame, params: dict) -> pd.Series:
    if side is None:
        return pd.Series(False, index=df.index)
    combine = side.get("combine", "and")
    parts = [_eval_condition(c, df, params) for c in side["conditions"]]
    if not parts:
        return pd.Series(False, index=df.index)
    out = parts[0]
    for part in parts[1:]:
        out = out & part if combine == "and" else out | part
    return out.fillna(False)


def _default_params(defn: dict) -> dict:
    out = {}
    for key, spec in (defn.get("params") or {}).items():
        out[key] = spec["default"]
    return out


def interpret_rules(defn: dict, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    validate_definition(defn)
    merged = {**_default_params(defn), **merge_params(params or {})}
    for key, spec in (defn.get("params") or {}).items():
        if key in merged:
            if spec.get("type") == "int":
                merged[key] = int(merged[key])
            elif spec.get("type") == "bool":
                merged[key] = bool(merged[key])
            else:
                merged[key] = float(merged[key])
    out = df.copy()
    long_sig = _eval_side(defn.get("long"), out, merged)
    short_sig = _eval_side(defn.get("short"), out, merged) if defn.get("short") else pd.Series(False, index=out.index)
    signal = np.zeros(len(out), dtype=int)
    signal[long_sig.to_numpy()] = 1
    signal[short_sig.to_numpy()] = -1
    out["signal"] = signal
    exit_cfg = defn["exit"]
    out["sl_atr"] = float(_resolve_number(exit_cfg["sl_atr"], merged))
    out["tp_atr"] = float(_resolve_number(exit_cfg["tp_atr"], merged))
    return out


def make_custom_strategy(defn: dict):
    def _fn(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        result = interpret_rules(defn, df, params)
        return result

    return _fn
