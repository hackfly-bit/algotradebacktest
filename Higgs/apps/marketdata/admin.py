from django.contrib import admin

from apps.marketdata.models import Dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("source_name", "symbol", "timeframe", "rows_h1", "volume_usable", "created_at")
    readonly_fields = ("created_at",)
