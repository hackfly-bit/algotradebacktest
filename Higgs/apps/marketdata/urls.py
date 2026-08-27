from django.urls import path

from apps.marketdata import views

app_name = "marketdata"

urlpatterns = [
    path("", views.dataset_list, name="dataset_list"),
    path("<int:pk>/", views.dataset_detail, name="dataset_detail"),
]
