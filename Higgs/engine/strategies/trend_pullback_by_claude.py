"""Trend pullback long-only (Claude)."""

from __future__ import annotations

import pandas as pd

from engine.registry import STRATEGY_SPECS, ensure_ema, merge_params, register_strategy


@register_strategy
def trend_pullback_by_claude(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """Trend-pullback momentum (by Claude).
    Regime : Close > EMA200 AND EMA200 naik (vs 5 bar lalu) -> hanya ikut uptrend besar.
    Kualitas: ADX > adx_min (trend nyata, bukan ranging) AND EMA_fast > EMA_slow.
    Trigger : pullback -- Low menyentuh/di bawah EMA_fast dalam pull_bars bar terakhir,
              lalu Close kembali di atas EMA_fast dan RSI > 50 (momentum resume).
    SHORT tidak dipakai.
    Exit    : SL = sl_atr * ATR (2.0), TP = tp_atr * ATR (4.0) -> minimal 2R.
    Execution: next bar open, sinyal pada candle yang sudah close.
    """
    p = merge_params(params)
    ema_fast = int(p.get("ema_fast", 20))
    ema_slow = int(p.get("ema_slow", 50))
    adx_min = float(p.get("adx_min", 20.0))
    pull_bars = int(p.get("pull_bars", 3))
    slope_bars = int(p.get("slope_bars", 5))

    out = ensure_ema(df, ema_fast)
    out = ensure_ema(out, ema_slow)
    out = ensure_ema(out, 200)
    out = out.copy()

    regime = (out["Close"] > out["ema_200"]) & (out["ema_200"] > out["ema_200"].shift(slope_bars))
    quality = (out["adx_14"] > adx_min) & (out[f"ema_{ema_fast}"] > out[f"ema_{ema_slow}"])
    pulled_back = (out["Low"] <= out[f"ema_{ema_fast}"]).rolling(pull_bars, min_periods=1).max().astype(bool)
    resume = (out["Close"] > out[f"ema_{ema_fast}"]) & (out["rsi_14"] > 50)

    out["signal"] = 0
    out.loc[regime & quality & pulled_back & resume, "signal"] = 1
    out["sl_atr"] = float(p.get("atr_sl_claude", 2.0))
    out["tp_atr"] = float(p.get("atr_tp_claude", 4.0))
    out.attrs["logic_spec"] = STRATEGY_SPECS["trend_pullback_by_claude"]
    return out
