"""Walk-forward analysis. Do not import Django."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.backtester import apply_strategy, run_backtest
from engine.data import slice_df

EMA_FAST_GRID = (15, 20, 25)


def walk_forward_windows(
    start: str,
    end: str,
    train_years: int = 3,
    test_years: int = 1,
    step_years: int = 1,
) -> list[tuple[str, str, str, str]]:
    """Return (dev_start, dev_end, val_start, val_end) date strings."""
    windows: list[tuple[str, str, str, str]] = []
    t0 = pd.Timestamp(start)
    t_end = pd.Timestamp(end)
    while True:
        dev_end = t0 + pd.DateOffset(years=train_years) - pd.Timedelta(days=1)
        val_start = dev_end + pd.Timedelta(days=1)
        val_end = val_start + pd.DateOffset(years=test_years) - pd.Timedelta(days=1)
        if val_end > t_end:
            break
        windows.append(
            (
                str(t0.date()),
                str(dev_end.date()),
                str(val_start.date()),
                str(val_end.date()),
            )
        )
        t0 = t0 + pd.DateOffset(years=step_years)
    return windows


@dataclass
class WalkForwardFoldResult:
    dev_start: str
    dev_end: str
    val_start: str
    val_end: str
    chosen_ema_fast: int
    dev_sharpe: float
    val_sharpe: float
    val_return: float
    val_max_dd: float
    val_trades: int
    positive_sharpe: bool


def evaluate_wf_pass(folds: list[WalkForwardFoldResult]) -> tuple[bool, dict]:
    if not folds:
        return False, {
            "wf_pass": False,
            "median_val_return": None,
            "pct_positive_sharpe": None,
            "n_folds": 0,
        }
    sharpes = [f.val_sharpe for f in folds]
    returns = [f.val_return for f in folds]
    pct_pos = sum(1 for s in sharpes if s > 0) / len(sharpes)
    median_ret = float(pd.Series(returns).median())
    wf_pass = pct_pos >= 0.5 and median_ret > 0
    return wf_pass, {
        "wf_pass": wf_pass,
        "median_val_return": median_ret,
        "pct_positive_sharpe": pct_pos,
        "n_folds": len(folds),
    }


def _backtest_window(
    df_ind: pd.DataFrame,
    strategy_name: str,
    params: dict,
    start: str | None,
    end: str | None,
    name: str,
    *,
    initial_equity: float,
    fee: float,
    slippage: float,
    commission_per_lot: float,
    spread: float,
    risk_pct: float,
    contract_size: float,
):
    sl = slice_df(df_ind, start=start, end=end)
    signals = apply_strategy(sl, strategy_name, params)
    return run_backtest(
        signals,
        initial_equity=initial_equity,
        fee=fee,
        slippage=slippage,
        commission_per_lot=commission_per_lot,
        spread=spread,
        risk_pct=risk_pct,
        contract_size=contract_size,
        name=name,
        params=params,
    )


def run_walk_forward(
    df_ind: pd.DataFrame,
    strategy_name: str,
    base_params: dict,
    *,
    initial_equity: float = 10_000.0,
    fee: float = 0.0,
    slippage: float = 0.0001,
    commission_per_lot: float = 7.0,
    spread: float = 0.25,
    risk_pct: float = 0.01,
    contract_size: float = 100.0,
    wf_start: str | None = None,
    wf_end: str | None = None,
    train_years: int = 3,
    test_years: int = 1,
    step_years: int = 1,
    ema_fast_grid: tuple[int, ...] = EMA_FAST_GRID,
) -> tuple[list[WalkForwardFoldResult], bool, dict]:
    ts = pd.to_datetime(df_ind["Datetime"])
    start = wf_start or str(ts.min().date())
    end = wf_end or str(ts.max().date())
    windows = walk_forward_windows(start, end, train_years, test_years, step_years)

    run_kwargs = {
        "initial_equity": initial_equity,
        "fee": fee,
        "slippage": slippage,
        "commission_per_lot": commission_per_lot,
        "spread": spread,
        "risk_pct": risk_pct,
        "contract_size": contract_size,
    }

    folds: list[WalkForwardFoldResult] = []
    for dev_s, dev_e, val_s, val_e in windows:
        best: tuple[float, dict, dict] | None = None
        for fast in ema_fast_grid:
            p = {**base_params, "ema_fast": fast}
            dev = _backtest_window(
                df_ind,
                strategy_name,
                p,
                dev_s,
                dev_e,
                "dev",
                **run_kwargs,
            )
            score = dev.metrics.get("sharpe")
            if score is None or (isinstance(score, float) and pd.isna(score)):
                continue
            if best is None or score > best[0]:
                best = (float(score), p, dev.metrics)
        if best is None:
            continue
        val = _backtest_window(
            df_ind,
            strategy_name,
            best[1],
            val_s,
            val_e,
            "val",
            **run_kwargs,
        )
        val_sharpe = float(val.metrics.get("sharpe") or 0.0)
        folds.append(
            WalkForwardFoldResult(
                dev_start=dev_s,
                dev_end=dev_e,
                val_start=val_s,
                val_end=val_e,
                chosen_ema_fast=int(best[1]["ema_fast"]),
                dev_sharpe=float(best[0]),
                val_sharpe=val_sharpe,
                val_return=float(val.metrics.get("total_return") or 0.0),
                val_max_dd=float(val.metrics.get("max_drawdown") or 0.0),
                val_trades=int(val.metrics.get("trades") or 0),
                positive_sharpe=val_sharpe > 0,
            )
        )

    wf_pass, summary = evaluate_wf_pass(folds)
    return folds, wf_pass, summary
