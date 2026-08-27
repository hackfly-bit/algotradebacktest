from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.marketdata.models import Dataset


@login_required
def overview(request):
    return render(
        request,
        "core/overview.html",
        {
            "page_title": "Ringkasan",
            "dataset_count": Dataset.objects.count(),
        },
    )


@login_required
def app_settings(request):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Pengaturan",
            "placeholder_note": "Default fee, spread, slippage, dan risiko belum diikat ke form. Fase berikutnya.",
        },
    )
