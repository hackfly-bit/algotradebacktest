"""UI tests for strategy builder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
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
    assert sd.created_by_id == user.pk

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
def test_builder_visual_editor_and_preview(client, django_user_model):
    user = django_user_model.objects.create_user("prev", password="pass")
    client.force_login(user)
    StrategyDefinition.objects.create(
        slug="custom_preview",
        label="Preview",
        definition_json=TEMPLATES["breakout_atr"],
        status=StrategyDefinition.Status.ACTIVE,
        logic_spec="spec",
        created_by=user,
    )
    list_resp = client.get(reverse("strategies:builder_list") + "?owner=mine")
    assert list_resp.status_code == 200
    assert b"custom_preview" in list_resp.content or b"Preview" in list_resp.content

    edit = client.get(reverse("strategies:builder_edit", args=[StrategyDefinition.objects.get().pk]))
    assert edit.status_code == 200
    assert b"Preset blocks" in edit.content
    assert b"strategyBuilder" in edit.content
    assert b"Parameters" in edit.content

    sd = StrategyDefinition.objects.get(slug="custom_preview")
    cache = Path(__file__).resolve().parents[1] / "media" / "cache" / "test_builder_prev" / "h1.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2020-01-02", periods=200, freq="h")
    close = 1800 + np.linspace(0, 10, 200)
    pd.DataFrame(
        {"Datetime": idx, "Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 0}
    ).to_parquet(cache, index=False)
    ds = Dataset.objects.create(
        symbol="XAUUSD",
        timeframe="1H",
        source_name="prev-mini",
        raw_path=str(cache),
        cache_path=str(cache),
        rows_m1=0,
        rows_h1=200,
        volume_usable=False,
        validation={},
    )
    resp = client.get(reverse("strategies:builder_preview", args=[sd.pk]) + f"?dataset={ds.pk}")
    assert resp.status_code == 200
    assert b"signal-chart" in resp.content
    assert b"equity_json" not in resp.content  # rendered into JS
    assert b"Close" in resp.content


@pytest.mark.django_db
def test_builder_validate_endpoint(client, django_user_model):
    user = django_user_model.objects.create_user("val", password="pass")
    client.force_login(user)
    ok = client.post(
        reverse("strategies:builder_validate"),
        data=json.dumps({"definition": TEMPLATES["breakout_atr"]}),
        content_type="application/json",
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    assert "logic_spec" in ok.json()

    bad = dict(TEMPLATES["breakout_atr"])
    bad["exit"] = {}
    fail = client.post(
        reverse("strategies:builder_validate"),
        data=json.dumps({"definition": bad}),
        content_type="application/json",
    )
    assert fail.status_code == 400
    assert fail.json()["ok"] is False


@pytest.mark.django_db
def test_builder_new_version(client, django_user_model):
    user = django_user_model.objects.create_user("ver", password="pass")
    client.force_login(user)
    sd = StrategyDefinition.objects.create(
        slug="custom_base",
        label="Base",
        definition_json=TEMPLATES["breakout_atr"],
        status=StrategyDefinition.Status.ACTIVE,
        created_by=user,
    )
    resp = client.post(reverse("strategies:builder_edit", args=[sd.pk]), {"action": "new_version"})
    assert resp.status_code == 302
    assert StrategyDefinition.objects.filter(parent=sd).count() == 1
