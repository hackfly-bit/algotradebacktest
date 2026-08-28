from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render

import engine.strategies  # noqa: F401
from apps.backtests.models import BacktestRun, MetricSet
from apps.core.forms import BacktestSettingsForm
from apps.core.models import BacktestSettings
from apps.marketdata.models import Dataset
from engine.registry import list_strategies


@login_required
def overview(request):
    runs = BacktestRun.objects.all()
    status_counts = runs.values("status").annotate(n=Count("id"))
    by_status = {row["status"]: row["n"] for row in status_counts}

    recent_runs = runs.select_related("dataset").order_by("-created_at")[:8]
    run_ids = [run.pk for run in recent_runs]
    metrics = {
        m.run_id: m
        for m in MetricSet.objects.filter(run_id__in=run_ids, split="full").only(
            "run_id", "final_equity", "sharpe", "trades"
        )
    }
    recent = []
    for run in recent_runs:
        metric = metrics.get(run.pk)
        recent.append(
            {
                "id": run.pk,
                "strategy_name": run.strategy_name,
                "status": run.status,
                "created_at": run.created_at,
                "final_equity": metric.final_equity if metric else None,
                "sharpe": metric.sharpe if metric else None,
                "trades": metric.trades if metric else None,
            }
        )

    latest = Dataset.objects.order_by("-created_at").first()
    return render(
        request,
        "core/overview.html",
        {
            "page_title": "Ringkasan",
            "dataset_count": Dataset.objects.count(),
            "strategy_count": len(list_strategies()),
            "run_total": runs.count(),
            "run_done": by_status.get(BacktestRun.Status.DONE, 0),
            "run_running": by_status.get(BacktestRun.Status.RUNNING, 0),
            "run_failed": by_status.get(BacktestRun.Status.FAILED, 0),
            "recent_runs": recent,
            "latest_dataset": latest,
        },
    )


@login_required
def app_settings(request):
    cfg = BacktestSettings.load()
    form = BacktestSettingsForm(request.POST or None, instance=cfg)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Default backtest disimpan.")
        return redirect("core:settings")
    return render(
        request,
        "core/settings.html",
        {
            "page_title": "Pengaturan",
            "form": form,
            "async_jobs": True,
        },
    )
