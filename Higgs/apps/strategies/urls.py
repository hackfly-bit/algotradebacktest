from django.urls import path

from apps.strategies import views

app_name = "strategies"

urlpatterns = [
    path("", views.strategy_list, name="strategy_list"),
    path("builder/", views.builder_list, name="builder_list"),
    path("builder/new/", views.builder_new, name="builder_new"),
    path("builder/<int:pk>/edit/", views.builder_edit, name="builder_edit"),
    path("builder/<int:pk>/archive/", views.builder_archive, name="builder_archive"),
    path("builder/<int:pk>/export/", views.builder_export, name="builder_export"),
    path("builder/<int:pk>/preview/", views.builder_preview, name="builder_preview"),
    path("builder/<int:pk>/quick-test/", views.builder_quick_test, name="builder_quick_test"),
    path("builder/import/", views.builder_import, name="builder_import"),
    path("<slug:slug>/", views.strategy_detail, name="strategy_detail"),
]
