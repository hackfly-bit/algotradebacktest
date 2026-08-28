"""Bridge Django StrategyDefinition to engine custom registry."""

from __future__ import annotations

from engine.custom_registry import clear_custom_strategies, register_custom_strategy
from engine.rule_spec import build_logic_spec


def sync_custom_strategies() -> int:
    from apps.strategies.models import StrategyDefinition

    clear_custom_strategies()
    count = 0
    for row in StrategyDefinition.objects.filter(status=StrategyDefinition.Status.ACTIVE):
        spec = row.logic_spec or build_logic_spec(row.definition_json)
        register_custom_strategy(row.slug, row.definition_json, spec)
        count += 1
    return count


def register_strategy_row(row) -> None:
    spec = row.logic_spec or build_logic_spec(row.definition_json)
    register_custom_strategy(row.slug, row.definition_json, spec)


def unregister_strategy_slug(slug: str) -> None:
    from engine.custom_registry import unregister_custom_strategy

    unregister_custom_strategy(slug)
