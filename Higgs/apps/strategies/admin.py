from django.contrib import admin

from apps.strategies.models import StrategyDefinition


@admin.register(StrategyDefinition)
class StrategyDefinitionAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "status", "allow_short", "is_builtin", "updated_at")
    list_filter = ("status", "allow_short", "is_builtin")
    search_fields = ("label", "slug")
    readonly_fields = ("created_at", "updated_at", "logic_spec")
