"""Background/backtest execution tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from django.db import transaction
from django.tasks import task
from django.utils import timezone as dj_tz

import engine.strategies  # noqa: F401
from apps.backtests.models import (
    BacktestRun,
    DecisionGate,
    MetricSet,
    MonteCarloSummary,
    RobustnessRow,
    Trade,
    WalkForwardFold,
)
from apps.reports.models import ExportFile
from engine.backtester import apply_strategy, run_backtest
from engine.data import slice_df
from engine.decision_gate import evaluate_decision_gate
from engine.indicators import add_indicators
from engine.monte_carlo import MC_SEED, N_MC_SIMS, evaluate_mc_pass, run_monte_carlo
from engine.mql5_export import Mql5SpecContext, build_mql5_spec, export_mql5_spec
from engine.registry import resolve_strategy_queue
from engine.robustness import run_robustness
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


def _update_run_params(run: BacktestRun, updates: dict) -> None:
    params = dict(run.params or {})
    params.update(updates)
    run.params = params
    run.save(update_fields=["params"])


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
    _update_run_params(run, {"WF_PASS": wf_pass})


def _persist_robustness(run: BacktestRun, result) -> None:
    RobustnessRow.objects.filter(run=run).delete()
    rows = result.param_grid + result.perturb_rows + result.cost_rows
    if rows:
        RobustnessRow.objects.bulk_create(
            [
                RobustnessRow(
                    run=run,
                    kind=row.kind,
                    label=row.label,
                    oos_return=row.oos_return,
                    oos_sharpe=row.oos_sharpe,
                    oos_dd=row.oos_dd,
                    trades=row.trades,
                    extras=row.extras,
                )
                for row in rows
            ],
            batch_size=200,
        )
    MetricSet.objects.filter(run=run, split="robustness", label="summary").delete()
    MetricSet.objects.create(
        run=run,
        split="robustness",
        label="summary",
        extras={
            "param_stable": result.param_stable,
            "perturb_stable": result.perturb_stable,
            "cost_pass": result.cost_pass,
        },
    )
    _update_run_params(
        run,
        {
            "PARAM_STABLE": result.param_stable,
            "PERTURB_STABLE": result.perturb_stable,
            "COST_PASS": result.cost_pass,
        },
    )


def _persist_monte_carlo(run: BacktestRun, mc: dict, mc_pass: bool) -> None:
    MonteCarloSummary.objects.filter(run=run).delete()
    for mode in ("shuffle", "bootstrap", "perturb", "slippage_mc"):
        data = mc.get(mode)
        if not data:
            continue
        payload = dict(data)
        hist = payload.pop("histogram", None)
        extras = {"histogram": hist} if hist else {}
        MonteCarloSummary.objects.create(
            run=run,
            mode=mode,
            n_sims=int(payload.get("n_sims") or N_MC_SIMS),
            median_final=payload.get("median_final"),
            p5_final=payload.get("p5_final"),
            p25_final=payload.get("p25_final"),
            p50_final=payload.get("p50_final"),
            p75_final=payload.get("p75_final"),
            p95_final=payload.get("p95_final"),
            median_max_dd=payload.get("median_max_dd"),
            p95_worst_dd=payload.get("p95_worst_dd"),
            prob_loss=payload.get("prob_loss"),
            prob_dd_gt_30=payload.get("prob_dd_gt_30"),
            extras=extras,
        )
    MetricSet.objects.filter(run=run, split="mc", label="summary").delete()
    boot = mc.get("bootstrap", {})
    MetricSet.objects.create(
        run=run,
        split="mc",
        label="summary",
        extras={"mc_pass": mc_pass, "bootstrap": boot},
    )
    _update_run_params(run, {"MC_PASS": mc_pass})


def _persist_decision_gate(run: BacktestRun, gate) -> None:
    DecisionGate.objects.update_or_create(
        run=run,
        defaults={
            "in_sample": gate.in_sample,
            "out_of_sample": gate.out_of_sample,
            "walk_forward": gate.walk_forward,
            "parameter_stability": gate.parameter_stability,
            "cost_stress": gate.cost_stress,
            "monte_carlo": gate.monte_carlo,
            "status": gate.status,
            "implement_mql5": gate.implement_mql5,
            "n_pass": gate.n_pass,
        },
    )
    _update_run_params(run, {"STATUS": gate.status, "implement_mql5": gate.implement_mql5})


def _persist_exports(run: BacktestRun, md_path: Path, txt_path: Path) -> None:
    ExportFile.objects.filter(run=run).delete()
    for kind, path in (("md", md_path), ("txt", txt_path)):
        ExportFile.objects.create(
            run=run,
            kind=kind,
            path=str(path),
            filename=path.name,
        )


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


def _run_deep_pipeline(
    run: BacktestRun,
    df: pd.DataFrame,
    strategy_name: str,
    params: dict,
    is_end: str,
    oos_start: str,
    is_result,
    oos_result,
    full_result,
) -> None:
    run_kwargs = {
        "initial_equity": run.initial_equity,
        "fee": run.fee,
        "slippage": run.slippage,
        "commission_per_lot": run.commission_per_lot,
        "spread": run.spread,
        "risk_pct": run.risk_pct,
        "contract_size": run.contract_size,
    }

    folds, wf_pass, wf_summary = run_walk_forward(df, strategy_name, params, **run_kwargs)
    _persist_walk_forward(run, folds, wf_pass, wf_summary)

    rob = run_robustness(
        df,
        strategy_name,
        params,
        in_sample_end=is_end,
        oos_start=oos_start,
        **run_kwargs,
    )
    _persist_robustness(run, rob)

    mc_trades = oos_result.trades if len(oos_result.trades) else full_result.trades
    mc = run_monte_carlo(
        mc_trades,
        n_sims=N_MC_SIMS,
        seed=MC_SEED,
        initial=run.initial_equity,
        contract_size=run.contract_size,
    )
    mc_pass = evaluate_mc_pass(mc, initial=run.initial_equity)
    _persist_monte_carlo(run, mc, mc_pass)

    gate = evaluate_decision_gate(
        is_metrics=is_result.metrics,
        oos_metrics=oos_result.metrics,
        wf_pass=wf_pass,
        param_stable=rob.param_stable,
        perturb_stable=rob.perturb_stable,
        cost_pass=rob.cost_pass,
        mc_pass=mc_pass,
    )
    _persist_decision_gate(run, gate)

    ts = pd.to_datetime(df["Datetime"])
    ctx = Mql5SpecContext(
        strategy_name=strategy_name,
        symbol=run.dataset.symbol,
        timeframe=run.dataset.timeframe,
        params=params,
        volume_usable=bool(run.dataset.volume_usable),
        is_metrics=is_result.metrics,
        oos_metrics=oos_result.metrics,
        gate=gate,
        mc=mc,
        initial_equity=run.initial_equity,
        fee=run.fee,
        commission_per_lot=run.commission_per_lot,
        spread=run.spread,
        slippage=run.slippage,
        risk_pct=run.risk_pct,
        contract_size=run.contract_size,
        in_sample_end=is_end,
        oos_start=oos_start,
        data_start=str(ts.min().date()),
        data_end=str(ts.max().date()),
        param_stable=rob.param_stable,
        perturb_stable=rob.perturb_stable,
        cost_pass=rob.cost_pass,
    )
    spec_text = build_mql5_spec(ctx)
    export_dir = Path(settings.MEDIA_ROOT) / "exports"
    md_path, txt_path = export_mql5_spec(
        spec_text,
        gate.status,
        export_dir,
        run.dataset.symbol,
        run.dataset.timeframe,
        strategy_name,
    )
    _persist_exports(run, md_path, txt_path)


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
                _run_deep_pipeline(
                    run,
                    df,
                    strategy_name,
                    params,
                    is_end,
                    oos_start,
                    is_result,
                    oos_result,
                    full,
                )
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
