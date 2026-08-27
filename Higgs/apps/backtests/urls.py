from django.urls import path

from apps.backtests import views

app_name = "backtests"

urlpatterns = [
    path("runs/", views.run_list, name="run_list"),
    path("runs/new/", views.run_new, name="run_new"),
    path("runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("runs/<int:pk>/status/", views.run_status, name="run_status"),
    path("compare/", views.compare, name="compare"),
]
