"""Decision gate tests."""

from __future__ import annotations

from engine.decision_gate import evaluate_decision_gate, evaluate_is_pass, evaluate_oos_pass


def test_is_pass_threshold():
    assert evaluate_is_pass({"sharpe": 1.1, "trades": 30}) is True
    assert evaluate_is_pass({"sharpe": 0.9, "trades": 30}) is False
    assert evaluate_is_pass({"sharpe": 1.1, "trades": 29}) is False


def test_oos_pass_threshold():
    assert evaluate_oos_pass({"sharpe": 0.9, "total_return": 0.01, "trades": 10}) is True
    assert evaluate_oos_pass({"sharpe": 0.7, "total_return": 0.01, "trades": 10}) is False


def test_gate_status_robust():
    gate = evaluate_decision_gate(
        is_metrics={"sharpe": 1.2, "trades": 40},
        oos_metrics={"sharpe": 1.0, "total_return": 0.05, "trades": 15},
        wf_pass=True,
        param_stable=True,
        perturb_stable=True,
        cost_pass=True,
        mc_pass=True,
    )
    assert gate.status == "ROBUST"
    assert gate.implement_mql5 is True
    assert gate.n_pass == 6


def test_gate_status_fail_on_oos():
    gate = evaluate_decision_gate(
        is_metrics={"sharpe": 1.2, "trades": 40},
        oos_metrics={"sharpe": 0.5, "total_return": -0.01, "trades": 15},
        wf_pass=True,
        param_stable=True,
        perturb_stable=True,
        cost_pass=True,
        mc_pass=True,
    )
    assert gate.status == "FAIL"
    assert gate.implement_mql5 is False


def test_gate_status_acceptable():
    gate = evaluate_decision_gate(
        is_metrics={"sharpe": 1.2, "trades": 40},
        oos_metrics={"sharpe": 1.0, "total_return": 0.05, "trades": 15},
        wf_pass=True,
        param_stable=True,
        perturb_stable=False,
        cost_pass=True,
        mc_pass=False,
    )
    assert gate.status == "ACCEPTABLE"
    assert gate.n_pass == 4
