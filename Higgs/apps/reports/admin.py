from django.contrib import admin

from apps.reports.models import ExportFile


@admin.register(ExportFile)
class ExportFileAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "kind", "filename", "created_at")
    list_filter = ("kind",)
