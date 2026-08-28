"""UI flow tests for backtest runs."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from django.test import Client
from django.urls import reverse

from apps.backtests.models import BacktestRun, MetricSet
from apps.backtests.tasks import create_screening_runs, enqueue_run
from apps.marketdata.models import Dataset


def _write_mini_h1(path: Path, n: int = 500) -> None:
    index = pd.date_range("2020-01-02", periods=n, freq="h")
    close = 1800 + np.linspace(0, 40, n)
    high = close + 2.0
    low = close - 2.0
    high[250] = high[249] + 10
    close[250] = high[250] - 0.5
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
def test_screening_creates_five_children_with_is_oos_metrics():
    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_screen" / "h1.parquet"
    _write_mini_h1(cache)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="screen-mini",
        raw_path=str(cache),
        cache_path=str(cache),
        rows_m1=0,
        rows_h1=500,
        volume_usable=False,
        validation={},
    )
    parent = BacktestRun.objects.create(
        dataset=ds,
        strategy_name="*",
        params={"volume_usable": False},
        in_sample_end=date(2020, 1, 15),
        oos_start=date(2020, 1, 18),
        status=BacktestRun.Status.QUEUED,
    )
    children = create_screening_runs(parent)
    assert len(children) == 5
    for child in children:
        enqueue_run.enqueue(child.pk)
    parent.refresh_from_db()
    assert parent.status == BacktestRun.Status.DONE
    for child in children:
        child.refresh_from_db()
        assert child.status == BacktestRun.Status.DONE
        assert MetricSet.objects.filter(run=child, split="is").exists()
        assert MetricSet.objects.filter(run=child, split="oos").exists()


@pytest.mark.django_db
def test_run_pages_render(client: Client, django_user_model):
    user = django_user_model.objects.create_user("trader", password="pass")
    client.force_login(user)
    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_ui" / "h1.parquet"
    _write_mini_h1(cache, n=400)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="ui-mini",
        raw_path=str(cache),
        cache_path=str(cache),
        rows_m1=0,
        rows_h1=400,
        volume_usable=False,
        validation={},
    )
    parent = BacktestRun.objects.create(
        dataset=ds,
        strategy_name="*",
        params={"volume_usable": False},
        in_sample_end=date(2020, 1, 10),
        oos_start=date(2020, 1, 15),
        status=BacktestRun.Status.QUEUED,
    )
    for child in create_screening_runs(parent):
        enqueue_run.enqueue(child.pk)

    assert client.get(reverse("backtests:run_new")).status_code == 200
    assert client.get(reverse("backtests:run_list")).status_code == 200
    resp = client.get(reverse("backtests:compare"))
    assert resp.status_code == 200
    assert b"breakout_atr" in resp.content or b"ema_rsi_volume" in resp.content
