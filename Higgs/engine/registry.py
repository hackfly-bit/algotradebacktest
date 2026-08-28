"""Strategy registry. Do not import Django."""

from __future__ import annotations

from typing import Callable

import pandas as pd

STRATEGY_REGISTRY: dict[str, Callable] = {}
STRATEGY_SPECS: dict[str, str] = {}

DEFAULT_PARAMS: dict = {
    "ema_fast": 20,
    "ema_slow": 50,
    "ema_trend": 200,
    "lookback": 24,
    "rsi_period": 14,
    "rsi_threshold": 50,
    "rsi_th": 50.0,
    "rsi_long": 52.0,
    "rsi_short": 48.0,
    "adx_th": 20.0,
    "adx_min": 20.0,
    "adx_rise": 3,
    "volume_ma": 20,
    "atr_period": 14,
    "atr_sl": 2.0,
    "atr_tp": 4.0,
    "atr_sl_gemini": 2.0,
    "atr_tp_gemini": 4.0,
    "atr_sl_claude": 2.0,
    "atr_tp_claude": 4.0,
    "atr_sl_kimi": 2.0,
    "atr_tp_kimi": 4.0,
    "allow_short": True,
    "use_volume_filter": True,
    "pull_bars": 3,
    "slope_bars": 5,
    "volume_usable": True,
}


def register_strategy(fn: Callable) -> Callable:
    STRATEGY_REGISTRY[fn.__name__] = fn
    STRATEGY_SPECS[fn.__name__] = (fn.__doc__ or "").strip()
    return fn


def list_strategies() -> list[str]:
    from engine.custom_registry import list_custom_strategies

    return sorted(set(STRATEGY_REGISTRY) | set(list_custom_strategies()))


def get_strategy(name: str) -> Callable:
    if name in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[name]
    from engine.custom_registry import CUSTOM_STRATEGY_REGISTRY

    if name in CUSTOM_STRATEGY_REGISTRY:
        return CUSTOM_STRATEGY_REGISTRY[name]
    available = ", ".join(list_strategies()) or "(kosong)"
    raise KeyError(f"Strategy '{name}' tidak ditemukan. Tersedia: {available}")


def get_strategy_spec(name: str) -> str:
    if name in STRATEGY_SPECS:
        return STRATEGY_SPECS[name]
    from engine.custom_registry import CUSTOM_STRATEGY_SPECS

    return CUSTOM_STRATEGY_SPECS.get(name, "")


def resolve_strategy_queue(spec) -> list[str]:
    if isinstance(spec, str) and spec in {"*", "all"}:
        names = list_strategies()
        if not names:
            raise KeyError("Tidak ada strategy terdaftar.")
        return names
    names = [spec] if isinstance(spec, str) else list(spec)
    available = set(STRATEGY_REGISTRY) | set(list_strategies())
    missing = [n for n in names if n not in available]
    if missing:
        available_list = ", ".join(list_strategies()) or "(kosong)"
        raise KeyError(f"Strategy tidak ditemukan: {missing}. Tersedia: {available_list}")
    return names


def merge_params(params: dict | None = None) -> dict:
    if params is None:
        return dict(DEFAULT_PARAMS)
    return {**DEFAULT_PARAMS, **params}


def ensure_ema(df: pd.DataFrame, period: int) -> pd.DataFrame:
    col = f"ema_{period}"
    if col not in df.columns:
        df = df.copy()
        df[col] = df["Close"].ewm(span=period, adjust=False).mean()
    return df
