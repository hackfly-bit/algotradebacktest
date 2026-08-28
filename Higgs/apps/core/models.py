from django.db import models


class BacktestSettings(models.Model):
    """Singleton defaults for new backtest runs (pk=1)."""

    initial_equity = models.FloatField(default=10_000.0)
    fee = models.FloatField(default=0.0)
    commission_per_lot = models.FloatField(default=7.0)
    spread = models.FloatField(default=0.25)
    slippage = models.FloatField(default=0.0001)
    risk_pct = models.FloatField(default=0.01)
    contract_size = models.FloatField(default=100.0)
    in_sample_end = models.DateField(null=True, blank=True)
    oos_start = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Backtest defaults"
        verbose_name_plural = "Backtest defaults"

    def __str__(self) -> str:
        return "Backtest defaults"

    @classmethod
    def load(cls) -> "BacktestSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
