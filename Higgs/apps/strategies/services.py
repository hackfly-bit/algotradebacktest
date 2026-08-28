"""Strategy listing and template helpers."""

from __future__ import annotations

import json
from pathlib import Path

from engine.registry import STRATEGY_REGISTRY, list_strategies

TEMPLATES_PATH = Path(__file__).resolve().parents[2] / "engine" / "strategies" / "builtin_templates.json"


def load_builtin_templates() -> dict:
    if not TEMPLATES_PATH.is_file():
        return {}
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


def list_builtin_names() -> list[str]:
    return sorted(STRATEGY_REGISTRY.keys())


def list_active_custom_slugs() -> list[str]:
    from apps.strategies.models import StrategyDefinition

    return list(
        StrategyDefinition.objects.filter(status=StrategyDefinition.Status.ACTIVE).values_list("slug", flat=True)
    )


def list_run_strategies() -> list[tuple[str, str]]:
    """Return (value, label) choices for run form."""
    rows = [(name, name) for name in sorted(STRATEGY_REGISTRY.keys())]
    from apps.strategies.models import StrategyDefinition

    for sd in StrategyDefinition.objects.filter(status=StrategyDefinition.Status.ACTIVE).order_by("label"):
        if sd.slug not in STRATEGY_REGISTRY:
            rows.append((sd.slug, f"{sd.label} ({sd.slug})"))
    return rows


def all_strategy_names_for_screening() -> list[str]:
    from apps.strategies.registry_bridge import sync_custom_strategies

    sync_custom_strategies()
    return list_strategies()
