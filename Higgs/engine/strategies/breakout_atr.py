"""Rolling high breakout long-only."""

from __future__ import annotations

import pandas as pd

from engine.registry import STRATEGY_SPECS, merge_params, register_strategy


@register_strategy
def breakout_atr(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """LONG jika Close menembus High rolling lookback (shift 1, tanpa look-ahead).
    SHORT tidak dipakai.
    Exit: SL = sl_atr * ATR, TP = tp_atr * ATR.
    Execution: next bar open.
    """
    p = merge_params(params)
    lookback = int(p.get("lookback", 20))
    out = df.copy()
    rolling_high = out["High"].rolling(lookback, min_periods=lookback).max().shift(1)
    out["signal"] = 0
    out.loc[out["Close"] > rolling_high, "signal"] = 1
    out["sl_atr"] = float(p.get("atr_sl", 1.5))
    out["tp_atr"] = float(p.get("atr_tp", 3.0))
    out.attrs["logic_spec"] = STRATEGY_SPECS["breakout_atr"]
    return out
