"""Technical indicators. Do not import Django. Do not write signal columns."""

from __future__ import annotations

import numpy as np
import pandas as pd

EMA_PERIODS = [10, 15, 18, 19, 20, 21, 22, 25, 30, 48, 49, 50, 51, 52, 200]


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    return pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    up = df["High"].diff()
    down = -df["Low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr_ = atr(df, period)
    plus_di = 100.0 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_
    minus_di = 100.0 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def add_indicators(df: pd.DataFrame, ema_periods: list[int] | None = None) -> pd.DataFrame:
    out = df.copy()
    periods = ema_periods or EMA_PERIODS
    for p in periods:
        out[f"ema_{p}"] = out["Close"].ewm(span=p, adjust=False).mean()
    out["rsi_14"] = rsi(out["Close"], 14)
    out["atr_14"] = atr(out, 14)
    out["ATR"] = out["atr_14"]
    out["adx_14"] = adx(out, 14)
    out["volume_ma_20"] = out["Volume"].rolling(20, min_periods=20).mean()
    out["range"] = out["High"] - out["Low"]
    return out
