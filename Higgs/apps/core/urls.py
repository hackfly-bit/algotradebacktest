from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("settings/", views.app_settings, name="settings"),
]
