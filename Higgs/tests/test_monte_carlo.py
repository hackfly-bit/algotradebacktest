"""Monte Carlo engine tests."""

from __future__ import annotations

import pandas as pd

from engine.monte_carlo import evaluate_mc_pass, run_monte_carlo


def _trades(n: int = 20) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pnl": [50.0 if i % 3 else -20.0 for i in range(n)],
            "entry": [2000.0] * n,
            "lots": [0.1] * n,
        }
    )


def test_run_monte_carlo_four_modes():
    mc = run_monte_carlo(_trades(), n_sims=200, seed=42)
    assert "shuffle" in mc
    assert "bootstrap" in mc
    assert "perturb" in mc
    assert "slippage_mc" in mc
    boot = mc["bootstrap"]
    assert boot["n_sims"] == 200
    assert "histogram" in boot


def test_run_monte_carlo_empty_trades():
    mc = run_monte_carlo(pd.DataFrame(), n_sims=100)
    assert mc.get("error") == "no trades"


def test_evaluate_mc_pass():
    mc = {
        "bootstrap": {
            "prob_loss": 0.05,
            "median_final": 12_000.0,
        }
    }
    assert evaluate_mc_pass(mc, initial=10_000.0) is True
    mc_fail = {"bootstrap": {"prob_loss": 0.20, "median_final": 12_000.0}}
    assert evaluate_mc_pass(mc_fail, initial=10_000.0) is False
