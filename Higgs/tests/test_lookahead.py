"""Look-ahead and execution-rule tests for the backtester."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from engine.backtester import SLIPPAGE, SPREAD, run_backtest


def _frame(n: int = 10, signal_at: int | None = None) -> pd.DataFrame:
    index = pd.date_range("2024-01-02 10:00", periods=n, freq="h")
    close = np.full(n, 2000.0)
    # Bar 3 dips enough to hit SL; bar 3 also spikes high enough for TP when both set
    high = close + 5.0
    low = close - 5.0
    open_ = close.copy()
    signal = np.zeros(n)
    sl_atr = np.full(n, 1.0)
    tp_atr = np.full(n, 2.0)
    atr = np.full(n, 10.0)
    if signal_at is not None:
        signal[signal_at] = 1.0
    return pd.DataFrame(
        {
            "Datetime": index,
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "ATR": atr,
            "signal": signal,
            "sl_atr": sl_atr,
            "tp_atr": tp_atr,
        }
    )


class LookaheadTests(unittest.TestCase):
    def test_entry_uses_next_bar_open(self):
        df = _frame(n=6, signal_at=1)
        df.loc[2, "Open"] = 2010.0
        result = run_backtest(df, commission_per_lot=0.0, spread=0.0, slippage=0.0)
        self.assertGreaterEqual(len(result.trades), 1)
        trade = result.trades.iloc[0]
        self.assertEqual(pd.Timestamp(trade["entry_time"]), df.loc[2, "Datetime"])
        self.assertAlmostEqual(float(trade["entry"]), 2010.0)

    def test_same_bar_signal_does_not_enter_on_signal_bar(self):
        df = _frame(n=5, signal_at=2)
        df.loc[2, "Open"] = 1990.0
        df.loc[3, "Open"] = 2020.0
        result = run_backtest(df, commission_per_lot=0.0, spread=0.0, slippage=0.0)
        self.assertGreaterEqual(len(result.trades), 1)
        self.assertEqual(pd.Timestamp(result.trades.iloc[0]["entry_time"]), df.loc[3, "Datetime"])
        self.assertAlmostEqual(float(result.trades.iloc[0]["entry"]), 2020.0)

    def test_sl_preferred_when_both_hit(self):
        df = _frame(n=6, signal_at=1)
        # Wide range on exit bar so both SL and TP are inside the bar
        df.loc[3, "Low"] = 1000.0
        df.loc[3, "High"] = 3000.0
        result = run_backtest(df, commission_per_lot=0.0, spread=0.0, slippage=0.0, risk_pct=0.01)
        self.assertGreaterEqual(len(result.trades), 1)
        self.assertEqual(result.trades.iloc[0]["reason"], "SL")

    def test_long_entry_applies_slippage_and_half_spread(self):
        df = _frame(n=5, signal_at=1)
        df.loc[2, "Open"] = 2000.0
        result = run_backtest(df, commission_per_lot=0.0)
        entry = float(result.trades.iloc[0]["entry"])
        expected = 2000.0 * (1.0 + SLIPPAGE) + SPREAD / 2.0
        self.assertAlmostEqual(entry, expected)


if __name__ == "__main__":
    unittest.main()
