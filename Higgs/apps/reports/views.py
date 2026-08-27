from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def export_list(request):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Ekspor",
            "placeholder_note": "File spec MQL5 belum dihasilkan. Gate dan ekspor masuk Fase 11.",
        },
    )


@login_required
def export_download(request, pk):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Unduh ekspor",
            "placeholder_note": f"Ekspor #{pk} belum ada. Fase 11.",
        },
    )
