"""Decision gate for strategy acceptance. Do not import Django."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    in_sample: bool
    out_of_sample: bool
    walk_forward: bool
    parameter_stability: bool
    cost_stress: bool
    monte_carlo: bool
    status: str
    implement_mql5: bool
    n_pass: int


def evaluate_is_pass(metrics: dict) -> bool:
    return float(metrics.get("sharpe") or 0) > 1.0 and int(metrics.get("trades") or 0) >= 30


def evaluate_oos_pass(metrics: dict) -> bool:
    return (
        float(metrics.get("sharpe") or 0) > 0.8
        and float(metrics.get("total_return") or 0) > 0
        and int(metrics.get("trades") or 0) >= 10
    )


def evaluate_decision_gate(
    *,
    is_metrics: dict,
    oos_metrics: dict,
    wf_pass: bool,
    param_stable: bool,
    perturb_stable: bool,
    cost_pass: bool,
    mc_pass: bool,
) -> GateResult:
    is_pass = evaluate_is_pass(is_metrics)
    oos_pass = evaluate_oos_pass(oos_metrics)
    gates = {
        "in_sample": is_pass,
        "out_of_sample": oos_pass,
        "walk_forward": wf_pass,
        "parameter_stability": param_stable and perturb_stable,
        "cost_stress": cost_pass,
        "monte_carlo": mc_pass,
    }
    n_pass = sum(bool(v) for v in gates.values())

    oos_return = float(oos_metrics.get("total_return") or 0)
    if not oos_pass or oos_return <= 0:
        status = "FAIL"
    elif n_pass == 6:
        status = "ROBUST"
    elif n_pass >= 4 and oos_pass:
        status = "ACCEPTABLE"
    else:
        status = "FRAGILE"

    implement = status in {"ROBUST", "ACCEPTABLE"}
    return GateResult(
        in_sample=gates["in_sample"],
        out_of_sample=gates["out_of_sample"],
        walk_forward=gates["walk_forward"],
        parameter_stability=gates["parameter_stability"],
        cost_stress=gates["cost_stress"],
        monte_carlo=gates["monte_carlo"],
        status=status,
        implement_mql5=implement,
        n_pass=n_pass,
    )
