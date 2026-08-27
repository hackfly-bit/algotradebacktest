from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("", views.export_list, name="export_list"),
    path("<int:pk>/download/", views.export_download, name="export_download"),
]
