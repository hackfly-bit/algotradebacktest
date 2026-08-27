from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def strategy_list(request):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Strategi",
            "placeholder_note": "Registry plugin belum di-port. Lima strategi masuk Fase 4.",
        },
    )


@login_required
def strategy_detail(request, slug):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Detail strategi",
            "placeholder_note": f"Strategi «{slug}» belum terdaftar. Registry masuk Fase 4.",
        },
    )
