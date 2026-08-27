from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.marketdata.ingest import ingest_dataset
from apps.marketdata.models import Dataset


def _mini_csv(path: Path, n: int = 60, volume: float = 0.0) -> None:
    index = pd.date_range("2024-01-02 10:00:00", periods=n, freq="min")
    closes = 2000.0 + pd.Series(range(n), dtype="float64") * 0.01
    pd.DataFrame(
        {
            "Datetime": index,
            "Open": closes,
            "High": closes + 0.1,
            "Low": closes - 0.1,
            "Close": closes,
            "Volume": volume,
        }
    ).to_csv(path, index=False)


class DatasetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="higgs", password="higgs-dev")

    def test_list_requires_login(self):
        response = self.client.get(reverse("marketdata:dataset_list"))
        self.assertEqual(response.status_code, 302)

    def test_list_empty_state(self):
        self.client.login(username="higgs", password="higgs-dev")
        response = self.client.get(reverse("marketdata:dataset_list"))
        self.assertContains(response, "Belum ada dataset.")

    def test_ingest_local_path_and_detail(self):
        self.client.login(username="higgs", password="higgs-dev")
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                csv_path = Path(tmp) / "mini.csv"
                _mini_csv(csv_path)
                response = self.client.post(
                    reverse("marketdata:dataset_list"),
                    {
                        "source_name": "mini-xau",
                        "symbol": "XAUUSD",
                        "timeframe": "1H",
                        "local_path": str(csv_path),
                    },
                )
                self.assertEqual(response.status_code, 302)
                dataset = Dataset.objects.get()
                self.assertEqual(dataset.rows_h1, 1)
                self.assertFalse(dataset.volume_usable)
                detail = self.client.get(reverse("marketdata:dataset_detail", args=[dataset.pk]))
                self.assertContains(detail, "tidak")
                self.assertContains(detail, "volume_usable")
                overview = self.client.get(reverse("core:overview"))
                self.assertContains(overview, "1 dataset terdaftar")
                self.assertContains(overview, "mini-xau")


class IngestCommandTests(TestCase):
    def test_call_command_creates_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                csv_path = Path(tmp) / "cmd.csv"
                _mini_csv(csv_path)
                call_command("ingest_dataset", str(csv_path), source_name="from-cmd")
                dataset = Dataset.objects.get()
                self.assertEqual(dataset.source_name, "from-cmd")
                self.assertEqual(dataset.rows_h1, 1)
                self.assertFalse(dataset.volume_usable)
                self.assertTrue(Path(dataset.cache_path).is_file())


class IngestHelperTests(TestCase):
    def test_ingest_dataset_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                csv_path = Path(tmp) / "helper.csv"
                _mini_csv(csv_path, volume=0)
                dataset = ingest_dataset(csv_path, source_name="helper")
                self.assertEqual(dataset.rows_m1, 60)
                self.assertIn("m1", dataset.validation)
                self.assertIn("h1", dataset.validation)
