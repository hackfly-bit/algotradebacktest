"""EMA / RSI / volume long-only momentum."""

from __future__ import annotations

import pandas as pd

from engine.registry import STRATEGY_SPECS, ensure_ema, merge_params, register_strategy


@register_strategy
def ema_rsi_volume(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """LONG jika EMA_fast > EMA_slow AND RSI > threshold AND Volume > Volume_MA.
    Jika data volume mati (hampir semua 0), filter volume diabaikan.
    SHORT tidak dipakai.
    Exit: SL = sl_atr * ATR, TP = tp_atr * ATR.
    Execution: next bar open, sinyal pada candle yang sudah close.
    """
    p = merge_params(params)
    ema_fast = int(p.get("ema_fast", 20))
    ema_slow = int(p.get("ema_slow", 50))
    rsi_th = float(p.get("rsi_threshold", 50))
    vol_ma = int(p.get("volume_ma", 20))
    use_vol = bool(p.get("use_volume_filter", True)) and bool(p.get("volume_usable", True))
    out = ensure_ema(df, ema_fast)
    out = ensure_ema(out, ema_slow)
    vol_col = f"volume_ma_{vol_ma}"
    if vol_col not in out.columns:
        out = out.copy()
        out[vol_col] = out["Volume"].rolling(vol_ma, min_periods=vol_ma).mean()

    long_cond = (out[f"ema_{ema_fast}"] > out[f"ema_{ema_slow}"]) & (out["rsi_14"] > rsi_th)
    if use_vol:
        long_cond = long_cond & (out["Volume"] > out[vol_col])

    out = out.copy()
    out["signal"] = 0
    out.loc[long_cond, "signal"] = 1
    out["sl_atr"] = float(p.get("atr_sl", 1.5))
    out["tp_atr"] = float(p.get("atr_tp", 3.0))
    out.attrs["volume_filter_applied"] = use_vol
    out.attrs["logic_spec"] = STRATEGY_SPECS["ema_rsi_volume"]
    return out
