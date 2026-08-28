"""Persistence tests for BacktestRun + ImmediateBackend enqueue."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from django.test import TestCase

from apps.backtests.models import BacktestRun, MetricSet, Trade
from apps.backtests.tasks import enqueue_run
from apps.marketdata.models import Dataset


def _write_mini_h1(path: Path, n: int = 400) -> None:
    index = pd.date_range("2022-01-03", periods=n, freq="h")
    close = 1800 + np.linspace(0, 40, n) + np.sin(np.linspace(0, 8, n))
    # Force a few breakouts
    high = close + 2.0
    low = close - 2.0
    high[200] = high[199] + 10
    close[200] = high[200] - 0.5
    df = pd.DataFrame(
        {
            "Datetime": index,
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.zeros(n),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


@pytest.mark.django_db
class BacktestPersistTests(TestCase):
    def test_enqueue_run_persists_trades_and_metrics(self):
        cache = Path(self._test_cache_dir()) / "h1.parquet"
        _write_mini_h1(cache)
        ds = Dataset.objects.create(
            symbol="XAUUSD",
            timeframe="1H",
            source_name="mini",
            raw_path=str(cache),
            cache_path=str(cache),
            rows_m1=0,
            rows_h1=400,
            volume_usable=False,
            validation={},
        )
        run = BacktestRun.objects.create(
            dataset=ds,
            strategy_name="breakout_atr",
            params={"volume_usable": False, "lookback": 12},
            status=BacktestRun.Status.QUEUED,
        )
        enqueue_run.enqueue(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, BacktestRun.Status.DONE)
        self.assertGreater(Trade.objects.filter(run=run).count(), 0)
        metric = MetricSet.objects.get(run=run, split="full")
        self.assertGreater(metric.trades or 0, 0)
        self.assertIsNotNone(metric.final_equity)

    def _test_cache_dir(self) -> Path:
        root = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_runs"
        root.mkdir(parents=True, exist_ok=True)
        return root
