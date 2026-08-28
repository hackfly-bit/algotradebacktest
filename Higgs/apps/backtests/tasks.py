"""Background/backtest execution tasks."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from django.db import transaction
from django.tasks import task
from django.utils import timezone as dj_tz

import engine.strategies  # noqa: F401
from apps.backtests.models import BacktestRun, MetricSet, Trade, WalkForwardFold
from engine.backtester import apply_strategy, run_backtest
from engine.data import slice_df
from engine.indicators import add_indicators
from engine.registry import resolve_strategy_queue
from engine.walk_forward import run_walk_forward

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

DEFAULT_IN_SAMPLE_END = "2023-12-31"
DEFAULT_OOS_START = "2024-01-01"


def _aware(ts) -> datetime:
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = pd.Timestamp(ts).to_pydatetime()
    if dj_tz.is_naive(dt):
        return dj_tz.make_aware(dt, timezone.utc)
    return dt


def _downsample_equity(equity: pd.Series, max_points: int = 400) -> list[dict]:
    eq = equity.dropna()
    if eq.empty:
        return []
    if len(eq) <= max_points:
        idx = eq.index
    else:
        positions = np.linspace(0, len(eq) - 1, max_points, dtype=int)
        idx = eq.index[positions]
    out = []
    for ts in idx:
        val = eq.loc[ts]
        if isinstance(val, pd.Series):
            val = val.iloc[-1]
        out.append({"ts": pd.Timestamp(ts).isoformat(), "equity": float(val)})
    return out


def _persist_result(
    run: BacktestRun,
    result,
    split: str = "full",
    label: str = "",
    *,
    store_trades: bool = False,
    store_equity: bool = False,
) -> None:
    MetricSet.objects.filter(run=run, split=split, label=label).delete()
    if store_trades:
        Trade.objects.filter(run=run).delete()
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
    if store_equity:
        extras["equity_curve"] = _downsample_equity(result.equity)
    MetricSet.objects.create(run=run, split=split, label=label, extras=extras, **payload)


def _persist_walk_forward(run: BacktestRun, folds, wf_pass: bool, summary: dict) -> None:
    WalkForwardFold.objects.filter(run=run).delete()
    if folds:
        WalkForwardFold.objects.bulk_create(
            [
                WalkForwardFold(
                    run=run,
                    dev_start=fold.dev_start,
                    dev_end=fold.dev_end,
                    val_start=fold.val_start,
                    val_end=fold.val_end,
                    best_ema_fast=fold.chosen_ema_fast,
                    dev_sharpe=fold.dev_sharpe,
                    val_sharpe=fold.val_sharpe,
                    val_return=fold.val_return,
                    val_max_dd=fold.val_max_dd,
                    val_trades=fold.val_trades,
                    positive_sharpe=fold.positive_sharpe,
                )
                for fold in folds
            ],
            batch_size=200,
        )
    MetricSet.objects.filter(run=run, split="wf", label="summary").delete()
    MetricSet.objects.create(
        run=run,
        split="wf",
        label="summary",
        extras={**summary, "wf_pass": wf_pass},
    )
    params = dict(run.params or {})
    params["WF_PASS"] = wf_pass
    run.params = params
    run.save(update_fields=["params"])


def _run_backtest_on_df(
    df_ind: pd.DataFrame,
    strategy_name: str,
    run: BacktestRun,
    params: dict,
    *,
    start: str | None = None,
    end: str | None = None,
    name: str = "run",
):
    sl = slice_df(df_ind, start=start, end=end)
    signals = apply_strategy(sl, strategy_name, params)
    return run_backtest(
        signals,
        initial_equity=run.initial_equity,
        fee=run.fee,
        slippage=run.slippage,
        commission_per_lot=run.commission_per_lot,
        spread=run.spread,
        risk_pct=run.risk_pct,
        contract_size=run.contract_size,
        name=name,
        params=params,
    )


def execute_run(run_id: int) -> None:
    run = BacktestRun.objects.select_related("dataset").get(pk=run_id)
    if run.strategy_name in {"*", "all"}:
        return

    run.status = BacktestRun.Status.RUNNING
    run.started_at = dj_tz.now()
    run.error_message = ""
    run.save(update_fields=["status", "started_at", "error_message"])

    try:
        df = add_indicators(pd.read_parquet(run.dataset.cache_path))
        params = dict(run.params or {})
        params.setdefault("volume_usable", bool(run.dataset.volume_usable))
        strategy_name = run.strategy_name

        is_end = run.in_sample_end.isoformat() if run.in_sample_end else DEFAULT_IN_SAMPLE_END
        oos_start = run.oos_start.isoformat() if run.oos_start else DEFAULT_OOS_START

        full = _run_backtest_on_df(df, strategy_name, run, params, name=f"{strategy_name}_full")
        is_result = _run_backtest_on_df(
            df, strategy_name, run, params, end=is_end, name=f"{strategy_name}_is"
        )
        oos_result = _run_backtest_on_df(
            df, strategy_name, run, params, start=oos_start, name=f"{strategy_name}_oos"
        )

        with transaction.atomic():
            _persist_result(run, full, split="full", store_trades=True, store_equity=True)
            _persist_result(run, is_result, split="is")
            _persist_result(run, oos_result, split="oos")
            if run.multi_deep:
                folds, wf_pass, summary = run_walk_forward(
                    df,
                    strategy_name,
                    params,
                    initial_equity=run.initial_equity,
                    fee=run.fee,
                    slippage=run.slippage,
                    commission_per_lot=run.commission_per_lot,
                    spread=run.spread,
                    risk_pct=run.risk_pct,
                    contract_size=run.contract_size,
                )
                _persist_walk_forward(run, folds, wf_pass, summary)
            run.status = BacktestRun.Status.DONE
            run.finished_at = dj_tz.now()
            run.save(update_fields=["status", "finished_at"])

        if run.parent_id:
            _refresh_parent_status(run.parent_id)
    except Exception as exc:  # noqa: BLE001
        run.status = BacktestRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = dj_tz.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        if run.parent_id:
            _refresh_parent_status(run.parent_id)
        raise


def _refresh_parent_status(parent_id: int) -> None:
    parent = BacktestRun.objects.get(pk=parent_id)
    children = list(parent.children.all())
    if not children:
        return
    statuses = {c.status for c in children}
    if BacktestRun.Status.FAILED in statuses:
        parent.status = BacktestRun.Status.FAILED
    elif all(c.status == BacktestRun.Status.DONE for c in children):
        parent.status = BacktestRun.Status.DONE
    elif any(c.status == BacktestRun.Status.RUNNING for c in children):
        parent.status = BacktestRun.Status.RUNNING
    else:
        parent.status = BacktestRun.Status.QUEUED
    parent.finished_at = dj_tz.now() if parent.status in {
        BacktestRun.Status.DONE,
        BacktestRun.Status.FAILED,
    } else None
    parent.save(update_fields=["status", "finished_at"])


def create_screening_runs(parent: BacktestRun) -> list[BacktestRun]:
    names = resolve_strategy_queue("*")
    children = []
    for name in names:
        child = BacktestRun.objects.create(
            dataset=parent.dataset,
            strategy_name=name,
            parent=parent,
            params=parent.params,
            initial_equity=parent.initial_equity,
            fee=parent.fee,
            commission_per_lot=parent.commission_per_lot,
            spread=parent.spread,
            slippage=parent.slippage,
            risk_pct=parent.risk_pct,
            contract_size=parent.contract_size,
            in_sample_end=parent.in_sample_end,
            oos_start=parent.oos_start,
            multi_deep=parent.multi_deep,
            status=BacktestRun.Status.QUEUED,
            created_by=parent.created_by,
        )
        children.append(child)
    return children


@task
def enqueue_run(run_id: int) -> None:
    execute_run(run_id)
