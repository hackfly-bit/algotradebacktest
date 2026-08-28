"""Synthetic backtester + metrics smoke tests."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import engine.strategies  # noqa: F401
from engine.backtester import apply_strategy, run_backtest
from engine.indicators import add_indicators
from engine.metrics import calculate_metrics

ENGINE_ROOT = Path(__file__).resolve().parents[1]


def _trending(n: int = 300) -> pd.DataFrame:
    index = pd.date_range("2021-01-04", periods=n, freq="h")
    close = 1800 + np.linspace(0, 80, n) + np.sin(np.linspace(0, 12, n)) * 2
    return pd.DataFrame(
        {
            "Datetime": index,
            "Open": close,
            "High": close + 1.5,
            "Low": close - 1.5,
            "Close": close,
            "Volume": np.zeros(n),
        }
    )


class BacktesterMetricsTests(unittest.TestCase):
    def test_engine_modules_no_django(self):
        for rel in ("engine/backtester.py", "engine/metrics.py"):
            tree = ast.parse((ENGINE_ROOT / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    self.assertNotEqual(name.split(".", 1)[0], "django", rel)

    def test_apply_and_run_produces_trades_and_metrics(self):
        df = add_indicators(_trending(n=500))
        # Inject a clear breakout so the smoke test is not data-shape dependent
        lookback = 10
        spike_i = 250
        df.loc[spike_i, "Close"] = df.loc[spike_i - 1, "High"] + 5.0
        df.loc[spike_i, "Open"] = df.loc[spike_i, "Close"]
        df.loc[spike_i, "High"] = df.loc[spike_i, "Close"] + 1.0
        signals = apply_strategy(df, "breakout_atr", {"lookback": lookback})
        self.assertGreaterEqual(int((signals["signal"] == 1).sum()), 1)
        result = run_backtest(signals, name="breakout_atr_full")
        self.assertIn("final_equity", result.metrics)
        self.assertIn("sharpe", result.metrics)
        self.assertGreaterEqual(int(result.metrics["trades"]), 1)
        self.assertFalse(result.equity.isna().all())

    def test_calculate_metrics_keys(self):
        index = pd.date_range("2024-01-01", periods=40, freq="D")
        equity = pd.Series(np.linspace(10_000, 11_000, 40), index=index)
        trades = pd.DataFrame({"pnl": [100.0, -50.0, 80.0]})
        m = calculate_metrics(equity, trades, initial=10_000.0)
        for key in (
            "final_equity",
            "total_return",
            "cagr",
            "sharpe",
            "sortino",
            "calmar",
            "max_drawdown",
            "win_rate",
            "profit_factor",
            "trades",
            "years",
        ):
            self.assertIn(key, m)
        self.assertEqual(m["trades"], 3)


if __name__ == "__main__":
    unittest.main()
