from django.db import models


class Dataset(models.Model):
    symbol = models.CharField(max_length=32, default="XAUUSD")
    timeframe = models.CharField(max_length=8, default="1H")
    source_name = models.CharField(max_length=255)
    raw_path = models.CharField(max_length=1024)
    cache_path = models.CharField(max_length=1024)
    rows_m1 = models.IntegerField()
    rows_h1 = models.IntegerField()
    start_ts = models.DateTimeField(blank=True, null=True)
    end_ts = models.DateTimeField(blank=True, null=True)
    validation = models.JSONField(default=dict)
    volume_usable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.source_name
