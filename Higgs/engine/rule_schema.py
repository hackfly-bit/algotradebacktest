"""Validate strategy rule JSON schema v1. Do not import Django."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
ALLOWED_OPS = {
    "gt",
    "lt",
    "gte",
    "lte",
    "eq",
    "crosses_above",
    "crosses_below",
    "rising",
    "falling",
    "touch_in_last_n",
    "squeeze",
    "volume_filter",
}
ALLOWED_COMBINE = {"and", "or"}
ALLOWED_PARAM_TYPES = {"int", "float", "bool"}


class RuleSchemaError(ValueError):
    pass


def _require(obj: dict, key: str, ctx: str) -> Any:
    if key not in obj:
        raise RuleSchemaError(f"{ctx}: missing '{key}'")
    return obj[key]


def validate_operand(node: Any, ctx: str) -> None:
    if isinstance(node, (int, float, bool)):
        return
    if isinstance(node, str):
        if node.startswith("$"):
            return
        raise RuleSchemaError(f"{ctx}: invalid string operand '{node}'")
    if not isinstance(node, dict):
        raise RuleSchemaError(f"{ctx}: operand must be object, literal, or $param")
    fn = node.get("fn")
    if fn == "literal":
        _require(node, "value", ctx)
        return
    if fn == "ema":
        _require(node, "period", ctx)
        return
    if fn in {"rolling_max", "rolling_min"}:
        _require(node, "col", ctx)
        _require(node, "period", ctx)
        if "shift" not in node:
            raise RuleSchemaError(f"{ctx}: rolling fn requires shift >= 1 (no look-ahead)")
        shift = int(node["shift"])
        if shift < 1:
            raise RuleSchemaError(f"{ctx}: rolling fn requires shift >= 1 (no look-ahead)")
        return
    if fn == "shift":
        _require(node, "ref", ctx)
        _require(node, "bars", ctx)
        validate_operand(node["ref"], f"{ctx}.ref")
        return
    if fn == "subtract":
        _require(node, "left", ctx)
        _require(node, "right", ctx)
        validate_operand(node["left"], f"{ctx}.left")
        validate_operand(node["right"], f"{ctx}.right")
        return
    if "col" in node:
        return
    if "param" in node:
        return
    raise RuleSchemaError(f"{ctx}: unknown operand fn '{fn}'")


def validate_condition(node: dict, ctx: str, depth: int = 0) -> None:
    if depth > 2:
        raise RuleSchemaError(f"{ctx}: nested rule depth exceeds 2")
    op = _require(node, "op", ctx)
    if op in ALLOWED_COMBINE:
        children = _require(node, "conditions", ctx)
        if not isinstance(children, list) or not children:
            raise RuleSchemaError(f"{ctx}: combine node needs non-empty conditions")
        for i, child in enumerate(children):
            if "op" in child and child["op"] in ALLOWED_COMBINE:
                validate_condition(child, f"{ctx}.conditions[{i}]", depth + 1)
            else:
                validate_leaf_condition(child, f"{ctx}.conditions[{i}]")
        return
    validate_leaf_condition(node, ctx)


def validate_leaf_condition(node: dict, ctx: str) -> None:
    op = _require(node, "op", ctx)
    if op not in ALLOWED_OPS:
        raise RuleSchemaError(f"{ctx}: unknown op '{op}'")
    if op in {"rising", "falling"}:
        _require(node, "ref", ctx)
        validate_operand(node["ref"], f"{ctx}.ref")
        return
    if op == "touch_in_last_n":
        _require(node, "col", ctx)
        _require(node, "ref", ctx)
        _require(node, "bars", ctx)
        validate_operand(node["ref"], f"{ctx}.ref")
        return
    if op == "squeeze":
        _require(node, "lookback", ctx)
        return
    if op == "volume_filter":
        return
    if op in {"crosses_above", "crosses_below"}:
        _require(node, "left", ctx)
        _require(node, "right", ctx)
        validate_operand(node["left"], f"{ctx}.left")
        validate_operand(node["right"], f"{ctx}.right")
        return
    _require(node, "left", ctx)
    _require(node, "right", ctx)
    validate_operand(node["left"], f"{ctx}.left")
    validate_operand(node["right"], f"{ctx}.right")


def validate_rule_side(node: dict | None, ctx: str) -> None:
    if node is None:
        return
    if not isinstance(node, dict):
        raise RuleSchemaError(f"{ctx}: must be object or null")
    combine = node.get("combine", "and")
    if combine not in ALLOWED_COMBINE:
        raise RuleSchemaError(f"{ctx}: invalid combine '{combine}'")
    conditions = _require(node, "conditions", ctx)
    if not isinstance(conditions, list) or not conditions:
        raise RuleSchemaError(f"{ctx}: conditions required")
    for i, cond in enumerate(conditions):
        validate_condition(cond, f"{ctx}.conditions[{i}]")


def validate_definition(defn: dict) -> dict:
    if not isinstance(defn, dict):
        raise RuleSchemaError("definition must be object")
    version = int(defn.get("schema_version", 0))
    if version != SCHEMA_VERSION:
        raise RuleSchemaError(f"unsupported schema_version {version}")
    params = defn.get("params") or {}
    if not isinstance(params, dict):
        raise RuleSchemaError("params must be object")
    for key, spec in params.items():
        if not isinstance(spec, dict):
            raise RuleSchemaError(f"params.{key} must be object")
        ptype = spec.get("type", "float")
        if ptype not in ALLOWED_PARAM_TYPES:
            raise RuleSchemaError(f"params.{key}: invalid type '{ptype}'")
        if "default" not in spec:
            raise RuleSchemaError(f"params.{key}: missing default")
    validate_rule_side(defn.get("long"), "long")
    short = defn.get("short")
    if short is not None:
        validate_rule_side(short, "short")
    exit_ = _require(defn, "exit", "definition")
    if "sl_atr" not in exit_ or "tp_atr" not in exit_:
        raise RuleSchemaError("exit requires sl_atr and tp_atr")
    return defn
