from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

import engine.strategies  # noqa: F401 — register plugins
from engine.registry import DEFAULT_PARAMS, STRATEGY_SPECS, list_strategies


def _preview(spec: str, limit: int = 140) -> str:
    text = " ".join(spec.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


@login_required
def strategy_list(request):
    rows = [
        {"name": name, "spec_preview": _preview(STRATEGY_SPECS.get(name, ""))}
        for name in list_strategies()
    ]
    return render(
        request,
        "strategies/strategy_list.html",
        {
            "page_title": "Strategi",
            "strategies": rows,
        },
    )


@login_required
def strategy_detail(request, slug):
    if slug not in STRATEGY_SPECS:
        raise Http404(f"Strategi «{slug}» tidak terdaftar.")
    params = sorted(DEFAULT_PARAMS.items())
    return render(
        request,
        "strategies/strategy_detail.html",
        {
            "page_title": slug,
            "name": slug,
            "logic_spec": STRATEGY_SPECS[slug],
            "default_params": params,
        },
    )
