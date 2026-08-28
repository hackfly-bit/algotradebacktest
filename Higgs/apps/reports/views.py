from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from apps.reports.models import ExportFile


def _export_root() -> Path:
    return (Path(settings.MEDIA_ROOT) / "exports").resolve()


def _safe_export_path(raw_path: str) -> Path:
    path = Path(raw_path).resolve()
    export_root = _export_root()
    if not path.is_relative_to(export_root):
        raise Http404("Path export tidak valid.")
    if not path.is_file():
        raise Http404("File export tidak ditemukan.")
    return path


@login_required
def export_list(request):
    files = ExportFile.objects.select_related("run", "run__dataset").order_by("-created_at")[:100]
    return render(
        request,
        "reports/export_list.html",
        {"page_title": "Ekspor", "files": files},
    )


@login_required
def export_download(request, pk):
    export = get_object_or_404(ExportFile, pk=pk)
    path = _safe_export_path(export.path)
    content_type = "text/markdown" if export.kind == "md" else "text/plain"
    return FileResponse(path.open("rb"), as_attachment=True, filename=export.filename, content_type=content_type)
