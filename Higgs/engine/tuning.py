"""Per-strategy parameter grids for walk-forward and robustness. Do not import Django."""

from __future__ import annotations

from dataclasses import dataclass

EMA_FAST_GRID = (10, 15, 20, 25, 30)
EMA_WF_GRID = (15, 20, 25)
EMA_PERTURB_PAIRS = ((18, 48), (19, 49), (20, 50), (21, 51), (22, 52))
LOOKBACK_GRID = (10, 15, 20, 25, 30)
LOOKBACK_WF_GRID = (12, 18, 24)
LOOKBACK_PERTURB = (18, 20, 22, 24, 26)


@dataclass(frozen=True)
class StrategyTuning:
    wf_variants: tuple[dict, ...]
    param_grid_variants: tuple[dict, ...]
    perturb_variants: tuple[dict, ...]


def _ema_tuning() -> StrategyTuning:
    return StrategyTuning(
        wf_variants=tuple({"ema_fast": v} for v in EMA_WF_GRID),
        param_grid_variants=tuple({"ema_fast": v} for v in EMA_FAST_GRID),
        perturb_variants=tuple({"ema_fast": f, "ema_slow": s} for f, s in EMA_PERTURB_PAIRS),
    )


def _lookback_tuning() -> StrategyTuning:
    return StrategyTuning(
        wf_variants=tuple({"lookback": v} for v in LOOKBACK_WF_GRID),
        param_grid_variants=tuple({"lookback": v} for v in LOOKBACK_GRID),
        perturb_variants=tuple({"lookback": v} for v in LOOKBACK_PERTURB),
    )


def _gemini_tuning() -> StrategyTuning:
    return StrategyTuning(
        wf_variants=tuple({"lookback": v} for v in (18, 24, 30)),
        param_grid_variants=tuple({"lookback": v} for v in (18, 21, 24, 27, 30)),
        perturb_variants=tuple({"ema_fast": f, "ema_slow": s} for f, s in EMA_PERTURB_PAIRS),
    )


def _kimi_tuning() -> StrategyTuning:
    return StrategyTuning(
        wf_variants=tuple({"lookback": v} for v in (16, 20, 24)),
        param_grid_variants=tuple({"lookback": v} for v in (14, 18, 20, 22, 26)),
        perturb_variants=tuple({"ema_fast": f, "ema_slow": s} for f, s in EMA_PERTURB_PAIRS),
    )


STRATEGY_TUNING: dict[str, StrategyTuning] = {
    "breakout_atr": _lookback_tuning(),
    "ema_rsi_volume": _ema_tuning(),
    "trend_pullback_by_claude": _ema_tuning(),
    "trend_breakout_by_gemini": _gemini_tuning(),
    "momentum_squeeze_by_kimi": _kimi_tuning(),
}


def get_strategy_tuning(strategy_name: str) -> StrategyTuning:
    return STRATEGY_TUNING.get(strategy_name, _ema_tuning())


def variant_label(variant: dict) -> str:
    if len(variant) == 1:
        key, value = next(iter(variant.items()))
        if isinstance(value, float):
            return f"{key}_{value:g}"
        return f"{key}_{value}"
    return "_".join(f"{k}={v}" for k, v in sorted(variant.items()))


def param_stable_threshold(grid_len: int) -> int:
    if grid_len <= 0:
        return 0
    return max(2, min(4, grid_len - 1))
