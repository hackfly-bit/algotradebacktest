from __future__ import annotations

from datetime import date

from django import forms

from apps.core.models import BacktestSettings


class BacktestSettingsForm(forms.ModelForm):
    class Meta:
        model = BacktestSettings
        fields = [
            "initial_equity",
            "fee",
            "commission_per_lot",
            "spread",
            "slippage",
            "risk_pct",
            "contract_size",
            "in_sample_end",
            "oos_start",
        ]
        widgets = {
            "initial_equity": forms.NumberInput(attrs={"class": "field-input", "step": "100"}),
            "fee": forms.NumberInput(attrs={"class": "field-input", "step": "0.0001"}),
            "commission_per_lot": forms.NumberInput(attrs={"class": "field-input", "step": "0.1"}),
            "spread": forms.NumberInput(attrs={"class": "field-input", "step": "0.01"}),
            "slippage": forms.NumberInput(attrs={"class": "field-input", "step": "0.00001"}),
            "risk_pct": forms.NumberInput(attrs={"class": "field-input", "step": "0.001"}),
            "contract_size": forms.NumberInput(attrs={"class": "field-input", "step": "1"}),
            "in_sample_end": forms.DateInput(attrs={"class": "field-input", "type": "date"}),
            "oos_start": forms.DateInput(attrs={"class": "field-input", "type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        is_end = cleaned.get("in_sample_end")
        oos_start = cleaned.get("oos_start")
        if is_end and oos_start and is_end >= oos_start:
            raise forms.ValidationError("In-sample end harus sebelum OOS start.")
        return cleaned


def default_run_initial() -> dict:
    cfg = BacktestSettings.load()
    initial = {
        "initial_equity": cfg.initial_equity,
        "fee": cfg.fee,
        "commission_per_lot": cfg.commission_per_lot,
        "spread": cfg.spread,
        "slippage": cfg.slippage,
        "risk_pct": cfg.risk_pct,
        "contract_size": cfg.contract_size,
    }
    if cfg.in_sample_end:
        initial["in_sample_end"] = cfg.in_sample_end
    else:
        initial["in_sample_end"] = date(2023, 12, 31)
    if cfg.oos_start:
        initial["oos_start"] = cfg.oos_start
    else:
        initial["oos_start"] = date(2024, 1, 1)
    return initial
