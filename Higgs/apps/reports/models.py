from django.db import models


class ExportFile(models.Model):
    class Kind(models.TextChoices):
        MD = "md", "md"
        TXT = "txt", "txt"

    run = models.ForeignKey("backtests.BacktestRun", on_delete=models.CASCADE, related_name="exports")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    path = models.CharField(max_length=512)
    filename = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["run"])]

    def __str__(self) -> str:
        return self.filename
