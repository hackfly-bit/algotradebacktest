from django.conf import settings
from django.db import models


class BacktestRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "queued"
        RUNNING = "running", "running"
        DONE = "done", "done"
        FAILED = "failed", "failed"

    dataset = models.ForeignKey(
        "marketdata.Dataset",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    strategy_name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    params = models.JSONField(default=dict, blank=True)
    initial_equity = models.FloatField(default=10_000.0)
    fee = models.FloatField(default=0.0)
    commission_per_lot = models.FloatField(default=7.0)
    spread = models.FloatField(default=0.25)
    slippage = models.FloatField(default=0.0001)
    risk_pct = models.FloatField(default=0.01)
    contract_size = models.FloatField(default=100.0)
    in_sample_end = models.DateField(null=True, blank=True)
    oos_start = models.DateField(null=True, blank=True)
    multi_deep = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    error_message = models.TextField(blank=True)
    task_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backtest_runs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.strategy_name} #{self.pk} ({self.status})"


class Trade(models.Model):
    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="trades")
    entry_time = models.DateTimeField()
    exit_time = models.DateTimeField()
    direction = models.SmallIntegerField()
    entry = models.FloatField()
    exit = models.FloatField()
    lots = models.FloatField()
    pnl = models.FloatField()
    return_pct = models.FloatField()
    reason = models.CharField(max_length=16)

    class Meta:
        indexes = [models.Index(fields=["run"])]


class MetricSet(models.Model):
    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="metrics")
    split = models.CharField(max_length=32, default="full")
    label = models.CharField(max_length=64, blank=True)
    final_equity = models.FloatField(null=True, blank=True)
    total_return = models.FloatField(null=True, blank=True)
    cagr = models.FloatField(null=True, blank=True)
    sharpe = models.FloatField(null=True, blank=True)
    sortino = models.FloatField(null=True, blank=True)
    calmar = models.FloatField(null=True, blank=True)
    max_drawdown = models.FloatField(null=True, blank=True)
    win_rate = models.FloatField(null=True, blank=True)
    profit_factor = models.FloatField(null=True, blank=True)
    expectancy = models.FloatField(null=True, blank=True)
    average_win = models.FloatField(null=True, blank=True)
    average_loss = models.FloatField(null=True, blank=True)
    trades = models.IntegerField(null=True, blank=True)
    average_trade = models.FloatField(null=True, blank=True)
    longest_losing_streak = models.IntegerField(null=True, blank=True)
    recovery_factor = models.FloatField(null=True, blank=True)
    years = models.FloatField(null=True, blank=True)
    extras = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["run", "split"])]
