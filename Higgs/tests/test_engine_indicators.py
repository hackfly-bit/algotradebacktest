"""Synthetic tests for engine.indicators. Do not load the parent 5.89M-bar CSV."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from engine.indicators import EMA_PERIODS, add_indicators, atr, rsi, true_range

ENGINE_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLS = (
    "ema_10",
    "ema_20",
    "ema_50",
    "ema_200",
    "rsi_14",
    "atr_14",
    "ATR",
    "adx_14",
    "volume_ma_20",
    "range",
)


def _ohlcv(n: int = 300, close_base: float = 2000.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=n, freq="h")
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.5, size=n).cumsum()
    closes = close_base + noise
    highs = closes + rng.uniform(0.1, 1.0, size=n)
    lows = closes - rng.uniform(0.1, 1.0, size=n)
    opens = closes + rng.normal(0, 0.2, size=n)
    return pd.DataFrame(
        {
            "Datetime": index,
            "Open": opens,
            "High": np.maximum(highs, np.maximum(opens, closes)),
            "Low": np.minimum(lows, np.minimum(opens, closes)),
            "Close": closes,
            "Volume": rng.integers(0, 5, size=n).astype(float),
        }
    )


class EngineIndicatorsTests(unittest.TestCase):
    def test_indicators_module_does_not_import_django(self):
        tree = ast.parse((ENGINE_ROOT / "engine/indicators.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                self.assertNotEqual(name.split(".", 1)[0], "django")

    def test_ema_periods_match_notebook(self):
        self.assertEqual(
            EMA_PERIODS,
            [10, 15, 18, 19, 20, 21, 22, 25, 30, 48, 49, 50, 51, 52, 200],
        )

    def test_add_indicators_required_columns_no_signal(self):
        out = add_indicators(_ohlcv())
        for col in REQUIRED_COLS:
            self.assertIn(col, out.columns, col)
        for p in EMA_PERIODS:
            self.assertIn(f"ema_{p}", out.columns)
        self.assertNotIn("signal", out.columns)
        pd.testing.assert_series_equal(out["ATR"], out["atr_14"], check_names=False)
        pd.testing.assert_series_equal(out["range"], out["High"] - out["Low"], check_names=False)

    def test_warmup_nans_for_long_period_indicators(self):
        out = add_indicators(_ohlcv(n=250))
        # EMA200 uses ewm(span=200, adjust=False) — filled from bar 0; RSI/ATR/ADX use min_periods
        self.assertTrue(out["rsi_14"].iloc[:13].isna().all())
        self.assertGreater(int(out["rsi_14"].notna().sum()), 0)
        self.assertTrue(out["atr_14"].iloc[:13].isna().all())
        self.assertFalse(out["atr_14"].iloc[13:].isna().any())
        self.assertTrue(out["adx_14"].iloc[:13].isna().all())
        self.assertTrue(out["volume_ma_20"].iloc[:19].isna().all())
        self.assertFalse(out["volume_ma_20"].iloc[19:].isna().any())
        # After full warmup window, EMA/ATR should be finite; RSI/ADX may NaN on flat DI
        tail = out.iloc[200:][["ema_200", "atr_14"]]
        self.assertFalse(tail.isna().any().any())
        self.assertGreater(int(out.iloc[200:]["rsi_14"].notna().sum()), 0)
        self.assertGreater(int(out.iloc[200:]["adx_14"].notna().sum()), 0)

    def test_rsi_bounded_when_defined(self):
        series = _ohlcv()["Close"]
        values = rsi(series, 14).dropna()
        self.assertTrue((values >= 0).all())
        self.assertTrue((values <= 100).all())

    def test_true_range_non_negative(self):
        tr = true_range(_ohlcv())
        self.assertTrue((tr.dropna() >= 0).all())

    def test_atr_matches_true_range_ewm(self):
        df = _ohlcv()
        expected = true_range(df).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        got = atr(df, 14)
        pd.testing.assert_series_equal(got, expected)

    def test_custom_ema_periods(self):
        out = add_indicators(_ohlcv(n=50), ema_periods=[5, 8])
        self.assertIn("ema_5", out.columns)
        self.assertIn("ema_8", out.columns)
        self.assertNotIn("ema_200", out.columns)


if __name__ == "__main__":
    unittest.main()
