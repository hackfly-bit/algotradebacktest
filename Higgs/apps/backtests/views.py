from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.backtests.forms import BacktestRunForm
from apps.backtests.models import BacktestRun, MetricSet, Trade, WalkForwardFold
from apps.backtests.tasks import create_screening_runs, enqueue_run
from apps.marketdata.models import Dataset

VALID_TABS = {"overview", "equity", "trades", "splits", "walkforward"}


def _metric_map(run: BacktestRun) -> dict[str, MetricSet | None]:
    rows = {m.split: m for m in run.metrics.all()}
    wf_summary = MetricSet.objects.filter(run=run, split="wf", label="summary").first()
    return {
        "full": rows.get("full"),
        "is": rows.get("is"),
        "oos": rows.get("oos"),
        "wf": wf_summary,
    }


def _run_tabs(run: BacktestRun) -> list[tuple[str, str]]:
    tabs = [
        ("overview", "Overview"),
        ("equity", "Equity"),
        ("trades", "Trades"),
        ("splits", "IS/OOS"),
    ]
    if run.multi_deep:
        tabs.append(("walkforward", "Walk-forward"))
    return tabs


def _enqueue(run_id: int) -> None:
    def _go():
        result = enqueue_run.enqueue(run_id)
        BacktestRun.objects.filter(pk=run_id).update(task_id=str(getattr(result, "id", "") or ""))

    transaction.on_commit(_go)


@login_required
def run_list(request):
    qs = BacktestRun.objects.select_related("dataset").exclude(strategy_name__in={"*", "all"})
    status = request.GET.get("status", "").strip()
    strategy = request.GET.get("strategy", "").strip()
    if status:
        qs = qs.filter(status=status)
    if strategy:
        qs = qs.filter(strategy_name=strategy)
    runs = qs.order_by("-created_at")[:100]
    rows = []
    for run in runs:
        m = MetricSet.objects.filter(run=run, split="full").first()
        rows.append({"run": run, "metric": m})
    return render(
        request,
        "backtests/run_list.html",
        {
            "page_title": "Run",
            "runs": rows,
            "status_filter": status,
            "strategy_filter": strategy,
        },
    )


@login_required
def run_new(request):
    if not Dataset.objects.exists():
        return render(
            request,
            "backtests/run_new.html",
            {
                "page_title": "Run baru",
                "form": None,
                "no_dataset": True,
            },
        )
    form = BacktestRunForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        ds = data["dataset"]
        params = {"volume_usable": ds.volume_usable}
        with transaction.atomic():
            if data["strategy_name"] == "*":
                parent = BacktestRun.objects.create(
                    dataset=ds,
                    strategy_name="*",
                    params=params,
                    initial_equity=data["initial_equity"],
                    fee=data["fee"],
                    commission_per_lot=data["commission_per_lot"],
                    spread=data["spread"],
                    slippage=data["slippage"],
                    risk_pct=data["risk_pct"],
                    contract_size=data["contract_size"],
                    in_sample_end=data["in_sample_end"],
                    oos_start=data["oos_start"],
                    multi_deep=data["multi_deep"],
                    status=BacktestRun.Status.QUEUED,
                    created_by=request.user,
                )
                children = create_screening_runs(parent)
                for child in children:
                    _enqueue(child.pk)
                redirect_pk = parent.pk
            else:
                run = BacktestRun.objects.create(
                    dataset=ds,
                    strategy_name=data["strategy_name"],
                    params=params,
                    initial_equity=data["initial_equity"],
                    fee=data["fee"],
                    commission_per_lot=data["commission_per_lot"],
                    spread=data["spread"],
                    slippage=data["slippage"],
                    risk_pct=data["risk_pct"],
                    contract_size=data["contract_size"],
                    in_sample_end=data["in_sample_end"],
                    oos_start=data["oos_start"],
                    multi_deep=data["multi_deep"],
                    status=BacktestRun.Status.QUEUED,
                    created_by=request.user,
                )
                _enqueue(run.pk)
                redirect_pk = run.pk
        return redirect("backtests:run_detail", pk=redirect_pk)
    return render(
        request,
        "backtests/run_new.html",
        {
            "page_title": "Run baru",
            "form": form,
            "no_dataset": False,
        },
    )


