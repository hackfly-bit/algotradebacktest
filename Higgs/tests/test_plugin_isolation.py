"""Tests for strategy registry and plugin isolation."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import engine.strategies  # noqa: F401 — discover plugins
from engine.indicators import add_indicators
from engine.registry import (
    DEFAULT_PARAMS,
    STRATEGY_SPECS,
    get_strategy,
    list_strategies,
    resolve_strategy_queue,
)

ENGINE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [
    "breakout_atr",
    "ema_rsi_volume",
    "momentum_squeeze_by_kimi",
    "trend_breakout_by_gemini",
    "trend_pullback_by_claude",
]
FORBIDDEN_IMPORT_ROOTS = {"django", "engine.backtester", "engine.metrics"}


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


class StrategyPluginTests(unittest.TestCase):
    def test_list_strategies_has_five(self):
        self.assertEqual(list_strategies(), EXPECTED)
        for name in EXPECTED:
            self.assertTrue(STRATEGY_SPECS[name])

    def test_resolve_star_and_missing(self):
        self.assertEqual(resolve_strategy_queue("*"), EXPECTED)
        self.assertEqual(resolve_strategy_queue("all"), EXPECTED)
        self.assertEqual(resolve_strategy_queue("ema_rsi_volume"), ["ema_rsi_volume"])
        with self.assertRaises(KeyError):
            resolve_strategy_queue("no_such_strategy")

    def test_plugins_emit_signal_contract(self):
        df = add_indicators(_ohlcv())
        for name in EXPECTED:
            out = get_strategy(name)(df, {"volume_usable": False})
            self.assertIn("signal", out.columns, name)
            self.assertIn("sl_atr", out.columns, name)
            self.assertIn("tp_atr", out.columns, name)
            unique = set(out["signal"].dropna().unique().tolist())
            self.assertTrue(unique.issubset({-1, 0, 1}), f"{name}: {unique}")
            self.assertGreaterEqual(float(out["sl_atr"].iloc[-1]), 0.0)
            self.assertGreaterEqual(float(out["tp_atr"].iloc[-1]), 0.0)

    def test_ema_rsi_volume_skips_volume_when_unusable(self):
        df = add_indicators(_ohlcv())
        with_vol = get_strategy("ema_rsi_volume")(df, {"volume_usable": True, "use_volume_filter": True})
        without = get_strategy("ema_rsi_volume")(df, {"volume_usable": False, "use_volume_filter": True})
        self.assertTrue(with_vol.attrs["volume_filter_applied"])
        self.assertFalse(without.attrs["volume_filter_applied"])
        self.assertGreaterEqual(int((without["signal"] == 1).sum()), int((with_vol["signal"] == 1).sum()))

    def test_breakout_uses_shifted_rolling_high(self):
        df = add_indicators(_ohlcv(n=80))
        lookback = int(DEFAULT_PARAMS["lookback"])
        out = get_strategy("breakout_atr")(df)
        rolling_high = df["High"].rolling(lookback, min_periods=lookback).max().shift(1)
        expected = (df["Close"] > rolling_high).astype(int)
        pd.testing.assert_series_equal(out["signal"].astype(int), expected, check_names=False)

    def test_plugin_modules_isolated_from_backtester_metrics_django(self):
        strategies_dir = ENGINE_ROOT / "engine" / "strategies"
        for path in sorted(strategies_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    root = name.split(".", 1)[0]
                    self.assertNotIn(root if root != "engine" else name, FORBIDDEN_IMPORT_ROOTS, path.name)
                    if name.startswith("engine."):
                        self.assertNotIn(name, FORBIDDEN_IMPORT_ROOTS, path.name)


if __name__ == "__main__":
    unittest.main()
