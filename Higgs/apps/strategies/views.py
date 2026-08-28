"""Strategy builder and listing views."""

from __future__ import annotations

import json

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

import engine.strategies  # noqa: F401
from apps.marketdata.models import Dataset
from apps.strategies.forms import StrategyDefinitionForm, StrategyImportForm
from apps.strategies.models import StrategyDefinition
from apps.strategies.presets import empty_definition, presets_for_json
from apps.strategies.registry_bridge import sync_custom_strategies
from apps.strategies.services import load_builtin_templates, list_builtin_names
from apps.strategies.validate_view import builder_validate  # noqa: F401 — re-export for urls
from engine.backtester import apply_strategy, run_backtest
from engine.data import slice_df
from engine.indicators import add_indicators
from engine.registry import DEFAULT_PARAMS, STRATEGY_SPECS, list_strategies
from engine.rule_spec import build_logic_spec

import pandas as pd

SHORT_STRATEGIES = {"trend_breakout_by_gemini", "momentum_squeeze_by_kimi"}
VOLUME_STRATEGIES = {"ema_rsi_volume"}


def _editor_context(form, *, is_new: bool, strategy=None, request=None, import_form=None) -> dict:
    templates = load_builtin_templates()
    if strategy and strategy.definition_json:
        defn = strategy.definition_json
    elif form.data.get("definition_raw"):
        try:
            defn = json.loads(form.data["definition_raw"])
        except json.JSONDecodeError:
            defn = empty_definition()
    elif form.initial.get("template_key") and form.initial["template_key"] in templates:
        defn = templates[form.initial["template_key"]]
    elif getattr(form, "cleaned_data", None) and form.cleaned_data.get("definition_json"):
        defn = form.cleaned_data["definition_json"]
    else:
        key = (request.GET.get("template") if request else "") or ""
        defn = templates.get(key) or empty_definition()
    forks = []
    parent = None
    if strategy:
        forks = list(strategy.forks.order_by("-created_at")[:8])
        parent = strategy.parent
    return {
        "page_title": "Strategi baru" if is_new else f"Edit {strategy.label}",
        "form": form,
        "import_form": import_form or StrategyImportForm(),
        "is_new": is_new,
        "strategy": strategy,
        "definition_json": json.dumps(defn),
        "presets_json": json.dumps(presets_for_json()),
        "logic_spec_preview": json.dumps(build_logic_spec(defn) if isinstance(defn, dict) else ""),
        "forks": forks,
        "parent": parent,
        "validate_url": reverse("strategies:builder_validate"),
    }


