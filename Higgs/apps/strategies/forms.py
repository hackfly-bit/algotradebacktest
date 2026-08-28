"""Forms for strategy builder."""

from __future__ import annotations

import json
import re

from django import forms
from django.core.exceptions import ValidationError

from apps.strategies.models import StrategyDefinition
from apps.strategies.services import load_builtin_templates
from engine.rule_schema import RuleSchemaError, validate_definition
from engine.rule_spec import build_logic_spec

SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class StrategyDefinitionForm(forms.ModelForm):
    template_key = forms.ChoiceField(
        label="Template",
        required=False,
        widget=forms.Select(attrs={"class": "field-input"}),
    )
    definition_raw = forms.CharField(
        label="Definisi JSON",
        required=False,
        widget=forms.Textarea(attrs={"class": "field-input font-mono text-[11px]", "rows": 18}),
    )

    class Meta:
        model = StrategyDefinition
        fields = ["label", "slug", "description", "allow_short", "status"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "field-input"}),
            "slug": forms.TextInput(attrs={"class": "field-input", "placeholder": "my_breakout"}),
            "description": forms.Textarea(attrs={"class": "field-input", "rows": 3}),
            "allow_short": forms.CheckboxInput(attrs={"class": "rounded border-black/20"}),
            "status": forms.Select(attrs={"class": "field-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        templates = load_builtin_templates()
        self.fields["template_key"].choices = [("", "— kosong / edit JSON —")] + [
            (k, v.get("label", k)) for k, v in templates.items()
        ]
        if self.instance and self.instance.pk and self.instance.definition_json:
            self.fields["definition_raw"].initial = json.dumps(self.instance.definition_json, indent=2)
        elif not self.is_bound:
            key = self.initial.get("template_key") or self.data.get("template_key")
            if key and key in templates:
                self.fields["definition_raw"].initial = json.dumps(templates[key], indent=2)

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip().lower()
        slug = slug.replace("-", "_")
        if not slug:
            raise ValidationError("Slug wajib diisi.")
        if not SLUG_RE.match(slug):
            raise ValidationError("Slug hanya huruf kecil, angka, underscore.")
        if not slug.startswith("custom_") and not self.instance.is_builtin:
            slug = f"custom_{slug}"
        qs = StrategyDefinition.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Slug sudah dipakai.")
        return slug

    def clean(self):
        cleaned = super().clean()
        raw = (cleaned.get("definition_raw") or "").strip()
        template_key = cleaned.get("template_key")
        if not raw and template_key:
            templates = load_builtin_templates()
            raw = json.dumps(templates.get(template_key, {}))
        if not raw:
            raise ValidationError("Isi definisi JSON atau pilih template.")
        try:
            defn = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"JSON tidak valid: {exc}") from exc
        try:
            validate_definition(defn)
        except RuleSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        cleaned["definition_json"] = defn
        if cleaned.get("allow_short") is None:
            cleaned["allow_short"] = bool(defn.get("allow_short"))
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.definition_json = self.cleaned_data["definition_json"]
        obj.schema_version = int(obj.definition_json.get("schema_version", 1))
        obj.logic_spec = build_logic_spec(obj.definition_json)
        if commit:
            obj.save()
            from apps.strategies.registry_bridge import register_strategy_row

            if obj.status == StrategyDefinition.Status.ACTIVE:
                register_strategy_row(obj)
            else:
                from apps.strategies.registry_bridge import unregister_strategy_slug

                unregister_strategy_slug(obj.slug)
        return obj


class StrategyImportForm(forms.Form):
    file = forms.FileField(label="Import JSON", widget=forms.ClearableFileInput(attrs={"class": "field-input"}))

    def clean_file(self):
        upload = self.cleaned_data["file"]
        try:
            data = json.loads(upload.read().decode("utf-8"))
            validate_definition(data)
        except RuleSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"File tidak valid: {exc}") from exc
        self.cleaned_data["definition"] = data
        return upload
