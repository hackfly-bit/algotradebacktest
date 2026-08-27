from django.urls import path

from apps.strategies import views

app_name = "strategies"

urlpatterns = [
    path("", views.strategy_list, name="strategy_list"),
    path("<slug:slug>/", views.strategy_detail, name="strategy_detail"),
]
