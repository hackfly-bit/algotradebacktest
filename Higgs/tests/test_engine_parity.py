"""Notebook parity targets for full-sample backtests (needs local M1 CSV)."""

from __future__ import annotations

import unittest
from pathlib import Path

import engine.strategies  # noqa: F401
from engine.backtester import apply_strategy, run_backtest
from engine.data import build_h1_cache
from engine.indicators import add_indicators

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "XAUUSD_2009_2026_M1.csv"
CACHE_PATH = Path(__file__).resolve().parents[1] / "media" / "cache" / "parity_h1.parquet"

# CONVERSION_PLAN §11 — relative tolerance ~1e-3 on final_equity / sharpe
TARGETS = {
    "breakout_atr": {"final_equity": 27001.67, "total_return": 1.7002, "sharpe": 0.375, "trades": 1961},
    "ema_rsi_volume": {"final_equity": 89513.90, "total_return": 7.9514, "sharpe": 0.567, "trades": 3016},
    "momentum_squeeze_by_kimi": {"final_equity": 10617.68, "total_return": 0.0618, "sharpe": 0.073, "trades": 1109},
    "trend_breakout_by_gemini": {"final_equity": 22986.09, "total_return": 1.2986, "sharpe": 0.314, "trades": 2166},
    "trend_pullback_by_claude": {"final_equity": 15358.39, "total_return": 0.5358, "sharpe": 0.212, "trades": 1317},
}


@unittest.skipUnless(CSV_PATH.is_file(), f"Missing {CSV_PATH.name} (see Fase 2b bootstrap)")
class EngineParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CACHE_PATH.is_file():
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            build_h1_cache(CSV_PATH, CACHE_PATH)
        import pandas as pd

        cls.df_ind = add_indicators(pd.read_parquet(CACHE_PATH))
        # Match notebook: volume dead on this dataset
        cls.params = {"volume_usable": False}

    def _assert_strategy(self, name: str):
        target = TARGETS[name]
        signals = apply_strategy(self.df_ind, name, self.params)
        result = run_backtest(signals, name=f"{name}_full", params=self.params)
        m = result.metrics
        self.assertAlmostEqual(m["final_equity"], target["final_equity"], delta=target["final_equity"] * 1e-3)
        self.assertAlmostEqual(m["sharpe"], target["sharpe"], delta=max(abs(target["sharpe"]) * 1e-3, 1e-3))
        self.assertAlmostEqual(m["total_return"], target["total_return"], delta=max(abs(target["total_return"]) * 1e-3, 1e-3))
        self.assertEqual(int(m["trades"]), target["trades"])

    def test_breakout_atr(self):
        self._assert_strategy("breakout_atr")

    def test_ema_rsi_volume(self):
        self._assert_strategy("ema_rsi_volume")

    def test_momentum_squeeze_by_kimi(self):
        self._assert_strategy("momentum_squeeze_by_kimi")

    def test_trend_breakout_by_gemini(self):
        self._assert_strategy("trend_breakout_by_gemini")

    def test_trend_pullback_by_claude(self):
        self._assert_strategy("trend_pullback_by_claude")


if __name__ == "__main__":
    unittest.main()
