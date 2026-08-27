"""Thin Django wrapper around engine.data.build_h1_cache."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from apps.marketdata.models import Dataset
from engine.data import build_h1_cache


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    item = getattr(value, "item", None)
    if callable(item):
        return _json_ready(item())
    return value


def _aware(ts):
    if ts is None:
        return None
    to_pydatetime = getattr(ts, "to_pydatetime", None)
    if callable(to_pydatetime):
        ts = to_pydatetime()
    if not isinstance(ts, datetime):
        return None
    if timezone.is_naive(ts):
        return timezone.make_aware(ts, timezone.UTC)
    return ts


def ingest_dataset(raw_path, *, source_name=None, symbol="XAUUSD", timeframe="1H") -> Dataset:
    raw_path = Path(raw_path).expanduser().resolve()
    if not raw_path.is_file():
        raise FileNotFoundError(f"CSV tidak ditemukan: {raw_path}")

    cache_dir = Path(settings.MEDIA_ROOT) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{symbol}_{timeframe}_{uuid4().hex[:10]}.parquet"

    meta = build_h1_cache(raw_path, cache_path)
    return Dataset.objects.create(
        symbol=symbol,
        timeframe=timeframe,
        source_name=source_name or raw_path.name,
        raw_path=str(raw_path),
        cache_path=str(cache_path),
        rows_m1=meta["rows_m1"],
        rows_h1=meta["rows_h1"],
        start_ts=_aware(meta["start_ts"]),
        end_ts=_aware(meta["end_ts"]),
        validation=_json_ready(meta["validation"]),
        volume_usable=bool(meta["volume_usable"]),
    )
