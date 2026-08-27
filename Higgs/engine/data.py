"""OHLCV load, validate, and H1 cache. Do not import Django."""

from pathlib import Path

import numpy as np
import pandas as pd

VOLUME_DEAD_THRESHOLD = 0.80


def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    rename = {c: c.title() for c in df.columns}
    df = df.rename(columns=rename)
    if "Datetime" not in df.columns:
        raise ValueError(f"Datetime column missing: {list(df.columns)}")
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=False)
    df = df.sort_values("Datetime")
    return df.reset_index(drop=True)


def validate_ohlcv(df: pd.DataFrame, name: str, freq: str | None = None) -> dict:
    report = {"name": name, "rows": int(len(df))}
    report["duplicate_ts"] = int(df["Datetime"].duplicated().sum()) if "Datetime" in df.columns else int(df.index.duplicated().sum())
    ts = df["Datetime"] if "Datetime" in df.columns else pd.Series(df.index)
    report["start"] = str(ts.min())
    report["end"] = str(ts.max())
    report["tz"] = str(getattr(ts.dt, "tz", None) or "naive (assume broker server time)")

    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    invalid = (h < l) | (c > h) | (c < l) | (o > h) | (o < l) | ~np.isfinite(c)
    report["ohlc_invalid"] = int(invalid.sum())
    report["volume_zero_pct"] = float((df["Volume"] <= 0).mean())
    report["volume_dead"] = report["volume_zero_pct"] >= VOLUME_DEAD_THRESHOLD

    if freq:
        expected = pd.date_range(ts.min(), ts.max(), freq=freq)
        report["expected_bars"] = int(len(expected))
        report["missing_bars"] = int(len(expected.difference(pd.DatetimeIndex(ts))))
    else:
        report["missing_bars"] = None

    ret = c.pct_change().abs()
    report["gap_gt_2pct"] = int((ret > 0.02).sum())
    report["max_abs_return"] = float(ret.max()) if len(ret) else 0.0
    return report


def resample_h1(df: pd.DataFrame) -> pd.DataFrame:
    x = df.set_index("Datetime")
    h1 = x.resample("1h").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    h1 = h1.dropna(subset=["Open", "High", "Low", "Close"])
    h1 = h1.reset_index()
    return h1


def clean_m1(df: pd.DataFrame) -> pd.DataFrame:
    out = df.drop_duplicates("Datetime", keep="first")
    invalid_mask = (
        (out["High"] < out["Low"])
        | (out["Close"] > out["High"])
        | (out["Close"] < out["Low"])
        | (out["Open"] > out["High"])
        | (out["Open"] < out["Low"])
    )
    if invalid_mask.any():
        out = out.loc[~invalid_mask].copy()
    return out.reset_index(drop=True)


def build_h1_cache(raw_path, cache_path) -> dict:
    raw_path = Path(raw_path)
    cache_path = Path(cache_path)
    raw = load_raw(raw_path)
    m1_report = validate_ohlcv(raw, "M1")
    cleaned = clean_m1(raw)
    h1 = resample_h1(cleaned)
    h1_report = validate_ohlcv(h1, "H1", freq="1h")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    h1.to_parquet(cache_path, engine="pyarrow", index=False)
    start_ts = h1["Datetime"].iloc[0] if len(h1) else None
    end_ts = h1["Datetime"].iloc[-1] if len(h1) else None
    return {
        "rows_m1": m1_report["rows"],
        "rows_h1": int(len(h1)),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "validation": {"m1": m1_report, "h1": h1_report},
        "volume_usable": not h1_report["volume_dead"],
    }
