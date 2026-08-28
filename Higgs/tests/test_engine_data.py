"""Synthetic tests for engine.data. Do not load the parent 5.89M-bar CSV."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engine.data import (
    VOLUME_DEAD_THRESHOLD,
    build_h1_cache,
    clean_m1,
    load_raw,
    resample_h1,
    validate_ohlcv,
)

ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPORT_KEYS_BASE = {
    "name",
    "rows",
    "duplicate_ts",
    "start",
    "end",
    "tz",
    "ohlc_invalid",
    "volume_zero_pct",
    "volume_dead",
    "missing_bars",
    "gap_gt_2pct",
    "max_abs_return",
}


def _m1_hour(start="2024-01-02 10:00:00", n=60, volume=0.0, close_base=2000.0) -> pd.DataFrame:
    index = pd.date_range(start, periods=n, freq="min")
    closes = close_base + pd.Series(range(n), dtype="float64") * 0.01
    return pd.DataFrame(
        {
            "Datetime": index,
            "Open": closes,
            "High": closes + 0.1,
            "Low": closes - 0.1,
            "Close": closes,
            "Volume": volume,
        }
    )


def _write_csv(df: pd.DataFrame, path: Path, title_case: bool = True) -> None:
    out = df.copy()
    if not title_case:
        out.columns = [c.lower() for c in out.columns]
    out.to_csv(path, index=False)


class EngineDataTests(unittest.TestCase):
    def test_engine_modules_do_not_import_django(self):
        for rel in (
            "engine/__init__.py",
            "engine/data.py",
            "engine/indicators.py",
            "engine/registry.py",
        ):
            tree = ast.parse((ENGINE_ROOT / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    self.assertNotEqual(name.split(".", 1)[0], "django", rel)

    def test_validate_report_keys_without_freq(self):
        report = validate_ohlcv(_m1_hour(), "M1")
        self.assertEqual(set(report) - {"expected_bars"}, REPORT_KEYS_BASE)
        self.assertNotIn("expected_bars", report)
        self.assertIsNone(report["missing_bars"])
        self.assertEqual(report["name"], "M1")
        self.assertEqual(report["rows"], 60)

    def test_validate_report_keys_with_freq(self):
        h1 = resample_h1(_m1_hour())
        report = validate_ohlcv(h1, "H1", freq="1h")
        self.assertTrue(REPORT_KEYS_BASE.issubset(report))
        self.assertIn("expected_bars", report)
        self.assertIsInstance(report["expected_bars"], int)
        self.assertIsInstance(report["missing_bars"], int)

    def test_resample_sixty_m1_to_one_h1(self):
        h1 = resample_h1(_m1_hour())
        self.assertEqual(len(h1), 1)
        self.assertEqual(h1.loc[0, "Open"], 2000.0)
        self.assertEqual(h1.loc[0, "Close"], 2000.0 + 59 * 0.01)
        self.assertAlmostEqual(float(h1.loc[0, "High"]), 2000.0 + 59 * 0.01 + 0.1)
        self.assertAlmostEqual(float(h1.loc[0, "Low"]), 2000.0 - 0.1)

    def test_volume_dead_when_volume_zero(self):
        self.assertEqual(VOLUME_DEAD_THRESHOLD, 0.80)
        report = validate_ohlcv(_m1_hour(volume=0), "M1")
        self.assertEqual(report["volume_zero_pct"], 1.0)
        self.assertTrue(report["volume_dead"])

    def test_volume_not_dead_when_volume_positive(self):
        report = validate_ohlcv(_m1_hour(volume=10), "M1")
        self.assertEqual(report["volume_zero_pct"], 0.0)
        self.assertFalse(report["volume_dead"])

    def test_clean_m1_drops_duplicate_datetime_keep_first(self):
        base = _m1_hour(n=2)
        dup = base.iloc[[0]].copy()
        dup.loc[dup.index[0], "Close"] = 9999.0
        mixed = pd.concat([base, dup], ignore_index=True)
        cleaned = clean_m1(mixed)
        self.assertEqual(len(cleaned), 2)
        first = cleaned.loc[cleaned["Datetime"] == base.loc[0, "Datetime"]].iloc[0]
        self.assertEqual(first["Close"], base.loc[0, "Close"])

    def test_clean_m1_drops_invalid_ohlc(self):
        df = _m1_hour(n=3)
        df.loc[1, "High"] = df.loc[1, "Low"] - 1
        cleaned = clean_m1(df)
        self.assertEqual(len(cleaned), 2)

    def test_load_raw_strips_and_title_cases_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.csv"
            _write_csv(_m1_hour(n=3), path, title_case=False)
            loaded = load_raw(path)
            self.assertEqual(list(loaded.columns)[:6], ["Datetime", "Open", "High", "Low", "Close", "Volume"])
            self.assertTrue(pd.api.types.is_datetime64_any_dtype(loaded["Datetime"]))

    def test_build_h1_cache_writes_parquet_and_volume_usable_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "raw.csv"
            cache_path = Path(tmp) / "cache" / "h1.parquet"
            _write_csv(_m1_hour(n=60, volume=0), raw_path)
            meta = build_h1_cache(raw_path, cache_path)
            self.assertTrue(cache_path.is_file())
            self.assertEqual(meta["rows_m1"], 60)
            self.assertEqual(meta["rows_h1"], 1)
            self.assertFalse(meta["volume_usable"])
            self.assertIn("m1", meta["validation"])
            self.assertIn("h1", meta["validation"])
            cached = pd.read_parquet(cache_path)
            self.assertEqual(len(cached), 1)
            self.assertTrue(meta["validation"]["h1"]["volume_dead"])


if __name__ == "__main__":
    unittest.main()