@login_required
def run_detail(request, pk):
    run = get_object_or_404(BacktestRun.objects.select_related("dataset"), pk=pk)
    if run.strategy_name in {"*", "all"}:
        children = run.children.select_related("dataset").order_by("strategy_name")
        return render(
            request,
            "backtests/run_screening.html",
            {
                "page_title": f"Screening #{run.pk}",
                "parent": run,
                "children": [
                    {
                        "run": c,
                        "metrics": _metric_map(c),
                    }
                    for c in children
                ],
            },
        )
    tab = request.GET.get("tab", "overview")
    if tab not in VALID_TABS:
        tab = "overview"
    if tab == "walkforward" and not run.multi_deep:
        tab = "overview"
    metrics = _metric_map(run)
    equity_json = "[]"
    if metrics["full"] and metrics["full"].extras.get("equity_curve"):
        import json

        equity_json = json.dumps(metrics["full"].extras["equity_curve"])

    page_obj = None
    if tab == "trades":
        paginator = Paginator(run.trades.order_by("-entry_time"), 50)
        page_obj = paginator.get_page(request.GET.get("page"))

    split_rows = [
        ("full", metrics["full"]),
        ("is", metrics["is"]),
        ("oos", metrics["oos"]),
    ]
    tabs = _run_tabs(run)
    wf_folds = list(run.wf_folds.all()) if run.multi_deep else []
    wf_summary = metrics.get("wf")
    return render(
        request,
        "backtests/run_detail.html",
        {
            "page_title": f"Run #{run.pk}",
            "run": run,
            "metrics": metrics,
            "active_tab": tab,
            "equity_json": equity_json,
            "page_obj": page_obj,
            "split_rows": split_rows,
            "tabs": tabs,
            "wf_folds": wf_folds,
            "wf_summary": wf_summary,
        },
    )


@login_required
def run_partial(request, pk, tab):
    if tab not in VALID_TABS:
        raise Http404
    run = get_object_or_404(BacktestRun.objects.select_related("dataset"), pk=pk)
    if run.strategy_name in {"*", "all"}:
        raise Http404
    if tab == "walkforward" and not run.multi_deep:
        raise Http404
    metrics = _metric_map(run)
    ctx = {
        "run": run,
        "metrics": metrics,
        "active_tab": tab,
    }
    if tab == "trades":
        paginator = Paginator(run.trades.order_by("-entry_time"), 50)
        ctx["page_obj"] = paginator.get_page(request.GET.get("page"))
    if tab == "equity":
        import json

        curve = []
        if metrics["full"] and metrics["full"].extras.get("equity_curve"):
            curve = metrics["full"].extras["equity_curve"]
        ctx["equity_json"] = json.dumps(curve)
    if tab == "walkforward":
        ctx["wf_folds"] = list(run.wf_folds.all())
        ctx["wf_summary"] = metrics.get("wf")
    return render(request, f"backtests/partials/tab_{tab}.html", ctx)


