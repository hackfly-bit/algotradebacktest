"""Next-bar backtester. Do not import Django. Strategy-agnostic."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.metrics import INITIAL_EQUITY, calculate_metrics
from engine.registry import get_strategy

FEE = 0.0
COMMISSION_PER_LOT = 7.0
SPREAD = 0.25
SLIPPAGE = 0.0001
RISK_PCT = 0.01
CONTRACT_SIZE = 100.0
MAX_POSITIONS = 1


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series
    trades: pd.DataFrame
    metrics: dict
    params: dict = field(default_factory=dict)
    fee: float = FEE
    slippage: float = SLIPPAGE
    commission_per_lot: float = COMMISSION_PER_LOT
    spread: float = SPREAD


def run_backtest(
    signal_df: pd.DataFrame,
    initial_equity: float = INITIAL_EQUITY,
    fee: float = FEE,
    slippage: float = SLIPPAGE,
    commission_per_lot: float = COMMISSION_PER_LOT,
    spread: float = SPREAD,
    risk_pct: float = RISK_PCT,
    contract_size: float = CONTRACT_SIZE,
    name: str = "backtest",
    params: dict | None = None,
) -> BacktestResult:
    need = {"Open", "High", "Low", "Close", "ATR", "signal", "sl_atr", "tp_atr"}
    missing = need - set(signal_df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    x = signal_df.sort_values("Datetime").reset_index(drop=True)
    n = len(x)
    opens = x["Open"].to_numpy(float)
    highs = x["High"].to_numpy(float)
    lows = x["Low"].to_numpy(float)
    closes = x["Close"].to_numpy(float)
    atrs = x["ATR"].to_numpy(float)
    signals = x["signal"].to_numpy(float)
    sl_atrs = x["sl_atr"].to_numpy(float)
    tp_atrs = x["tp_atr"].to_numpy(float)
    times = pd.to_datetime(x["Datetime"]).to_numpy()

    equity_val = float(initial_equity)
    equity_curve = np.full(n, np.nan)
    equity_curve[0] = equity_val
    in_pos = False
    direction = 0
    entry_price = sl = tp = lots = 0.0
    entry_i = 0
    trades: list[dict] = []

    for i in range(1, n):
        if equity_val <= 0:
            equity_curve[i:] = 0.0
            break

        if in_pos:
            hit_sl = (direction == 1 and lows[i] <= sl) or (direction == -1 and highs[i] >= sl)
            hit_tp = (direction == 1 and highs[i] >= tp) or (direction == -1 and lows[i] <= tp)
            exit_price = None
            reason = None
            if hit_sl and hit_tp:
                exit_price, reason = sl, "SL"
            elif hit_sl:
                exit_price, reason = sl, "SL"
            elif hit_tp:
                exit_price, reason = tp, "TP"

            if exit_price is not None:
                if direction == 1:
                    exit_price = exit_price * (1.0 - slippage) - spread / 2.0
                else:
                    exit_price = exit_price * (1.0 + slippage) + spread / 2.0
                pnl = direction * (exit_price - entry_price) * lots * contract_size
                pnl -= fee * lots * contract_size * (entry_price + exit_price)
                pnl -= commission_per_lot * lots
                equity_val += pnl
                trades.append(
                    {
                        "entry_time": times[entry_i],
                        "exit_time": times[i],
                        "direction": direction,
                        "entry": entry_price,
                        "exit": exit_price,
                        "lots": lots,
                        "pnl": pnl,
                        "reason": reason,
                        "return_pct": direction * (exit_price / entry_price - 1.0),
                    }
                )
                in_pos = False

        equity_curve[i] = max(equity_val, 0.0)

        if equity_val <= 0:
            continue

        if (not in_pos) and signals[i - 1] != 0 and np.isfinite(atrs[i - 1]) and atrs[i - 1] > 0:
            direction = int(np.sign(signals[i - 1]))
            raw_entry = opens[i]
            if not np.isfinite(raw_entry):
                continue
            if direction == 1:
                entry_price = raw_entry * (1.0 + slippage) + spread / 2.0
            else:
                entry_price = raw_entry * (1.0 - slippage) - spread / 2.0
            sl_dist = float(sl_atrs[i - 1] * atrs[i - 1])
            tp_dist = float(tp_atrs[i - 1] * atrs[i - 1])
            if sl_dist <= 0 or not np.isfinite(sl_dist):
                continue
            if direction == 1:
                sl, tp = entry_price - sl_dist, entry_price + tp_dist
            else:
                sl, tp = entry_price + sl_dist, entry_price - tp_dist
            lots = (equity_val * risk_pct) / (contract_size * sl_dist)
            if lots <= 0 or not np.isfinite(lots):
                continue
            in_pos = True
            entry_i = i

    if in_pos:
        exit_price = closes[-1] * (1.0 - slippage * direction) - direction * spread / 2.0
        pnl = direction * (exit_price - entry_price) * lots * contract_size
        pnl -= fee * lots * contract_size * (entry_price + exit_price)
        pnl -= commission_per_lot * lots
        equity_val += pnl
        equity_curve[-1] = equity_val
        trades.append(
            {
                "entry_time": times[entry_i],
                "exit_time": times[-1],
                "direction": direction,
                "entry": entry_price,
                "exit": exit_price,
                "lots": lots,
                "pnl": pnl,
                "reason": "EOD",
                "return_pct": direction * (exit_price / entry_price - 1.0),
            }
        )

    eq = pd.Series(equity_curve, index=pd.to_datetime(times), name="equity").ffill()
    trade_df = pd.DataFrame(trades)
    metrics = calculate_metrics(eq, trade_df, initial_equity)
    metrics["fee"] = fee
    metrics["slippage"] = slippage
    metrics["commission_per_lot"] = commission_per_lot
    metrics["spread"] = spread
    return BacktestResult(
        name=name,
        equity=eq,
        trades=trade_df,
        metrics=metrics,
        params=params or {},
        fee=fee,
        slippage=slippage,
        commission_per_lot=commission_per_lot,
        spread=spread,
    )


def apply_strategy(
    df_ind: pd.DataFrame,
    name: str,
    params: dict | None = None,
) -> pd.DataFrame:
    return get_strategy(name)(df_ind, params)
