"""Markdown for the results. Every number comes with its interval."""
from __future__ import annotations


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _ci(d: dict, key: str = "mean") -> str:
    return f"{_pct(d[key])} [{_pct(d['lo'])}, {_pct(d['hi'])}]"


def sweep_table(rows: list[tuple[str, dict]]) -> str:
    out = ["| Model (fit on train, scored on validation) | Hit@10 [95% CI] | NDCG@10 | Answered | queries (cold targets) |", "|---|---|---|---|---:|"]
    for name, s in rows:
        out.append(f"| `{name}` | {_ci(s['hit10'])} | {_pct(s['ndcg10']['mean'])} | {_pct(s['answered'])} "
                   f"| {s['n_queries']} ({_pct(s['cold_share'])}) |")
    return "\n".join(out)


def test_table(rows: list[tuple[str, dict]], lifts: dict[str, dict], baseline: str) -> str:
    out = ["| Model | Hit@5 | Hit@10 [95% CI] | NDCG@10 | MRR | Answered | Coverage@10 | Novelty@10 |", "|---|---|---|---|---|---|---|---|"]
    for name, s in rows:
        out.append(f"| `{name}` | {_pct(s['hit5']['mean'])} | {_ci(s['hit10'])} | {_pct(s['ndcg10']['mean'])} "
                   f"| {s['rr']['mean']:.3f} | {_pct(s['answered'])} | {_pct(s['coverage10'])} | {s['novelty10']:.2f} bits |")
    n = rows[0][1]
    out.append(f"\n{n['n_queries']} leave-one-out queries over {n['n_baskets']} test baskets; "
               f"{_pct(n['cold_share'])} of targets are cold (never sold in the fitting window). "
               "Intervals are cluster bootstraps over baskets. *Answered* is the share of queries where the "
               "model gave any candidate a positive score; coverage and novelty are only meaningful when it is high.")
    out.append(f"\n**Lift over the production baseline (`{baseline}`)**\n")
    out.append("| Model | ΔHit@10 [95% CI] | ΔNDCG@10 [95% CI] | Distinguishable from baseline? |")
    out.append("|---|---|---|---|")
    for name, l in lifts.items():
        h, g = l["hit10"], l["ndcg10"]
        dist = "yes" if (h["distinguishable"] or g["distinguishable"]) else "no"
        out.append(f"| `{name}` | {100*h['diff']:+.1f} pts [{100*h['lo']:+.1f}, {100*h['hi']:+.1f}] "
                   f"| {100*g['diff']:+.1f} pts [{100*g['lo']:+.1f}, {100*g['hi']:+.1f}] | {dist} |")
    return "\n".join(out)


def segment_table(rows: list[tuple[str, dict]]) -> str:
    groups = rows[0][1]["segments"]
    labels = [(g, l) for g in groups for l in groups[g]]
    head = " | ".join(f"{g}: {l} (n={groups[g][l]['n']})" for g, l in labels)
    out = [f"| Hit@10 by segment | {head} |", "|---|" + "---|" * len(labels)]
    for name, s in rows:
        cells = " | ".join(_pct(s["segments"][g][l]["hit10"]) if l in s["segments"][g] else "–" for g, l in labels)
        out.append(f"| `{name}` | {cells} |")
    return "\n".join(out)
