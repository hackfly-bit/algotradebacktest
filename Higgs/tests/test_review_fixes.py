"""Tests for code-review fixes (security, tuning, async)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse

from apps.backtests.models import BacktestRun
from apps.backtests.tasks import execute_run
from apps.marketdata.models import Dataset
from apps.reports.models import ExportFile
from engine.tuning import get_strategy_tuning


def test_breakout_uses_lookback_tuning():
    tuning = get_strategy_tuning("breakout_atr")
    assert "lookback" in tuning.wf_variants[0]
    assert "ema_fast" not in tuning.wf_variants[0]


def test_ema_strategy_uses_ema_tuning():
    tuning = get_strategy_tuning("ema_rsi_volume")
    assert "ema_fast" in tuning.wf_variants[0]


@pytest.mark.django_db
def test_local_path_rejected_outside_media():
    user = User.objects.create_user("sec", password="pass")
    client = Client()
    client.force_login(user)
    with tempfile.TemporaryDirectory() as tmp:
        outside = Path(tmp) / "outside.csv"
        pd.DataFrame({"Datetime": [], "Open": [], "High": [], "Low": [], "Close": [], "Volume": []}).to_csv(
            outside, index=False
        )
        with override_settings(MEDIA_ROOT=str(Path(tmp) / "media")):
            response = client.post(
                reverse("marketdata:dataset_list"),
                {
                    "source_name": "bad",
                    "symbol": "XAUUSD",
                    "timeframe": "1H",
                    "local_path": str(outside),
                },
            )
            assert response.status_code == 200
            assert "Path harus berada" in response.content.decode()


@pytest.mark.django_db
def test_export_download_rejects_path_outside_exports():
    user = User.objects.create_user("exp", password="pass")
    client = Client()
    client.force_login(user)
    run = BacktestRun.objects.create(
        dataset=Dataset.objects.create(
            symbol="X",
            timeframe="1H",
            source_name="x",
            raw_path="x",
            cache_path="x",
            rows_m1=0,
            rows_h1=0,
            volume_usable=False,
            validation={},
        ),
        strategy_name="breakout_atr",
        status=BacktestRun.Status.DONE,
    )
    export = ExportFile.objects.create(
        run=run,
        kind="md",
        path="/etc/passwd",
        filename="passwd.md",
    )
    response = client.get(reverse("reports:export_download", args=[export.pk]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_execute_run_failure_does_not_raise():
    run = BacktestRun.objects.create(
        dataset=Dataset.objects.create(
            symbol="X",
            timeframe="1H",
            source_name="x",
            raw_path="/missing.parquet",
            cache_path="/missing.parquet",
            rows_m1=0,
            rows_h1=0,
            volume_usable=False,
            validation={},
        ),
        strategy_name="breakout_atr",
        status=BacktestRun.Status.QUEUED,
    )
    execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == BacktestRun.Status.FAILED
    assert run.error_message


@pytest.mark.django_db
def test_settings_page_saves_defaults():
    user = User.objects.create_user("cfg", password="pass")
    client = Client()
    client.force_login(user)
    response = client.post(
        reverse("core:settings"),
        {
            "initial_equity": "15000",
            "fee": "0",
            "commission_per_lot": "7",
            "spread": "0.3",
            "slippage": "0.0001",
            "risk_pct": "0.01",
            "contract_size": "100",
            "in_sample_end": "2023-12-31",
            "oos_start": "2024-01-01",
        },
    )
    assert response.status_code == 302
    from apps.core.models import BacktestSettings

    cfg = BacktestSettings.load()
    assert cfg.initial_equity == 15000


@pytest.mark.django_db(transaction=True)
def test_run_new_dispatches_async():
    user = User.objects.create_user("async", password="pass")
    client = Client()
    client.force_login(user)
    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_async" / "h1.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.is_file():
        import numpy as np

        idx = pd.date_range("2020-01-02", periods=200, freq="h")
        close = 1800 + np.linspace(0, 10, 200)
        pd.DataFrame(
            {"Datetime": idx, "Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 0}
        ).to_parquet(cache, index=False)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="async-mini",
        raw_path=str(cache),
        cache_path=str(cache),
        rows_m1=0,
        rows_h1=200,
        volume_usable=False,
        validation={},
    )
    with patch("apps.backtests.views.dispatch_run") as dispatch:
        response = client.post(
            reverse("backtests:run_new"),
            {
                "dataset": ds.pk,
                "strategy_name": "breakout_atr",
                "initial_equity": "10000",
                "fee": "0",
                "commission_per_lot": "7",
                "spread": "0.25",
                "slippage": "0.0001",
                "risk_pct": "0.01",
                "contract_size": "100",
                "in_sample_end": "2020-01-10",
                "oos_start": "2020-01-15",
            },
        )
        assert response.status_code == 302
        assert dispatch.called
