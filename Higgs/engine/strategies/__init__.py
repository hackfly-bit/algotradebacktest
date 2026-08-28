"""Auto-discover strategy plugins in this package."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


def discover() -> None:
    for module in pkgutil.iter_modules([str(_PACKAGE_DIR)]):
        if module.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module.name}")


discover()
