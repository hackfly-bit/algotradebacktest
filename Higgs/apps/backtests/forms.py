from __future__ import annotations

from datetime import date

from django import forms

import engine.strategies  # noqa: F401
from apps.marketdata.models import Dataset
from engine.registry import list_strategies


class BacktestRunForm(forms.Form):
    dataset = forms.ModelChoiceField(
        label="Dataset",
        queryset=Dataset.objects.all(),
        widget=forms.Select(attrs={"class": "field-input"}),
    )
    strategy_name = forms.ChoiceField(
        label="Strategi",
        widget=forms.Select(attrs={"class": "field-input"}),
    )
    initial_equity = forms.FloatField(
        label="Equity awal",
        initial=10_000.0,
        widget=forms.NumberInput(attrs={"class": "field-input", "step": "100"}),
    )
    fee = forms.FloatField(label="Fee", initial=0.0, widget=forms.NumberInput(attrs={"class": "field-input", "step": "0.0001"}))
    commission_per_lot = forms.FloatField(
        label="Komisi / lot",
        initial=7.0,
        widget=forms.NumberInput(attrs={"class": "field-input", "step": "0.1"}),
    )
    spread = forms.FloatField(label="Spread", initial=0.25, widget=forms.NumberInput(attrs={"class": "field-input", "step": "0.01"}))
    slippage = forms.FloatField(
        label="Slippage",
        initial=0.0001,
        widget=forms.NumberInput(attrs={"class": "field-input", "step": "0.00001"}),
    )
    risk_pct = forms.FloatField(
        label="Risk %",
        initial=0.01,
        widget=forms.NumberInput(attrs={"class": "field-input", "step": "0.001"}),
    )
    contract_size = forms.FloatField(
        label="Contract size",
        initial=100.0,
        widget=forms.NumberInput(attrs={"class": "field-input", "step": "1"}),
    )
    in_sample_end = forms.DateField(
        label="In-sample end",
        initial=date(2023, 12, 31),
        widget=forms.DateInput(attrs={"class": "field-input", "type": "date"}),
    )
    oos_start = forms.DateField(
        label="OOS start",
        initial=date(2024, 1, 1),
        widget=forms.DateInput(attrs={"class": "field-input", "type": "date"}),
    )
    multi_deep = forms.BooleanField(
        label="MULTI_DEEP (walk-forward, robustness, MC)",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "rounded border-black/20"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("*", "Semua strategi (*)")] + [(n, n) for n in list_strategies()]
        self.fields["strategy_name"].choices = choices
        if not self.fields["dataset"].queryset.exists():
            self.fields["dataset"].empty_label = "Tidak ada dataset"
