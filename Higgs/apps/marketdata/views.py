from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.marketdata.forms import DatasetIngestForm
from apps.marketdata.ingest import ingest_dataset
from apps.marketdata.models import Dataset


def _save_upload(upload) -> Path:
    uploads = Path(settings.MEDIA_ROOT) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    name = Path(upload.name).name or "upload.csv"
    dest = uploads / f"{uuid4().hex[:10]}_{name}"
    with dest.open("wb") as handle:
        for chunk in upload.chunks():
            handle.write(chunk)
    return dest


@login_required
def dataset_list(request):
    datasets = Dataset.objects.all()
    form = DatasetIngestForm()
    if request.method == "POST":
        form = DatasetIngestForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            raw_path = form.cleaned_data["local_path"]
            if csv_file:
                raw_path = str(_save_upload(csv_file))
            try:
                dataset = ingest_dataset(
                    raw_path,
                    source_name=form.cleaned_data["source_name"] or None,
                    symbol=form.cleaned_data["symbol"],
                    timeframe=form.cleaned_data["timeframe"],
                )
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Dataset {dataset.source_name} tersimpan. H1 {dataset.rows_h1} bar.")
                return redirect("marketdata:dataset_detail", pk=dataset.pk)
    return render(
        request,
        "marketdata/dataset_list.html",
        {
            "page_title": "Dataset",
            "datasets": datasets,
            "form": form,
        },
    )


@login_required
def dataset_detail(request, pk):
    dataset = get_object_or_404(Dataset, pk=pk)
    validation = dataset.validation or {}
    return render(
        request,
        "marketdata/dataset_detail.html",
        {
            "page_title": dataset.source_name,
            "dataset": dataset,
            "m1_report": validation.get("m1") or {},
            "h1_report": validation.get("h1") or {},
        },
    )
