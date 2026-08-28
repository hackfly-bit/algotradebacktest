"""Background/backtest execution tasks."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from django.db import transaction
from django.tasks import task
from django.utils import timezone as dj_tz

import engine.strategies  # noqa: F401
from apps.backtests.models import BacktestRun, MetricSet, Trade
from engine.backtester import apply_strategy, run_backtest
from engine.indicators import add_indicators
from engine.registry import resolve_strategy_queue

METRIC_FIELDS = {
    "final_equity",
    "total_return",
    "cagr",
    "sharpe",
    "sortino",
    "calmar",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "expectancy",
    "average_win",
    "average_loss",
    "trades",
    "average_trade",
    "longest_losing_streak",
    "recovery_factor",
    "years",
}


def _aware(ts) -> datetime:
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = pd.Timestamp(ts).to_pydatetime()
    if dj_tz.is_naive(dt):
        return dj_tz.make_aware(dt, timezone.utc)
    return dt


def _persist_result(run: BacktestRun, result, split: str = "full", label: str = "") -> None:
    Trade.objects.filter(run=run).delete()
    MetricSet.objects.filter(run=run, split=split, label=label).delete()
    if len(result.trades):
        Trade.objects.bulk_create(
            [
                Trade(
                    run=run,
                    entry_time=_aware(row["entry_time"]),
                    exit_time=_aware(row["exit_time"]),
                    direction=int(row["direction"]),
                    entry=float(row["entry"]),
                    exit=float(row["exit"]),
                    lots=float(row["lots"]),
                    pnl=float(row["pnl"]),
                    return_pct=float(row["return_pct"]),
                    reason=str(row["reason"]),
                )
                for _, row in result.trades.iterrows()
            ],
            batch_size=1000,
        )
    metrics = result.metrics
    payload = {k: metrics.get(k) for k in METRIC_FIELDS if k in metrics}
    extras = {k: v for k, v in metrics.items() if k not in METRIC_FIELDS and k != "error"}
    MetricSet.objects.create(run=run, split=split, label=label, extras=extras, **payload)


def execute_run(run_id: int) -> None:
    run = BacktestRun.objects.select_related("dataset").get(pk=run_id)
    run.status = BacktestRun.Status.RUNNING
    run.started_at = dj_tz.now()
    run.error_message = ""
    run.save(update_fields=["status", "started_at", "error_message"])

    try:
        cache_path = run.dataset.cache_path
        df = add_indicators(pd.read_parquet(cache_path))
        params = dict(run.params or {})
        params.setdefault("volume_usable", bool(run.dataset.volume_usable))

        names = resolve_strategy_queue(run.strategy_name)
        # Parent screening (*) expands later; for now run first / single name on this row
        name = names[0] if run.strategy_name in {"*", "all"} else run.strategy_name
        signals = apply_strategy(df, name, params)
        result = run_backtest(
            signals,
            initial_equity=run.initial_equity,
            fee=run.fee,
            slippage=run.slippage,
            commission_per_lot=run.commission_per_lot,
            spread=run.spread,
            risk_pct=run.risk_pct,
            contract_size=run.contract_size,
            name=f"{name}_full",
            params=params,
        )
        with transaction.atomic():
            _persist_result(run, result, split="full")
            run.status = BacktestRun.Status.DONE
            run.finished_at = dj_tz.now()
            run.save(update_fields=["status", "finished_at"])
    except Exception as exc:  # noqa: BLE001 — persist failure on the run row
        run.status = BacktestRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = dj_tz.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        raise


@task
def enqueue_run(run_id: int) -> None:
    execute_run(run_id)
