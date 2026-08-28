"""Donchian trend breakout long/short (Gemini)."""

from __future__ import annotations

import pandas as pd

from engine.registry import STRATEGY_SPECS, ensure_ema, merge_params, register_strategy


@register_strategy
def trend_breakout_by_gemini(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """Trend Momentum Donchian Breakout (by Gemini).
    1. Macro Regime   : Close > EMA200 (Long) / Close < EMA200 (Short).
    2. Trend Alignment: EMA_fast > EMA_slow (Long) / EMA_fast < EMA_slow (Short).
    3. Volatility/ADX : ADX > adx_th (20) — skip ranging / choppy market.
    4. Momentum RSI   : RSI > rsi_th (50) Long / RSI < (100 - rsi_th) Short.
    5. Trigger        : Donchian lookback High/Low breakout (shift 1, no look-ahead).
    6. Exit           : SL = 2.0 * ATR, TP = 4.0 * ATR (1:2 R:R).
    Execution         : next bar open, sinyal pada candle yang sudah close.
    """
    p = merge_params(params)
    ema_fast = int(p.get("ema_fast", 20))
    ema_slow = int(p.get("ema_slow", 50))
    ema_trend = int(p.get("ema_trend", 200))
    lookback = int(p.get("lookback", 24))
    adx_th = float(p.get("adx_th", 20.0))
    rsi_th = float(p.get("rsi_th", p.get("rsi_threshold", 50.0)))
    sl_atr = float(p.get("atr_sl_gemini", p.get("atr_sl", 2.0)))
    tp_atr = float(p.get("atr_tp_gemini", p.get("atr_tp", 4.0)))
    allow_short = bool(p.get("allow_short", True))

    out = ensure_ema(df, ema_fast)
    out = ensure_ema(out, ema_slow)
    out = ensure_ema(out, ema_trend)
    out = out.copy()

    upper = out["High"].rolling(lookback, min_periods=lookback).max().shift(1)
    lower = out["Low"].rolling(lookback, min_periods=lookback).min().shift(1)
    adx_ok = out["adx_14"] > adx_th

    long_cond = (
        (out["Close"] > upper)
        & (out["Close"] > out[f"ema_{ema_trend}"])
        & (out[f"ema_{ema_fast}"] > out[f"ema_{ema_slow}"])
        & adx_ok
        & (out["rsi_14"] > rsi_th)
    )
    out["signal"] = 0
    out.loc[long_cond, "signal"] = 1

    if allow_short:
        short_cond = (
            (out["Close"] < lower)
            & (out["Close"] < out[f"ema_{ema_trend}"])
            & (out[f"ema_{ema_fast}"] < out[f"ema_{ema_slow}"])
            & adx_ok
            & (out["rsi_14"] < (100.0 - rsi_th))
        )
        out.loc[short_cond, "signal"] = -1

    out["sl_atr"] = sl_atr
    out["tp_atr"] = tp_atr
    out.attrs["logic_spec"] = STRATEGY_SPECS["trend_breakout_by_gemini"]
    return out
