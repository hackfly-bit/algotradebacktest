from django.contrib import admin

from apps.backtests.models import (
    BacktestRun,
    DecisionGate,
    MetricSet,
    MonteCarloSummary,
    RobustnessRow,
    Trade,
    WalkForwardFold,
)


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "strategy_name", "status", "dataset", "created_at", "finished_at")
    list_filter = ("status", "strategy_name")
    search_fields = ("strategy_name", "error_message")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "entry_time", "exit_time", "direction", "pnl", "reason")
    list_filter = ("reason", "direction")


@admin.register(MetricSet)
class MetricSetAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "split", "label", "final_equity", "sharpe", "trades")
    list_filter = ("split",)


@admin.register(WalkForwardFold)
class WalkForwardFoldAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "dev_start", "val_start", "best_ema_fast", "val_sharpe", "positive_sharpe")
    list_filter = ("positive_sharpe",)


@admin.register(RobustnessRow)
class RobustnessRowAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "kind", "label", "oos_return", "oos_sharpe", "trades")
    list_filter = ("kind",)


@admin.register(MonteCarloSummary)
class MonteCarloSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "mode", "median_final", "prob_loss", "n_sims")
    list_filter = ("mode",)


@admin.register(DecisionGate)
class DecisionGateAdmin(admin.ModelAdmin):
    list_display = ("run", "status", "n_pass", "implement_mql5")
    list_filter = ("status", "implement_mql5")
