"""Runtime registry for UI-built custom strategies. Do not import Django."""

from __future__ import annotations

from typing import Callable

from engine.rule_interpreter import make_custom_strategy
from engine.rule_schema import validate_definition

CUSTOM_STRATEGY_REGISTRY: dict[str, Callable] = {}
CUSTOM_STRATEGY_DEFS: dict[str, dict] = {}
CUSTOM_STRATEGY_SPECS: dict[str, str] = {}


def clear_custom_strategies() -> None:
    CUSTOM_STRATEGY_REGISTRY.clear()
    CUSTOM_STRATEGY_DEFS.clear()
    CUSTOM_STRATEGY_SPECS.clear()


def register_custom_strategy(name: str, definition: dict, logic_spec: str = "") -> None:
    validate_definition(definition)
    CUSTOM_STRATEGY_DEFS[name] = definition
    CUSTOM_STRATEGY_SPECS[name] = logic_spec or definition.get("label", name)
    CUSTOM_STRATEGY_REGISTRY[name] = make_custom_strategy(definition)


def unregister_custom_strategy(name: str) -> None:
    CUSTOM_STRATEGY_REGISTRY.pop(name, None)
    CUSTOM_STRATEGY_DEFS.pop(name, None)
    CUSTOM_STRATEGY_SPECS.pop(name, None)


def list_custom_strategies() -> list[str]:
    return sorted(CUSTOM_STRATEGY_REGISTRY)


def get_custom_definition(name: str) -> dict | None:
    return CUSTOM_STRATEGY_DEFS.get(name)
