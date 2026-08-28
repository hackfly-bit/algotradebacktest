"""UI tests for strategy builder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from django.test import Client
from django.urls import reverse

from apps.backtests.models import BacktestRun, MetricSet
from apps.backtests.tasks import enqueue_run
from apps.marketdata.models import Dataset
from apps.strategies.models import StrategyDefinition
from apps.strategies.services import load_builtin_templates

TEMPLATES = load_builtin_templates()


@pytest.mark.django_db
def test_builder_crud_and_run(client, django_user_model):
    user = django_user_model.objects.create_user("builder", password="pass")
    client.force_login(user)
    defn = dict(TEMPLATES["breakout_atr"])
    defn["label"] = "My Breakout"
    resp = client.post(
        reverse("strategies:builder_new"),
        {
            "label": "My Breakout",
            "slug": "my_breakout",
            "description": "test",
            "allow_short": False,
            "status": "active",
            "template_key": "",
            "definition_raw": json.dumps(defn),
        },
    )
    assert resp.status_code == 302
    sd = StrategyDefinition.objects.get(slug="custom_my_breakout")
    assert sd.status == StrategyDefinition.Status.ACTIVE

    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_builder" / "h1.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2020-01-02", periods=400, freq="h")
    close = 1800 + np.linspace(0, 40, 400)
    pd.DataFrame(
        {"Datetime": idx, "Open": close, "High": close + 2, "Low": close - 2, "Close": close, "Volume": 0}
    ).to_parquet(cache, index=False)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="builder-mini",
        raw_path=str(cache),
        cache_path=str(cache),
        rows_m1=0,
        rows_h1=400,
        volume_usable=False,
        validation={},
    )
    run = BacktestRun.objects.create(
        dataset=ds,
        strategy_name=sd.slug,
        params={"volume_usable": False},
        status=BacktestRun.Status.QUEUED,
    )
    enqueue_run.enqueue(run.pk)
    run.refresh_from_db()
    assert run.status == BacktestRun.Status.DONE
    assert MetricSet.objects.filter(run=run, split="full").exists()


@pytest.mark.django_db
def test_builder_list_and_preview(client, django_user_model):
    user = django_user_model.objects.create_user("prev", password="pass")
    client.force_login(user)
    StrategyDefinition.objects.create(
        slug="custom_preview",
        label="Preview",
        definition_json=TEMPLATES["breakout_atr"],
        status=StrategyDefinition.Status.ACTIVE,
        logic_spec="spec",
    )
    assert client.get(reverse("strategies:builder_list")).status_code == 200
    sd = StrategyDefinition.objects.get(slug="custom_preview")
    resp = client.get(reverse("strategies:builder_preview", args=[sd.pk]))
    assert resp.status_code == 200
    assert b"Dataset tidak tersedia" in resp.content or b"signal-chart" in resp.content