def _preview(spec: str, limit: int = 140) -> str:
    text = " ".join(spec.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _pair_params(items: list[tuple]) -> list[tuple]:
    pairs = []
    for i in range(0, len(items), 2):
        left = items[i]
        right = items[i + 1] if i + 1 < len(items) else None
        pairs.append((left, right))
    return pairs


@login_required
def strategy_list(request):
    sync_custom_strategies()
    rows = []
    for name in list_builtin_names():
        rows.append(
            {
                "name": name,
                "spec_preview": _preview(STRATEGY_SPECS.get(name, "")),
                "allow_short": name in SHORT_STRATEGIES,
                "uses_volume": name in VOLUME_STRATEGIES,
                "is_custom": False,
                "builder_id": None,
            }
        )
    for sd in StrategyDefinition.objects.filter(status=StrategyDefinition.Status.ACTIVE).order_by("label"):
        rows.append(
            {
                "name": sd.slug,
                "spec_preview": _preview(sd.logic_spec or sd.label),
                "allow_short": sd.allow_short,
                "uses_volume": "volume_filter" in json.dumps(sd.definition_json),
                "is_custom": True,
                "builder_id": sd.pk,
            }
        )
    return render(
        request,
        "strategies/strategy_list.html",
        {
            "page_title": "Strategi",
            "strategies": rows,
        },
    )


@login_required
def strategy_detail(request, slug):
    sync_custom_strategies()
    custom = StrategyDefinition.objects.filter(slug=slug).first()
    if custom:
        return render(
            request,
            "strategies/strategy_detail.html",
            {
                "page_title": custom.label,
                "name": custom.slug,
                "logic_spec": custom.logic_spec or build_logic_spec(custom.definition_json),
                "default_params": sorted((custom.definition_json.get("params") or {}).items()),
                "param_pairs": _pair_params(
                    sorted((k, v.get("default")) for k, v in (custom.definition_json.get("params") or {}).items())
                ),
                "allow_short": custom.allow_short,
                "is_custom": True,
                "builder_id": custom.pk,
            },
        )
    if slug not in STRATEGY_SPECS:
        raise Http404(f"Strategi «{slug}» tidak terdaftar.")
    params = sorted(DEFAULT_PARAMS.items())
    return render(
        request,
        "strategies/strategy_detail.html",
        {
            "page_title": slug,
            "name": slug,
            "logic_spec": STRATEGY_SPECS[slug],
            "default_params": params,
            "param_pairs": _pair_params(params),
            "allow_short": slug in SHORT_STRATEGIES,
            "is_custom": False,
            "builder_id": None,
        },
    )


@login_required
def builder_list(request):
    qs = StrategyDefinition.objects.exclude(status=StrategyDefinition.Status.ARCHIVED)
    owner = request.GET.get("owner", "mine")
    if owner == "mine":
        qs = qs.filter(created_by=request.user)
    elif owner == "others":
        qs = qs.exclude(created_by=request.user)
    custom = qs.order_by("-updated_at")
    templates = load_builtin_templates()
    return render(
        request,
        "strategies/builder/list.html",
        {
            "page_title": "Strategy Builder",
            "strategies": custom,
            "template_count": len(templates),
            "owner_filter": owner,
        },
    )


@login_required
def builder_new(request):
    template_key = request.GET.get("template", "")
    initial = {"template_key": template_key} if template_key else {}
    form = StrategyDefinitionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.is_builtin = False
        obj.save()
        from apps.strategies.registry_bridge import register_strategy_row

        if obj.status == StrategyDefinition.Status.ACTIVE:
            register_strategy_row(obj)
        sync_custom_strategies()
        messages.success(request, f"Strategi {obj.label} disimpan.")
        return redirect("strategies:builder_edit", pk=obj.pk)
    return render(
        request,
        "strategies/builder/edit.html",
        _editor_context(form, is_new=True, request=request, import_form=StrategyImportForm()),
    )


@login_required
def builder_edit(request, pk):
    obj = get_object_or_404(StrategyDefinition, pk=pk)
    if request.method == "POST" and request.POST.get("action") == "duplicate":
        clone = StrategyDefinition.objects.create(
            slug=f"custom_copy_{uuid.uuid4().hex[:8]}",
            label=f"{obj.label} (copy)",
            description=obj.description,
            schema_version=obj.schema_version,
            definition_json=obj.definition_json,
            allow_short=obj.allow_short,
            status=StrategyDefinition.Status.DRAFT,
            logic_spec=obj.logic_spec,
            parent=obj,
            created_by=request.user,
        )
        messages.success(request, "Duplikat dibuat sebagai draft.")
        return redirect("strategies:builder_edit", pk=clone.pk)
    if request.method == "POST" and request.POST.get("action") == "new_version":
        ver = StrategyDefinition.objects.filter(parent=obj).count() + 2
        clone = StrategyDefinition.objects.create(
            slug=f"custom_v{ver}_{uuid.uuid4().hex[:6]}",
            label=f"{obj.label} v{ver}",
            description=obj.description,
            schema_version=obj.schema_version,
            definition_json=obj.definition_json,
            allow_short=obj.allow_short,
            status=StrategyDefinition.Status.DRAFT,
            logic_spec=obj.logic_spec,
            parent=obj,
            created_by=request.user,
        )
        messages.success(request, f"Versi baru v{ver} dibuat sebagai draft.")
        return redirect("strategies:builder_edit", pk=clone.pk)

    form = StrategyDefinitionForm(request.POST or None, instance=obj)
    if request.method == "POST" and request.POST.get("action", "save") == "save" and form.is_valid():
        form.save()
        sync_custom_strategies()
        messages.success(request, "Strategi diperbarui.")
        return redirect("strategies:builder_edit", pk=obj.pk)
    return render(
        request,
        "strategies/builder/edit.html",
        _editor_context(form, is_new=False, strategy=obj, request=request, import_form=StrategyImportForm()),
    )


@login_required
def builder_archive(request, pk):
    obj = get_object_or_404(StrategyDefinition, pk=pk)
    if request.method == "POST":
        obj.status = StrategyDefinition.Status.ARCHIVED
        obj.save(update_fields=["status"])
        from apps.strategies.registry_bridge import unregister_strategy_slug

        unregister_strategy_slug(obj.slug)
        messages.success(request, "Strategi diarsipkan.")
    return redirect("strategies:builder_list")


@login_required
def builder_import(request):
    if request.method != "POST":
        return redirect("strategies:builder_new")
    form = StrategyImportForm(request.POST, request.FILES)
    if form.is_valid():
        defn = form.cleaned_data["definition"]
        slug = request.POST.get("slug", "imported").strip().lower().replace("-", "_")
        if not slug.startswith("custom_"):
            slug = f"custom_{slug}"
        obj = StrategyDefinition.objects.create(
            slug=slug,
            label=defn.get("label", slug),
            definition_json=defn,
            allow_short=bool(defn.get("allow_short")),
            status=StrategyDefinition.Status.DRAFT,
            logic_spec=build_logic_spec(defn),
            created_by=request.user,
        )
        messages.success(request, "Import berhasil.")
        return redirect("strategies:builder_edit", pk=obj.pk)
    messages.error(request, "Import gagal.")
    return redirect("strategies:builder_new")


@login_required
def builder_export(request, pk):
    obj = get_object_or_404(StrategyDefinition, pk=pk)
    payload = json.dumps(obj.definition_json, indent=2)
    response = HttpResponse(payload, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{obj.slug}.json"'
    return response


def _load_preview_df(dataset_id: int | None, max_bars: int = 500) -> pd.DataFrame:
    if dataset_id:
        ds = get_object_or_404(Dataset, pk=dataset_id)
        df = add_indicators(pd.read_parquet(ds.cache_path))
    else:
        ds = Dataset.objects.order_by("-created_at").first()
        if not ds:
            raise Http404("Tidak ada dataset untuk preview.")
        df = add_indicators(pd.read_parquet(ds.cache_path))
    return df.tail(max_bars)


@login_required
def builder_preview(request, pk):
    obj = get_object_or_404(StrategyDefinition, pk=pk)
    dataset_id = request.GET.get("dataset")
    try:
        df = _load_preview_df(int(dataset_id) if dataset_id else None, max_bars=300)
    except Http404:
        return render(
            request,
            "strategies/builder/preview.html",
            {
                "error": "Dataset tidak tersedia.",
                "strategy": obj,
                "equity_json": "[]",
                "markers_json": "[]",
                "datasets": [],
            },
        )
    sync_custom_strategies()
    ds = Dataset.objects.filter(pk=dataset_id).first() if dataset_id else Dataset.objects.order_by("-created_at").first()
    volume_usable = bool(ds.volume_usable) if ds else False
    params = {"volume_usable": volume_usable}
    for key, spec in (obj.definition_json.get("params") or {}).items():
        params[key] = spec.get("default")
    signals = apply_strategy(df, obj.slug, params)
    equity = []
    markers = []
    for _, row in signals.iterrows():
        ts = pd.Timestamp(row["Datetime"]).isoformat()
        equity.append({"ts": ts, "close": float(row["Close"]), "high": float(row["High"]), "low": float(row["Low"])})
        sig = int(row["signal"])
        if sig != 0:
            markers.append({"ts": ts, "close": float(row["Close"]), "signal": sig})
    datasets = Dataset.objects.order_by("-created_at")[:10]
    return render(
        request,
        "strategies/builder/preview.html",
        {
            "strategy": obj,
            "equity_json": json.dumps(equity),
            "markers_json": json.dumps(markers),
            "datasets": datasets,
            "selected_dataset": str(dataset_id) if dataset_id else (str(ds.pk) if ds else ""),
            "long_count": sum(1 for m in markers if m["signal"] == 1),
            "short_count": sum(1 for m in markers if m["signal"] == -1),
        },
    )


@login_required
@require_POST
def builder_quick_test(request, pk):
    obj = get_object_or_404(StrategyDefinition, pk=pk)
    dataset_id = request.POST.get("dataset")
    ds = get_object_or_404(Dataset, pk=dataset_id) if dataset_id else get_object_or_404(Dataset.objects.order_by("-created_at"))
    sync_custom_strategies()
    df = add_indicators(pd.read_parquet(ds.cache_path))
    df = slice_df(df, start=str(pd.to_datetime(df["Datetime"].min()).date()), end=None)
    if len(df) > 500:
        df = df.tail(500)
    params = {"volume_usable": bool(ds.volume_usable)}
    for key, spec in (obj.definition_json.get("params") or {}).items():
        params[key] = spec.get("default")
    signals = apply_strategy(df, obj.slug, params)
    result = run_backtest(signals, name=obj.slug, params=params)
    m = result.metrics
    return JsonResponse(
        {
            "sharpe": m.get("sharpe"),
            "total_return": m.get("total_return"),
            "trades": m.get("trades"),
            "max_drawdown": m.get("max_drawdown"),
        }
    )
