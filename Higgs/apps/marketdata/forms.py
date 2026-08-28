from pathlib import Path

from django import forms
from django.conf import settings

DEFAULT_UPLOAD_HINT = "media/uploads/…"


class DatasetIngestForm(forms.Form):
    source_name = forms.CharField(
        label="Nama sumber",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "field-input"}),
    )
    symbol = forms.CharField(
        label="Simbol",
        max_length=32,
        initial="XAUUSD",
        widget=forms.TextInput(attrs={"class": "field-input"}),
    )
    timeframe = forms.CharField(
        label="Timeframe cache",
        max_length=8,
        initial="1H",
        widget=forms.TextInput(attrs={"class": "field-input"}),
    )
    csv_file = forms.FileField(
        label="Unggah CSV M1",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "field-input", "accept": ".csv,text/csv"}),
    )
    local_path = forms.CharField(
        label="Atau path di bawah media/",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "field-input",
                "placeholder": DEFAULT_UPLOAD_HINT,
            }
        ),
        help_text=f"Hanya file di dalam {settings.MEDIA_ROOT}. Untuk path lain gunakan manage.py ingest_dataset.",
    )

    def clean(self):
        cleaned = super().clean()
        csv_file = cleaned.get("csv_file")
        local_path = (cleaned.get("local_path") or "").strip()
        cleaned["local_path"] = local_path
        if bool(csv_file) == bool(local_path):
            raise forms.ValidationError("Unggah satu file CSV atau isi path lokal, jangan keduanya.")
        if local_path:
            media_root = Path(settings.MEDIA_ROOT).resolve()
            path = Path(local_path).expanduser()
            if not path.is_absolute():
                path = media_root / path
            path = path.resolve()
            if not path.is_relative_to(media_root):
                raise forms.ValidationError("Path harus berada di dalam folder media aplikasi.")
            if not path.is_file():
                raise forms.ValidationError(f"File tidak ditemukan: {local_path}")
            cleaned["local_path"] = str(path)
        return cleaned
