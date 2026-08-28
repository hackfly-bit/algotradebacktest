"""Monte Carlo simulation on trade PnLs. Do not import Django."""

from __future__ import annotations

import numpy as np
import pandas as pd

N_MC_SIMS = 10_000
MC_SEED = 42
INITIAL_EQUITY = 10_000.0
CONTRACT_SIZE = 100.0


def max_dd_matrix(equity: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(equity, axis=1)
    dd = (equity - peak) / np.where(peak == 0, np.nan, peak)
    return np.nanmin(dd, axis=1)


def _summarize(finals: np.ndarray, maxdds: np.ndarray, label: str, n_sims: int, initial: float) -> dict:
    bins = np.histogram(finals, bins=30)
    return {
        "label": label,
        "n_sims": int(n_sims),
        "median_final": float(np.median(finals)),
        "p5_final": float(np.percentile(finals, 5)),
        "p25_final": float(np.percentile(finals, 25)),
        "p50_final": float(np.percentile(finals, 50)),
        "p75_final": float(np.percentile(finals, 75)),
        "p95_final": float(np.percentile(finals, 95)),
        "median_max_dd": float(np.median(maxdds)),
        "p95_worst_dd": float(np.percentile(maxdds, 5)),
        "prob_loss": float((finals < initial).mean()),
        "prob_dd_gt_30": float((maxdds < -0.30).mean()),
        "histogram": {
            "counts": bins[0].tolist(),
            "edges": bins[1].tolist(),
        },
    }


def run_monte_carlo(
    trades: pd.DataFrame,
    n_sims: int = N_MC_SIMS,
    seed: int = MC_SEED,
    initial: float = INITIAL_EQUITY,
    contract_size: float = CONTRACT_SIZE,
) -> dict:
    if trades is None or trades.empty:
        return {"error": "no trades", "n": 0}

    pnls = trades["pnl"].to_numpy(float)
    n = len(pnls)
    rng = np.random.default_rng(seed)
    out: dict = {}

    order = np.argsort(rng.random((n_sims, n)), axis=1)
    seq = pnls[order]
    eq = initial + np.cumsum(seq, axis=1)
    eq = np.concatenate([np.full((n_sims, 1), initial), eq], axis=1)
    out["shuffle"] = _summarize(eq[:, -1], max_dd_matrix(eq), "shuffle", n_sims, initial)

    idx = rng.integers(0, n, size=(n_sims, n))
    seq = pnls[idx]
    eq = initial + np.cumsum(seq, axis=1)
    eq = np.concatenate([np.full((n_sims, 1), initial), eq], axis=1)
    out["bootstrap"] = _summarize(eq[:, -1], max_dd_matrix(eq), "bootstrap", n_sims, initial)

    noise = rng.normal(0.0, 0.10, size=(n_sims, n))
    seq = pnls * (1.0 + noise)
    eq = initial + np.cumsum(seq, axis=1)
    eq = np.concatenate([np.full((n_sims, 1), initial), eq], axis=1)
    out["perturb"] = _summarize(eq[:, -1], max_dd_matrix(eq), "perturb", n_sims, initial)

    extra = rng.uniform(0.0001, 0.0012, size=(n_sims, n))
    notionals = trades["entry"].to_numpy(float) * trades["lots"].to_numpy(float) * contract_size
    seq = pnls - extra * notionals
    eq = initial + np.cumsum(seq, axis=1)
    eq = np.concatenate([np.full((n_sims, 1), initial), eq], axis=1)
    out["slippage_mc"] = _summarize(eq[:, -1], max_dd_matrix(eq), "slippage_mc", n_sims, initial)
    return out


def evaluate_mc_pass(mc: dict, initial: float = INITIAL_EQUITY) -> bool:
    boot = mc.get("bootstrap", {})
    if not boot:
        return False
    return bool(boot.get("prob_loss", 1) < 0.15 and boot.get("median_final", 0) > initial)
