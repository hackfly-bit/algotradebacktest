"""Tests for JSON rule interpreter and parity with Python plugins."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import engine.strategies  # noqa: F401
from engine.custom_registry import register_custom_strategy, unregister_custom_strategy
from engine.indicators import add_indicators
from engine.registry import get_strategy
from engine.rule_interpreter import interpret_rules
from engine.rule_schema import RuleSchemaError, validate_definition

TEMPLATES = Path(__file__).resolve().parents[1] / "engine" / "strategies" / "builtin_templates.json"


def _ohlcv(n: int = 400) -> pd.DataFrame:
    index = pd.date_range("2020-01-02", periods=n, freq="h")
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.8, size=n).cumsum()
    closes = 1800.0 + noise
    highs = closes + rng.uniform(0.2, 1.5, size=n)
    lows = closes - rng.uniform(0.2, 1.5, size=n)
    opens = closes + rng.normal(0, 0.3, size=n)
    return pd.DataFrame(
        {
            "Datetime": index,
            "Open": opens,
            "High": np.maximum(highs, np.maximum(opens, closes)),
            "Low": np.minimum(lows, np.minimum(opens, closes)),
            "Close": closes,
            "Volume": rng.integers(0, 3, size=n).astype(float),
        }
    )


@pytest.fixture
def templates() -> dict:
    return json.loads(TEMPLATES.read_text(encoding="utf-8"))


def test_validate_rejects_rolling_without_shift():
    bad = {
        "schema_version": 1,
        "params": {},
        "long": {
            "combine": "and",
            "conditions": [
                {
                    "op": "gt",
                    "left": {"col": "Close"},
                    "right": {"fn": "rolling_max", "col": "High", "period": 20, "shift": 0},
                }
            ],
        },
        "short": None,
        "exit": {"sl_atr": 2, "tp_atr": 4},
    }
    with pytest.raises(RuleSchemaError):
        validate_definition(bad)


def test_breakout_json_parity(templates):
    df = add_indicators(_ohlcv(80))
    py = get_strategy("breakout_atr")(df, {"volume_usable": False, "lookback": 24})
    js = interpret_rules(templates["breakout_atr"], df, {"volume_usable": False, "lookback": 24})
    pd.testing.assert_series_equal(py["signal"].astype(int), js["signal"].astype(int), check_names=False)


def test_ema_rsi_json_parity(templates):
    df = add_indicators(_ohlcv(400))
    params = {"volume_usable": False, "use_volume_filter": True}
    py = get_strategy("ema_rsi_volume")(df, params)
    js = interpret_rules(templates["ema_rsi_volume"], df, params)
    pd.testing.assert_series_equal(py["signal"].astype(int), js["signal"].astype(int), check_names=False)


def test_gemini_json_parity(templates):
    df = add_indicators(_ohlcv(600))
    params = {"volume_usable": False, "allow_short": True}
    py = get_strategy("trend_breakout_by_gemini")(df, params)
    js = interpret_rules(templates["trend_breakout_by_gemini"], df, params)
    pd.testing.assert_series_equal(py["signal"].astype(int), js["signal"].astype(int), check_names=False)


def test_kimi_json_parity(templates):
    df = add_indicators(_ohlcv(600))
    params = {"volume_usable": False}
    py = get_strategy("momentum_squeeze_by_kimi")(df, params)
    js = interpret_rules(templates["momentum_squeeze_by_kimi"], df, params)
    pd.testing.assert_series_equal(py["signal"].astype(int), js["signal"].astype(int), check_names=False)


def test_custom_registry_run(templates):
    name = "custom_test_breakout"
    register_custom_strategy(name, templates["breakout_atr"], "test")
    try:
        df = add_indicators(_ohlcv(100))
        out = get_strategy(name)(df, {"volume_usable": False})
        assert set(out["signal"].unique()).issubset({-1, 0, 1})
    finally:
        unregister_custom_strategy(name)


def test_all_builtin_templates_validate(templates):
    for name, defn in templates.items():
        validate_definition(defn)
