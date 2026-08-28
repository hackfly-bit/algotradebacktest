"""Seed built-in strategy templates into DB (optional reference rows)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.strategies.models import StrategyDefinition
from apps.strategies.services import load_builtin_templates
from engine.rule_schema import validate_definition
from engine.rule_spec import build_logic_spec


class Command(BaseCommand):
    help = "Validate and optionally install built-in JSON strategy templates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--install",
            action="store_true",
            help="Create archived template rows in StrategyDefinition",
        )

    def handle(self, *args, **options):
        templates = load_builtin_templates()
        for name, defn in templates.items():
            validate_definition(defn)
            self.stdout.write(self.style.SUCCESS(f"OK {name}"))
            if options["install"]:
                slug = f"template_{name}"
                StrategyDefinition.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "label": defn.get("label", name),
                        "definition_json": defn,
                        "allow_short": bool(defn.get("allow_short")),
                        "is_builtin": True,
                        "status": StrategyDefinition.Status.ARCHIVED,
                        "logic_spec": build_logic_spec(defn),
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"Validated {len(templates)} templates"))
