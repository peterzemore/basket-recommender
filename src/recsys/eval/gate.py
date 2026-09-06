"""Apply gates.toml to a results file. Returns the checks so the CLI can print them
and CI can fail on any that did not pass."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path


def load_results(path: Path) -> dict:
    return json.loads(path.read_text())


def served_model(results: dict) -> str:
    name = results.get("chosen_on_validation", {}).get("hybrid")
    if not name or name not in results["summaries"]:
        raise SystemExit("results carry no served (hybrid) model - run `recsys evaluate` first")
    return name


def run_gates(results: dict, gates: dict) -> list[dict]:
    name = served_model(results)
    s = results["summaries"][name]
    base = results["baseline"]
    lift = results["lift_vs_baseline"][name]["hit10"]["diff"]
    cold = s["segments"]["target"].get("cold", {}).get("hit10", 0.0)
    g = gates["served"]
    checks = [
        ("hit10", s["hit10"]["mean"], g["min_hit10"]),
        (f"lift over {base} (hit10, points)", lift, g["min_lift_hit10_over_baseline"]),
        ("cold-target hit10", cold, g["min_cold_hit10"]),
        ("coverage@10", s["coverage10"], g["min_coverage10"]),
        ("answered", s["answered"], g["min_answered"]),
        ("test queries", s["n_queries"], gates["protocol"]["min_test_queries"]),
    ]
    out = [{"check": c, "value": v, "min": m, "ok": v >= m} for c, v, m in checks]
    split = results["split"]
    for key in ("train_end", "val_end"):
        out.append({"check": f"protocol {key}", "value": split[key], "min": gates["protocol"][key],
                    "ok": split[key] == gates["protocol"][key]})
    return out


def drift(fresh: dict, committed: dict, tol: float = 1e-9) -> list[dict]:
    """Point estimates must match the committed file exactly - the run is seeded and the
    means do not depend on the bootstrap - so the numbers in the README are the numbers
    the code produces. Intervals are not compared."""
    out = []
    for name, s in fresh["summaries"].items():
        c = committed["summaries"].get(name)
        if c is None:
            out.append({"check": f"{name} present in committed results", "value": "missing", "min": "present", "ok": False})
            continue
        for metric in ("hit10", "ndcg10"):
            out.append({"check": f"{name} {metric} matches committed", "value": s[metric]["mean"],
                        "min": c[metric]["mean"], "ok": abs(s[metric]["mean"] - c[metric]["mean"]) <= tol})
    return out


def load_gates(path: Path) -> dict:
    return tomllib.loads(path.read_text())