@login_required
def run_status(request, pk):
    run = get_object_or_404(BacktestRun, pk=pk)
    if run.strategy_name in {"*", "all"}:
        children = list(run.children.all())
        done = sum(1 for c in children if c.status == BacktestRun.Status.DONE)
        total = len(children)
        if run.status == BacktestRun.Status.DONE:
            text = f"Screening selesai ({total}/{total})"
            badge = "badge-profit"
        elif run.status == BacktestRun.Status.RUNNING:
            text = f"Screening berjalan ({done}/{total})"
            badge = "badge-warn"
        elif run.status == BacktestRun.Status.FAILED:
            text = "Screening gagal"
            badge = "badge-loss"
        else:
            text = f"Screening antrian ({done}/{total})"
            badge = "badge-neutral"
    else:
        badge = {
            BacktestRun.Status.DONE: "badge-profit",
            BacktestRun.Status.RUNNING: "badge-warn",
            BacktestRun.Status.FAILED: "badge-loss",
        }.get(run.status, "badge-neutral")
        text = {
            BacktestRun.Status.DONE: f"Run #{run.pk} selesai",
            BacktestRun.Status.RUNNING: f"Run #{run.pk} berjalan",
            BacktestRun.Status.FAILED: f"Run #{run.pk} gagal",
            BacktestRun.Status.QUEUED: f"Run #{run.pk} antrian",
        }.get(run.status, run.status)
    polling = run.status in {BacktestRun.Status.QUEUED, BacktestRun.Status.RUNNING}
    if run.strategy_name in {"*", "all"} and run.status not in {
        BacktestRun.Status.DONE,
        BacktestRun.Status.FAILED,
    }:
        polling = True
    return render(
        request,
        "backtests/partials/status.html",
        {
            "status_text": text,
            "badge_class": badge,
            "polling": polling,
            "run_id": run.pk,
        },
    )


@login_required
def compare(request):
    parent_id = request.GET.get("batch")
    if parent_id:
        parent = get_object_or_404(BacktestRun, pk=parent_id, strategy_name="*")
        runs = parent.children.all().order_by("strategy_name")
        batch_label = f"Screening #{parent.pk}"
    else:
        parent = (
            BacktestRun.objects.filter(strategy_name="*", status=BacktestRun.Status.DONE)
            .order_by("-created_at")
            .first()
        )
        runs = parent.children.all().order_by("strategy_name") if parent else BacktestRun.objects.none()
        batch_label = f"Screening #{parent.pk}" if parent else "Belum ada screening"

    rows = []
    for run in runs:
        metrics = _metric_map(run)
        is_m = metrics["is"]
        oos_m = metrics["oos"]
        rows.append(
            {
                "run": run,
                "is_sharpe": is_m.sharpe if is_m else None,
                "is_return": is_m.total_return if is_m else None,
                "is_dd": is_m.max_drawdown if is_m else None,
                "is_trades": is_m.trades if is_m else None,
                "oos_sharpe": oos_m.sharpe if oos_m else None,
                "oos_return": oos_m.total_return if oos_m else None,
                "oos_dd": oos_m.max_drawdown if oos_m else None,
                "oos_trades": oos_m.trades if oos_m else None,
            }
        )
    rows.sort(key=lambda r: (r["oos_sharpe"] is None, -(r["oos_sharpe"] or -999)))

    batches = BacktestRun.objects.filter(strategy_name="*").order_by("-created_at")[:10]
    return render(
        request,
        "backtests/compare.html",
        {
            "page_title": "Bandingkan",
            "rows": rows,
            "batch_label": batch_label,
            "batches": batches,
            "selected_batch": parent,
        },
    )


@login_required
def global_status(request):
    active = (
        BacktestRun.objects.filter(status__in=[BacktestRun.Status.QUEUED, BacktestRun.Status.RUNNING])
        .exclude(strategy_name__in={"*", "all"})
        .order_by("-created_at")
        .first()
    )
    screening = (
        BacktestRun.objects.filter(
            strategy_name="*",
            status__in=[BacktestRun.Status.QUEUED, BacktestRun.Status.RUNNING],
        )
        .order_by("-created_at")
        .first()
    )
    target = active or screening
    if not target:
        return render(
            request,
            "backtests/partials/status.html",
            {
                "status_text": "Tidak ada job berjalan",
                "badge_class": "badge-neutral",
                "polling": False,
                "run_id": None,
            },
        )
    return run_status(request, target.pk)
