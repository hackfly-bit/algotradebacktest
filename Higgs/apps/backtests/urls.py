from django.urls import path

from apps.backtests import views

app_name = "backtests"

urlpatterns = [
    path("runs/", views.run_list, name="run_list"),
    path("runs/new/", views.run_new, name="run_new"),
    path("runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("runs/<int:pk>/partials/<slug:tab>/", views.run_partial, name="run_partial"),
    path("runs/<int:pk>/status/", views.run_status, name="run_status"),
    path("status/", views.global_status, name="global_status"),
    path("compare/", views.compare, name="compare"),
]
