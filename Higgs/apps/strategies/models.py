from django.conf import settings
from django.db import models


class StrategyDefinition(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "draft"
        ACTIVE = "active", "active"
        ARCHIVED = "archived", "archived"

    slug = models.SlugField(max_length=128, unique=True)
    label = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    schema_version = models.PositiveSmallIntegerField(default=1)
    definition_json = models.JSONField(default=dict)
    allow_short = models.BooleanField(default=False)
    is_builtin = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    logic_spec = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="strategy_definitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.label
