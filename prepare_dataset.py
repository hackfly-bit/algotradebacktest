"""Download yearly XAUUSD M1 CSVs from HuggingFace and merge into notebook contract.

Run from repo root (Windows: prepare_dataset.bat). Stdlib + pandas only.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
MERGED_NAME = "XAUUSD_2009_2026_M1.csv"
MERGED_PATH = REPO_ROOT / MERGED_NAME
DATASET_DIR = REPO_ROOT / "dataset"
HF_BASE = "https://huggingface.co/datasets/fokan/xauusd-2009-2026/resolve/main"

YEAR_FILES = [f"DAT_MT_XAUUSD_M1_{year}.csv" for year in range(2009, 2026)]
YEAR_FILES.append("DAT_MT_XAUUSD_M1_202601.csv")


def _download(name: str, dest: Path) -> None:
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"skip existing {dest.name}")
        return
    url = f"{HF_BASE}/{name}"
    print(f"download {name} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def _read_year(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        header=None,
        names=["Date", "Time", "Open", "High", "Low", "Close", "Volume"],
    )
    df["Datetime"] = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str),
        format="%Y.%m.%d %H:%M",
    )
    return df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]


def prepare_dataset(force: bool = False) -> Path:
    if MERGED_PATH.is_file() and not force:
        print(f"already exists: {MERGED_PATH}")
        return MERGED_PATH

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    for name in YEAR_FILES:
        dest = DATASET_DIR / name
        _download(name, dest)
        frames.append(_read_year(dest))

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates("Datetime", keep="first").sort_values("Datetime")
    merged = merged.reset_index(drop=True)
    merged.to_csv(MERGED_PATH, index=False)
    print(f"wrote {MERGED_PATH} rows={len(merged)}")

    for path in DATASET_DIR.glob("DAT_MT_XAUUSD_M1_*.csv"):
        path.unlink(missing_ok=True)
    print(f"cleaned raw files in {DATASET_DIR}")
    return MERGED_PATH


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in args
    prepare_dataset(force=force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
