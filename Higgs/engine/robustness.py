"""Parameter and cost robustness checks. Do not import Django."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.backtester import apply_strategy, run_backtest
from engine.data import slice_df

EMA_FAST_GRID = (10, 15, 20, 25, 30)
PERTURB_PAIRS = ((18, 48), (19, 49), (20, 50), (21, 51), (22, 52))
COST_MULTIPLIERS = (1, 2, 3)


@dataclass
class RobustnessRowResult:
    kind: str
    label: str
    oos_return: float
    oos_sharpe: float
    oos_dd: float
    trades: int
    extras: dict = field(default_factory=dict)


@dataclass
class RobustnessResult:
    param_grid: list[RobustnessRowResult]
    perturb_rows: list[RobustnessRowResult]
    cost_rows: list[RobustnessRowResult]
    param_stable: bool
    perturb_stable: bool
    cost_pass: bool


def _backtest_slice(
    df_ind: pd.DataFrame,
    strategy_name: str,
    params: dict,
    *,
    start: str | None = None,
    end: str | None = None,
    name: str = "run",
    initial_equity: float = 10_000.0,
    fee: float = 0.0,
    slippage: float = 0.0001,
    commission_per_lot: float = 7.0,
    spread: float = 0.25,
    risk_pct: float = 0.01,
    contract_size: float = 100.0,
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


def _row_from_result(kind: str, label: str, result, *, extras: dict | None = None) -> RobustnessRowResult:
    m = result.metrics
    return RobustnessRowResult(
        kind=kind,
        label=label,
        oos_return=float(m.get("total_return") or 0.0),
        oos_sharpe=float(m.get("sharpe") or 0.0),
        oos_dd=float(m.get("max_drawdown") or 0.0),
        trades=int(m.get("trades") or 0),
        extras=extras or {},
    )


def run_robustness(
    df_ind: pd.DataFrame,
    strategy_name: str,
    base_params: dict,
    *,
    in_sample_end: str,
    oos_start: str,
    initial_equity: float = 10_000.0,
    fee: float = 0.0,
    slippage: float = 0.0001,
    commission_per_lot: float = 7.0,
    spread: float = 0.25,
    risk_pct: float = 0.01,
    contract_size: float = 100.0,
) -> RobustnessResult:
    run_kwargs = {
        "initial_equity": initial_equity,
        "fee": fee,
        "slippage": slippage,
        "commission_per_lot": commission_per_lot,
        "spread": spread,
        "risk_pct": risk_pct,
        "contract_size": contract_size,
    }

    grid_rows: list[RobustnessRowResult] = []
    sharpes: list[float] = []
    for fast in EMA_FAST_GRID:
        p = {**base_params, "ema_fast": fast}
        r = _backtest_slice(
            df_ind,
            strategy_name,
            p,
            end=in_sample_end,
            name=f"ema_fast_{fast}",
            **run_kwargs,
        )
        grid_rows.append(_row_from_result("param_grid", f"ema_fast_{fast}", r, extras={"ema_fast": fast}))
        sharpes.append(float(r.metrics.get("sharpe") or 0.0))
    arr = np.asarray(sharpes, dtype=float)
    param_stable = bool(np.isfinite(arr).all() and (arr > 0).sum() >= 4)

    perturb_rows: list[RobustnessRowResult] = []
    for fast, slow in PERTURB_PAIRS:
        p = {**base_params, "ema_fast": fast, "ema_slow": slow}
        r = _backtest_slice(
            df_ind,
            strategy_name,
            p,
            start=oos_start,
            name=f"{fast}/{slow}",
            **run_kwargs,
        )
        perturb_rows.append(_row_from_result("ema_perturb", f"{fast}/{slow}", r))

    perturb_stable = bool(perturb_rows and all(row.oos_return > 0 for row in perturb_rows))

    cost_rows: list[RobustnessRowResult] = []
    for mult in COST_MULTIPLIERS:
        r = _backtest_slice(
            df_ind,
            strategy_name,
            base_params,
            start=oos_start,
            name=f"cost_x{mult}",
            fee=fee * mult,
            slippage=slippage * mult,
            commission_per_lot=commission_per_lot * mult,
            spread=spread * mult,
            **{k: v for k, v in run_kwargs.items() if k not in {"fee", "slippage", "commission_per_lot", "spread"}},
        )
        cost_rows.append(
            _row_from_result(
                "cost_stress",
                f"fee_x{mult}",
                r,
                extras={"cost_mult": mult},
            )
        )

    cost_pass = False
    for row in cost_rows:
        if row.extras.get("cost_mult") == 2:
            cost_pass = row.oos_return > 0
            break

    return RobustnessResult(
        param_grid=grid_rows,
        perturb_rows=perturb_rows,
        cost_rows=cost_rows,
        param_stable=param_stable,
        perturb_stable=perturb_stable,
        cost_pass=cost_pass,
    )
