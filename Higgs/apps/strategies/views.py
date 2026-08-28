from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

import engine.strategies  # noqa: F401 — register plugins
from engine.registry import DEFAULT_PARAMS, STRATEGY_SPECS, list_strategies

SHORT_STRATEGIES = {"trend_breakout_by_gemini", "momentum_squeeze_by_kimi"}
VOLUME_STRATEGIES = {"ema_rsi_volume"}


def _preview(spec: str, limit: int = 140) -> str:
    text = " ".join(spec.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _pair_params(items: list[tuple]) -> list[tuple]:
    pairs = []
    for i in range(0, len(items), 2):
        left = items[i]
        right = items[i + 1] if i + 1 < len(items) else None
        pairs.append((left, right))
    return pairs


@login_required
def strategy_list(request):
    rows = []
    for name in list_strategies():
        rows.append(
            {
                "name": name,
                "spec_preview": _preview(STRATEGY_SPECS.get(name, "")),
                "allow_short": name in SHORT_STRATEGIES,
                "uses_volume": name in VOLUME_STRATEGIES,
            }
        )
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
            "param_pairs": _pair_params(params),
            "allow_short": slug in SHORT_STRATEGIES,
        },
    )
