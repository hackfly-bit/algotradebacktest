"""Preset condition blocks and UI helpers for the strategy builder."""

from __future__ import annotations

PRESET_BLOCKS: list[dict] = [
    {
        "id": "regime_ema200",
        "label": "Regime EMA200",
        "description": "Close > EMA(200)",
        "side": "long",
        "condition": {
            "op": "gt",
            "left": {"col": "Close"},
            "right": {"fn": "ema", "period": 200},
        },
    },
    {
        "id": "ema_cross",
        "label": "EMA cross",
        "description": "EMA fast > EMA slow",
        "side": "long",
        "condition": {
            "op": "gt",
            "left": {"fn": "ema", "period": "$ema_fast"},
            "right": {"fn": "ema", "period": "$ema_slow"},
        },
        "params": {
            "ema_fast": {"type": "int", "default": 20, "min": 5, "max": 100, "optimizable": True},
            "ema_slow": {"type": "int", "default": 50, "min": 10, "max": 200, "optimizable": True},
        },
    },
    {
        "id": "rsi_filter",
        "label": "RSI filter",
        "description": "RSI > threshold",
        "side": "long",
        "condition": {
            "op": "gt",
            "left": {"col": "rsi_14"},
            "right": "$rsi_threshold",
        },
        "params": {
            "rsi_threshold": {"type": "float", "default": 50, "min": 30, "max": 70, "optimizable": False},
        },
    },
    {
        "id": "donchian_breakout",
        "label": "Donchian breakout",
        "description": "Close > rolling high (shift 1)",
        "side": "long",
        "condition": {
            "op": "gt",
            "left": {"col": "Close"},
            "right": {"fn": "rolling_max", "col": "High", "period": "$lookback", "shift": 1},
        },
        "params": {
            "lookback": {"type": "int", "default": 24, "min": 5, "max": 100, "optimizable": True},
        },
    },
    {
        "id": "adx_filter",
        "label": "ADX filter",
        "description": "ADX > threshold",
        "side": "long",
        "condition": {
            "op": "gt",
            "left": {"col": "adx_14"},
            "right": "$adx_th",
        },
        "params": {
            "adx_th": {"type": "float", "default": 20, "min": 10, "max": 40, "optimizable": False},
        },
    },
    {
        "id": "pullback",
        "label": "Pullback touch",
        "description": "Low touched EMA fast in last N bars",
        "side": "long",
        "condition": {
            "op": "touch_in_last_n",
            "col": "Low",
            "ref": {"fn": "ema", "period": "$ema_fast"},
            "bars": "$pull_bars",
        },
        "params": {
            "ema_fast": {"type": "int", "default": 20, "min": 5, "max": 100, "optimizable": True},
            "pull_bars": {"type": "int", "default": 3, "min": 1, "max": 10, "optimizable": False},
        },
    },
    {
        "id": "squeeze",
        "label": "Squeeze",
        "description": "Donchian width / ATR below median",
        "side": "long",
        "condition": {"op": "squeeze", "lookback": "$lookback", "median_bars": 100},
        "params": {
            "lookback": {"type": "int", "default": 20, "min": 5, "max": 100, "optimizable": True},
        },
    },
    {
        "id": "volume_filter",
        "label": "Volume filter",
        "description": "Volume > Volume MA when usable",
        "side": "long",
        "condition": {"op": "volume_filter"},
        "params": {
            "volume_ma": {"type": "int", "default": 20, "min": 5, "max": 100, "optimizable": False},
            "use_volume_filter": {"type": "bool", "default": True, "optimizable": False},
        },
    },
    {
        "id": "adx_rising",
        "label": "ADX rising",
        "description": "ADX rising over N bars",
        "side": "long",
        "condition": {"op": "rising", "ref": {"col": "adx_14"}, "bars": "$adx_rise"},
        "params": {
            "adx_rise": {"type": "int", "default": 3, "min": 1, "max": 10, "optimizable": False},
        },
    },
]


def empty_definition(label: str = "Custom strategy") -> dict:
    return {
        "schema_version": 1,
        "label": label,
        "allow_short": False,
        "params": {
            "lookback": {"type": "int", "default": 24, "min": 5, "max": 100, "optimizable": True},
            "atr_sl": {"type": "float", "default": 2.0, "optimizable": False},
            "atr_tp": {"type": "float", "default": 4.0, "optimizable": False},
        },
        "long": {"combine": "and", "conditions": []},
        "short": None,
        "exit": {"sl_atr": "$atr_sl", "tp_atr": "$atr_tp"},
    }


def presets_for_json() -> list[dict]:
    """JSON-serializable preset list for Alpine."""
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "description": p["description"],
            "condition": p["condition"],
            "params": p.get("params") or {},
        }
        for p in PRESET_BLOCKS
    ]
