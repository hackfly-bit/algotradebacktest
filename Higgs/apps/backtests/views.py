from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.backtests.forms import BacktestRunForm
from apps.backtests.job_runner import dispatch_run
from apps.backtests.models import BacktestRun, DecisionGate, MetricSet, Trade
from apps.backtests.tasks import create_screening_runs
from apps.marketdata.models import Dataset

VALID_TABS = {
    "overview",
    "equity",
    "trades",
    "splits",
    "walkforward",
    "robustness",
    "cost",
    "montecarlo",
    "gate",
    "export",
}
DEEP_TABS = {"walkforward", "robustness", "cost", "montecarlo", "gate", "export"}


def _metric_map(run: BacktestRun) -> dict[str, MetricSet | None]:
    rows = {m.split: m for m in run.metrics.all()}
    return {
        "full": rows.get("full"),
        "is": rows.get("is"),
        "oos": rows.get("oos"),
        "wf": MetricSet.objects.filter(run=run, split="wf", label="summary").first(),
        "robustness": MetricSet.objects.filter(run=run, split="robustness", label="summary").first(),
        "mc": MetricSet.objects.filter(run=run, split="mc", label="summary").first(),
    }


def _run_tabs(run: BacktestRun) -> list[tuple[str, str]]:
    tabs = [
        ("overview", "Overview"),
        ("equity", "Equity"),
        ("trades", "Trades"),
        ("splits", "IS/OOS"),
    ]
    if run.multi_deep:
        tabs.extend(
            [
                ("walkforward", "Walk-forward"),
                ("robustness", "Robustness"),
                ("cost", "Cost stress"),
                ("montecarlo", "Monte Carlo"),
                ("gate", "Gate"),
                ("export", "Export"),
            ]
        )
    return tabs


def _deep_context(run: BacktestRun, metrics: dict) -> dict:
    rob_summary = metrics.get("robustness")
    param_rows = run.robustness_rows.filter(kind="param_grid").order_by("label")
    perturb_rows = run.robustness_rows.filter(kind="ema_perturb").order_by("label")
    cost_rows = run.robustness_rows.filter(kind="cost_stress").order_by("label")
    try:
        gate = run.decision_gate
    except DecisionGate.DoesNotExist:
        gate = None
    exports = list(run.exports.all())
    mc_rows = list(run.mc_summaries.all())
    export_preview = ""
    md = next((e for e in exports if e.kind == "md"), None)
    if md:
        try:
            export_preview = open(md.path, encoding="utf-8").read()[:8000]
        except OSError:
            export_preview = ""
    mc_hist_json = "null"
    boot = next((m for m in mc_rows if m.mode == "bootstrap"), None)
    if boot and boot.extras.get("histogram"):
        import json

        mc_hist_json = json.dumps(boot.extras["histogram"])
    return {
        "wf_folds": list(run.wf_folds.all()),
        "wf_summary": metrics.get("wf"),
        "rob_summary": rob_summary,
        "param_rows": param_rows,
        "perturb_rows": perturb_rows,
        "cost_rows": cost_rows,
        "mc_rows": mc_rows,
        "mc_summary": metrics.get("mc"),
        "mc_hist_json": mc_hist_json,
        "gate": gate,
        "exports": exports,
        "export_preview": export_preview,
    }


def _resolve_tab(run: BacktestRun, tab: str) -> str:
    if tab not in VALID_TABS:
        return "overview"
    if tab in DEEP_TABS and not run.multi_deep:
        return "overview"
    return tab


def _enqueue(run_id: int) -> None:
    def _go():
        dispatch_run(run_id)
        BacktestRun.objects.filter(pk=run_id).update(task_id=f"async-{run_id}")

    transaction.on_commit(_go)


@login_required
def run_list(request):
    qs = (
        BacktestRun.objects.select_related("dataset")
        .exclude(strategy_name__in={"*", "all"})
        .prefetch_related("decision_gate")
    )
    status = request.GET.get("status", "").strip()
    strategy = request.GET.get("strategy", "").strip()
    gate = request.GET.get("gate", "").strip()
    if status:
        qs = qs.filter(status=status)
    if strategy:
        qs = qs.filter(strategy_name=strategy)
    if gate:
        qs = qs.filter(decision_gate__status=gate)
    runs = qs.order_by("-created_at")[:100]
    metric_map = {
        m.run_id: m
        for m in MetricSet.objects.filter(run_id__in=[r.pk for r in runs], split="full")
    }
    rows = [{"run": run, "metric": metric_map.get(run.pk)} for run in runs]
    return render(
        request,
        "backtests/run_list.html",
        {
            "page_title": "Run",
            "runs": rows,
            "status_filter": status,
            "strategy_filter": strategy,
            "gate_filter": gate,
        },
    )


@login_required
def run_new(request):
    if not Dataset.objects.exists():
        return render(
            request,
            "backtests/run_new.html",
            {"page_title": "Run baru", "form": None, "no_dataset": True},
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
        {"page_title": "Run baru", "form": form, "no_dataset": False},
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
                "children": [{"run": c, "metrics": _metric_map(c)} for c in children],
            },
        )
    tab = _resolve_tab(run, request.GET.get("tab", "overview"))
    metrics = _metric_map(run)
    equity_json = "[]"
    if metrics["full"] and metrics["full"].extras.get("equity_curve"):
        import json

        equity_json = json.dumps(metrics["full"].extras["equity_curve"])

    page_obj = None
    if tab == "trades":
        paginator = Paginator(run.trades.order_by("-entry_time"), 50)
        page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "page_title": f"Run #{run.pk}",
        "run": run,
        "metrics": metrics,
        "active_tab": tab,
        "equity_json": equity_json,
        "page_obj": page_obj,
        "split_rows": [("full", metrics["full"]), ("is", metrics["is"]), ("oos", metrics["oos"])],
        "tabs": _run_tabs(run),
    }
    if run.multi_deep:
        ctx.update(_deep_context(run, metrics))
    return render(request, "backtests/run_detail.html", ctx)


@login_required
def run_partial(request, pk, tab):
    if tab not in VALID_TABS:
        raise Http404
    run = get_object_or_404(BacktestRun.objects.select_related("dataset"), pk=pk)
    if run.strategy_name in {"*", "all"}:
        raise Http404
    if tab in DEEP_TABS and not run.multi_deep:
        raise Http404
    metrics = _metric_map(run)
    ctx = {"run": run, "metrics": metrics, "active_tab": tab}
    if tab == "trades":
        paginator = Paginator(run.trades.order_by("-entry_time"), 50)
        ctx["page_obj"] = paginator.get_page(request.GET.get("page"))
    if tab == "equity":
        import json

        curve = []
        if metrics["full"] and metrics["full"].extras.get("equity_curve"):
            curve = metrics["full"].extras["equity_curve"]
        ctx["equity_json"] = json.dumps(curve)
    if run.multi_deep:
        ctx.update(_deep_context(run, metrics))
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
        gate = None
        try:
            gate = run.decision_gate
        except DecisionGate.DoesNotExist:
            pass
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
                "gate_status": gate.status if gate else None,
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
