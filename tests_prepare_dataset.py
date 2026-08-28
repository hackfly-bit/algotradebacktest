"""Unit tests for prepare_dataset merge contract (no network)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import prepare_dataset as prep


class PrepareDatasetTests(unittest.TestCase):
    def test_read_year_column_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "y.csv"
            path.write_text(
                "2024.01.02,10:00,2000.0,2001.0,1999.0,2000.5,0\n"
                "2024.01.02,10:01,2000.5,2002.0,2000.0,2001.0,1\n",
                encoding="utf-8",
            )
            df = prep._read_year(path)
            self.assertEqual(list(df.columns), ["Datetime", "Open", "High", "Low", "Close", "Volume"])
            self.assertEqual(len(df), 2)
            self.assertEqual(str(df.loc[0, "Datetime"]), "2024-01-02 10:00:00")

    def test_prepare_skips_when_merged_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merged = root / prep.MERGED_NAME
            merged.write_text("Datetime,Open,High,Low,Close,Volume\n", encoding="utf-8")
            with mock.patch.object(prep, "REPO_ROOT", root), mock.patch.object(prep, "MERGED_PATH", merged), mock.patch.object(
                prep, "DATASET_DIR", root / "dataset"
            ):
                out = prep.prepare_dataset()
                self.assertEqual(out, merged)

    def test_prepare_merge_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset"
            dataset.mkdir()
            merged = root / prep.MERGED_NAME

            def fake_download(name: str, dest: Path) -> None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                # unique timestamps per file name hash
                stamp = abs(hash(name)) % 10_000
                dest.write_text(
                    f"2024.01.02,{10 + stamp % 5:02d}:00,2000,2001,1999,2000.5,0\n",
                    encoding="utf-8",
                )

            year_files = ["DAT_MT_XAUUSD_M1_2009.csv", "DAT_MT_XAUUSD_M1_202601.csv"]
            with mock.patch.object(prep, "REPO_ROOT", root), mock.patch.object(prep, "MERGED_PATH", merged), mock.patch.object(
                prep, "DATASET_DIR", dataset
            ), mock.patch.object(prep, "YEAR_FILES", year_files), mock.patch.object(prep, "_download", side_effect=fake_download):
                out = prep.prepare_dataset(force=True)
                self.assertTrue(out.is_file())
                df = pd.read_csv(out)
                self.assertEqual(list(df.columns), ["Datetime", "Open", "High", "Low", "Close", "Volume"])
                self.assertEqual(len(list(dataset.glob("DAT_MT_*.csv"))), 0)


if __name__ == "__main__":
    unittest.main()
