from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def run_list(request):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Run",
            "placeholder_note": "Daftar run belum ada. Persistensi BacktestRun masuk Fase 6.",
        },
    )


@login_required
def run_new(request):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Run baru",
            "placeholder_note": "Form screening belum diimplementasi. Fase 7.",
        },
    )


@login_required
def run_detail(request, pk):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Detail run",
            "placeholder_note": f"Run #{pk} belum ada. Tab metrik masuk Fase 7–11.",
        },
    )


@login_required
def run_status(request, pk):
    return render(
        request,
        "backtests/partials/status.html",
        {"status_text": "Tidak ada job berjalan."},
    )


@login_required
def compare(request):
    return render(
        request,
        "partials/placeholder.html",
        {
            "page_title": "Bandingkan",
            "placeholder_note": "Tabel banding IS/OOS belum diimplementasi. Fase 7.",
        },
    )
