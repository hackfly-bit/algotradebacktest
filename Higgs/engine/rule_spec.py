"""Generate human-readable logic spec from rule JSON. Do not import Django."""

from __future__ import annotations


def _fmt_operand(node) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, (int, float)):
        return str(node)
    if not isinstance(node, dict):
        return str(node)
    if "col" in node:
        return node["col"]
    if "param" in node:
        return f"${node['param']}"
    fn = node.get("fn")
    if fn == "ema":
        return f"EMA({node.get('period')})"
    if fn == "rolling_max":
        return f"rolling_max({node.get('col')}, {node.get('period')}, shift={node.get('shift', 1)})"
    if fn == "rolling_min":
        return f"rolling_min({node.get('col')}, {node.get('period')}, shift={node.get('shift', 1)})"
    if fn == "literal":
        return str(node.get("value"))
    if fn == "subtract":
        return f"{_fmt_operand(node.get('left'))} - {_fmt_operand(node.get('right'))}"
    return str(node)


def _fmt_condition(cond: dict, indent: int = 0) -> str:
    pad = "  " * indent
    op = cond.get("op")
    if op in {"and", "or"}:
        lines = [f"{pad}{op.upper()}:"]
        for child in cond.get("conditions", []):
            lines.append(_fmt_condition(child, indent + 1))
        return "\n".join(lines)
    if op == "volume_filter":
        return f"{pad}Volume > Volume_MA (when volume_usable)"
    if op == "touch_in_last_n":
        return f"{pad}touch_in_last_n({cond.get('col')}, {_fmt_operand(cond.get('ref'))}, bars={cond.get('bars')})"
    if op == "squeeze":
        return f"{pad}squeeze(lookback={cond.get('lookback')})"
    if op in {"rising", "falling"}:
        return f"{pad}{op}({_fmt_operand(cond.get('ref'))}, bars={cond.get('bars', 1)})"
    return f"{pad}{_fmt_operand(cond.get('left'))} {op} {_fmt_operand(cond.get('right'))}"


def _fmt_side(name: str, side: dict | None) -> str:
    if not side:
        return f"{name}: (none)"
    lines = [f"{name} ({side.get('combine', 'and').upper()}):"]
    for cond in side.get("conditions", []):
        lines.append(_fmt_condition(cond, 1))
    return "\n".join(lines)


def build_logic_spec(defn: dict) -> str:
    label = defn.get("label") or "Custom strategy"
    lines = [
        f"# {label}",
        "",
        "Execution: signal on closed bar; entry next bar open.",
        "",
        _fmt_side("LONG", defn.get("long")),
        "",
        _fmt_side("SHORT", defn.get("short")),
        "",
        f"Exit: SL = {defn.get('exit', {}).get('sl_atr')} x ATR, TP = {defn.get('exit', {}).get('tp_atr')} x ATR",
    ]
    params = defn.get("params") or {}
    if params:
        lines.append("")
        lines.append("Parameters:")
        for key, spec in params.items():
            lines.append(f"  - {key}: default={spec.get('default')} type={spec.get('type')}")
    return "\n".join(lines)
