"""Tests for walk-forward engine and persistence."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.backtests.models import BacktestRun, MetricSet, WalkForwardFold
from apps.backtests.tasks import enqueue_run
from apps.marketdata.models import Dataset
from engine.walk_forward import (
    evaluate_wf_pass,
    run_walk_forward,
    walk_forward_windows,
    WalkForwardFoldResult,
)
from engine.tuning import get_strategy_tuning


def test_walk_forward_windows_full_xauusd_range():
    windows = walk_forward_windows("2009-03-15", "2026-01-09")
    assert len(windows) == 13
    dev_s, dev_e, val_s, val_e = windows[0]
    assert dev_s == "2009-03-15"
    assert dev_e == "2012-03-14"
    assert val_s == "2012-03-15"
    assert val_e == "2013-03-14"


def test_evaluate_wf_pass_notebook_rule():
    folds = [
        WalkForwardFoldResult("a", "b", "c", "d", 20, 1.0, 0.5, 0.02, -0.1, 10, True),
        WalkForwardFoldResult("a", "b", "c", "d", 20, 1.0, -0.1, -0.01, -0.2, 8, False),
    ]
    passed, summary = evaluate_wf_pass(folds)
    assert passed is True
    assert summary["pct_positive_sharpe"] == 0.5
    assert summary["median_val_return"] == pytest.approx(0.005)

    folds_fail = [
        WalkForwardFoldResult("a", "b", "c", "d", 20, 1.0, -0.5, -0.02, -0.1, 10, False),
        WalkForwardFoldResult("a", "b", "c", "d", 20, 1.0, -0.1, -0.01, -0.2, 8, False),
    ]
    failed, _ = evaluate_wf_pass(folds_fail)
    assert failed is False


def test_run_walk_forward_returns_folds_on_synthetic_data():
    n = 365 * 6
    index = pd.date_range("2016-01-01", periods=n, freq="D")
    close = 1800 + np.linspace(0, 60, n)
    df = pd.DataFrame(
        {
            "Datetime": index,
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": np.zeros(n),
        }
    )
    from engine.indicators import add_indicators

    df_ind = add_indicators(df)
    folds, wf_pass, summary = run_walk_forward(
        df_ind,
        "breakout_atr",
        {"volume_usable": False, "lookback": 12},
        train_years=3,
        test_years=1,
        step_years=1,
    )
    tuning = get_strategy_tuning("breakout_atr")
    assert tuning.wf_variants[0].get("lookback") is not None
    assert len(folds) >= 2
    assert "wf_pass" in summary
    assert isinstance(wf_pass, bool)


def _write_wf_dataset(path: Path, years: int = 6) -> None:
    n = years * 365
    index = pd.date_range("2016-01-01", periods=n, freq="D")
    close = 1800 + np.linspace(0, 80, n)
    high = close + 3
    low = close - 3
    high[400] = high[399] + 15
    close[400] = high[400] - 0.5
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
def test_multi_deep_persists_walk_forward_folds():
    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_wf" / "h1.parquet"
    _write_wf_dataset(cache)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="wf-mini",
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
    assert WalkForwardFold.objects.filter(run=run).count() >= 2
    summary = MetricSet.objects.get(run=run, split="wf", label="summary")
    assert "wf_pass" in summary.extras
    assert "WF_PASS" in run.params
