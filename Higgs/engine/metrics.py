"""Performance metrics from equity curve and trades. Do not import Django."""

from __future__ import annotations

import numpy as np
import pandas as pd

INITIAL_EQUITY = 10_000.0


def max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak == 0, np.nan, peak)
    return float(np.nanmin(dd)) if len(dd) else 0.0


def calculate_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    initial: float = INITIAL_EQUITY,
) -> dict:
    eq = equity.dropna()
    if eq.empty:
        return {"error": "empty equity"}
    if not isinstance(eq.index, pd.DatetimeIndex):
        eq.index = pd.to_datetime(eq.index)
    eq = eq[~eq.index.duplicated(keep="last")].sort_index()
    final = float(eq.iloc[-1])
    total_return = final / initial - 1.0
    dt = (eq.index[-1] - eq.index[0]).days
    years = max(dt / 365.25, 1e-9)
    cagr = (final / initial) ** (1 / years) - 1.0 if final > 0 else -1.0
    daily = eq.resample("1D").last().ffill().dropna()
    rets = daily.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if len(rets) and rets.std() > 0 else 0.0
    downside = rets[rets < 0]
    sortino = float(rets.mean() / downside.std() * np.sqrt(252)) if len(downside) and downside.std() > 0 else 0.0
    max_dd = max_drawdown(eq.to_numpy(dtype=float))
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    n = int(len(trades))
    if n:
        wins = trades.loc[trades["pnl"] > 0, "pnl"]
        losses = trades.loc[trades["pnl"] < 0, "pnl"]
        win_rate = float((trades["pnl"] > 0).mean())
        avg_win = float(wins.mean()) if len(wins) else 0.0
        avg_loss = float(losses.mean()) if len(losses) else 0.0
        gross_win = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(losses.abs().sum()) if len(losses) else 0.0
        profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf
        expectancy = float(trades["pnl"].mean())
        signs = np.sign(trades["pnl"].to_numpy())
        worst = 0
        cur = 0
        for s in signs:
            if s < 0:
                cur += 1
                worst = max(worst, cur)
            else:
                cur = 0
        recovery = total_return / abs(max_dd) if max_dd < 0 else 0.0
    else:
        win_rate = avg_win = avg_loss = expectancy = recovery = 0.0
        profit_factor = 0.0
        worst = 0

    return {
        "initial_equity": initial,
        "final_equity": final,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "profit_factor": float(profit_factor) if np.isfinite(profit_factor) else 999.0,
        "expectancy": expectancy,
        "average_win": avg_win,
        "average_loss": avg_loss,
        "trades": n,
        "average_trade": float(trades["pnl"].mean()) if n else 0.0,
        "longest_losing_streak": int(worst),
        "recovery_factor": recovery,
        "years": years,
    }
