from pathlib import Path

from django import forms

DEFAULT_CSV_HINT = r"e:\Project\AlgoTradeBacktest\XAUUSD_2009_2026_M1.csv"


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
        label="Atau path lokal",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "field-input",
                "placeholder": DEFAULT_CSV_HINT,
            }
        ),
        help_text=f"Contoh: {DEFAULT_CSV_HINT}",
    )

    def clean(self):
        cleaned = super().clean()
        csv_file = cleaned.get("csv_file")
        local_path = (cleaned.get("local_path") or "").strip()
        cleaned["local_path"] = local_path
        if bool(csv_file) == bool(local_path):
            raise forms.ValidationError("Unggah satu file CSV atau isi path lokal, jangan keduanya.")
        if local_path:
            path = Path(local_path).expanduser()
            if not path.is_file():
                raise forms.ValidationError(f"File tidak ditemukan: {local_path}")
            cleaned["local_path"] = str(path)
        return cleaned
