import copy
import json

import pytest

from recsys.data import ROOT
from recsys.eval.gate import drift, load_gates, load_results, run_gates

RESULTS = ROOT / "results" / "test.json"
GATES = ROOT / "gates.toml"
pytestmark = pytest.mark.skipif(not RESULTS.exists(), reason="no results/test.json")


def test_committed_results_pass_the_gates():
    checks = run_gates(load_results(RESULTS), load_gates(GATES))
    assert all(c["ok"] for c in checks), [c for c in checks if not c["ok"]]


def test_an_injected_regression_fails_by_name():
    r = load_results(RESULTS)
    served = r["chosen_on_validation"]["hybrid"]
    r["summaries"][served]["segments"]["target"]["cold"]["hit10"] = 0.01
    failed = [c["check"] for c in run_gates(r, load_gates(GATES)) if not c["ok"]]
    assert failed == ["cold-target hit10"]


def test_a_changed_split_fails_the_protocol_gate():
    r = load_results(RESULTS)
    r["split"]["train_end"] = "2026-04-30"
    failed = [c["check"] for c in run_gates(r, load_gates(GATES)) if not c["ok"]]
    assert failed == ["protocol train_end"]


def test_drift_is_exact_and_catches_a_moved_number():
    r = load_results(RESULTS)
    assert all(c["ok"] for c in drift(r, copy.deepcopy(r)))
    moved = copy.deepcopy(r)
    name = next(iter(moved["summaries"]))
    moved["summaries"][name]["hit10"]["mean"] += 1e-6
    bad = [c for c in drift(r, moved) if not c["ok"]]
    assert len(bad) == 1 and bad[0]["check"].startswith(name)
