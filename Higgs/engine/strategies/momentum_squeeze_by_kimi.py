"""Momentum squeeze breakout long/short (Kimi)."""

from __future__ import annotations

import pandas as pd

from engine.registry import STRATEGY_SPECS, ensure_ema, merge_params, register_strategy


@register_strategy
def momentum_squeeze_by_kimi(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """Momentum Squeeze Breakout (by Kimi).
    1. Regime       : Close vs EMA200 + EMA_fast vs EMA_slow (arah tren).
    2. Volatility   : ADX > adx_th AND ADX rising (adx_14 > adx_14.shift(adx_rise)).
    3. Compression  : Donchian width / ATR < rolling median 100 (squeeze).
    4. Trigger      : Close menembus Donchian High/Low setelah squeeze (shift 1).
    5. Momentum     : RSI > rsi_long (52) Long / RSI < rsi_short (48) Short.
    6. Exit         : SL = 2.0 * ATR, TP = 4.0 * ATR.
    Execution       : next bar open, sinyal pada candle yang sudah close.
    """
    p = merge_params(params)
    ema_fast = int(p.get("ema_fast", 20))
    ema_slow = int(p.get("ema_slow", 50))
    ema_trend = int(p.get("ema_trend", 200))
    lookback = int(p.get("lookback", 20))
    adx_th = float(p.get("adx_th", 20.0))
    adx_rise = int(p.get("adx_rise", 3))
    rsi_long = float(p.get("rsi_long", 52.0))
    rsi_short = float(p.get("rsi_short", 48.0))
    sl_atr = float(p.get("atr_sl_kimi", p.get("atr_sl", 2.0)))
    tp_atr = float(p.get("atr_tp_kimi", p.get("atr_tp", 4.5)))

    out = ensure_ema(df, ema_fast)
    out = ensure_ema(out, ema_slow)
    out = ensure_ema(out, ema_trend)
    out = out.copy()

    bull = (out["Close"] > out[f"ema_{ema_trend}"]) & (out[f"ema_{ema_fast}"] > out[f"ema_{ema_slow}"])
    bear = (out["Close"] < out[f"ema_{ema_trend}"]) & (out[f"ema_{ema_fast}"] < out[f"ema_{ema_slow}"])
    adx_ok = (out["adx_14"] > adx_th) & (out["adx_14"] > out["adx_14"].shift(adx_rise))

    upper = out["High"].rolling(lookback, min_periods=lookback).max().shift(1)
    lower = out["Low"].rolling(lookback, min_periods=lookback).min().shift(1)
    width = (upper - lower) / out["atr_14"]
    squeeze = width < width.rolling(100).median()

    long_trigger = (out["Close"] > upper) & (out["rsi_14"] > rsi_long)
    short_trigger = (out["Close"] < lower) & (out["rsi_14"] < rsi_short)

    out["signal"] = 0
    out.loc[bull & adx_ok & squeeze & long_trigger, "signal"] = 1
    out.loc[bear & adx_ok & squeeze & short_trigger, "signal"] = -1
    out["sl_atr"] = sl_atr
    out["tp_atr"] = tp_atr
    out.attrs["logic_spec"] = STRATEGY_SPECS["momentum_squeeze_by_kimi"]
    return out
