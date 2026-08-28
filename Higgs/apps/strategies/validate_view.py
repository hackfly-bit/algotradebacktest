"""Validate rule definition without saving (HTMX / fetch)."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from engine.rule_schema import RuleSchemaError, validate_definition
from engine.rule_spec import build_logic_spec


@login_required
@require_POST
def builder_validate(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        defn = payload.get("definition") or payload
        validate_definition(defn)
        return JsonResponse(
            {
                "ok": True,
                "logic_spec": build_logic_spec(defn),
            }
        )
    except (json.JSONDecodeError, RuleSchemaError, TypeError, ValueError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
