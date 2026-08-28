"""Deep pipeline integration test (Fase 9-11)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.backtests.models import BacktestRun, DecisionGate, MonteCarloSummary, RobustnessRow
from apps.reports.models import ExportFile
from apps.backtests.tasks import enqueue_run
from apps.marketdata.models import Dataset


def _write_deep_dataset(path: Path, years: int = 6) -> None:
    n = years * 365
    index = pd.date_range("2016-01-01", periods=n, freq="D")
    close = 1800 + np.linspace(0, 80, n)
    high = close + 3
    low = close - 3
    for i in range(300, n, 400):
        high[i] = high[i - 1] + 12
        close[i] = high[i] - 0.5
    df = pd.DataFrame(
        {"Datetime": index, "Open": close, "High": high, "Low": low, "Close": close, "Volume": np.zeros(n)}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


@pytest.mark.django_db
def test_multi_deep_runs_full_pipeline():
    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_deep" / "h1.parquet"
    _write_deep_dataset(cache)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="deep-mini",
        raw_path=str(cache),
        cache_path=str(cache),
        rows_m1=0,
        rows_h1=365 * 6,
        volume_usable=False,
        validation={},
    )
    run = BacktestRun.objects.create(
        dataset=ds,
        strategy_name="breakout_atr",
        params={"volume_usable": False, "lookback": 12},
        in_sample_end=date(2019, 6, 1),
        oos_start=date(2019, 8, 1),
        multi_deep=True,
        status=BacktestRun.Status.QUEUED,
    )
    enqueue_run.enqueue(run.pk)
    run.refresh_from_db()
    assert run.status == BacktestRun.Status.DONE
    assert RobustnessRow.objects.filter(run=run).count() >= 13
    assert MonteCarloSummary.objects.filter(run=run).count() == 4
    gate = DecisionGate.objects.get(run=run)
    assert gate.status in {"FAIL", "FRAGILE", "ACCEPTABLE", "ROBUST"}
    exports = ExportFile.objects.filter(run=run)
    assert exports.count() == 2
    for export in exports:
        assert Path(export.path).is_file()
