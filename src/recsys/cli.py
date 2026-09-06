"""`recsys` command line: pull (needs credentials), build (no credentials), report."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from recsys.data import PUBLIC_DIR, RAW_DIR, ROOT, load_env_file, read_jsonl, write_jsonl

README_START, README_END = "<!-- data-table:start -->", "<!-- data-table:end -->"
RESULTS_START, RESULTS_END = "<!-- results:start -->", "<!-- results:end -->"


def _replace_between(text: str, start: str, end: str, body: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise SystemExit(f"README has no {start} / {end} markers")
    return pattern.sub(f"{start}\n{body}\n{end}", text)


def cmd_pull(args) -> int:
    from recsys.data.shopify import ShopifyAdmin, fetch_orders, fetch_products
    api = ShopifyAdmin.from_env(load_env_file(Path(args.env_file)))
    orders = fetch_orders(api, args.lookback_days)
    n_o = write_jsonl(RAW_DIR / "orders.jsonl", orders)
    products = fetch_products(api)
    n_p = write_jsonl(RAW_DIR / "products.jsonl", products)
    print(f"pulled {n_o} orders and {n_p} products into {RAW_DIR.relative_to(ROOT)}/")
    return 0


def cmd_build(args) -> int:
    from recsys.data.anonymize import anonymize_orders, flatten_products, load_or_create_salt
    from recsys.data.clean import clean_orders
    raw_orders = list(read_jsonl(RAW_DIR / "orders.jsonl"))
    raw_products = list(read_jsonl(RAW_DIR / "products.jsonl"))
    exclude = {e.strip() for e in (args.exclude_emails or "").split(",") if e.strip()}
    kept, stats = clean_orders(raw_orders, exclude)
    salt = load_or_create_salt(RAW_DIR / "anon_salt.txt")
    n_o = write_jsonl(PUBLIC_DIR / "orders.jsonl", anonymize_orders(kept, salt))
    n_p = write_jsonl(PUBLIC_DIR / "products.jsonl", flatten_products(raw_products))
    (PUBLIC_DIR / "clean_stats.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(json.dumps(stats, indent=2, sort_keys=True))
    print(f"wrote {n_o} orders and {n_p} variants to {PUBLIC_DIR.relative_to(ROOT)}/")
    return 0


def cmd_report(args) -> int:
    from recsys.data.report import compute, to_markdown
    stats = compute(list(read_jsonl(PUBLIC_DIR / "orders.jsonl")), list(read_jsonl(PUBLIC_DIR / "products.jsonl")))
    md = to_markdown(stats)
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(md)
    if args.update_readme:
        readme = ROOT / "README.md"
        text = readme.read_text()
        readme.write_text(_replace_between(text, README_START, README_END, md))
        print("README table updated")
    return 0


def cmd_evaluate(args) -> int:
    """Validation sweep picks each family's setting; one run on test; results written."""
    from recsys.eval.index import Index
    from recsys.eval.queries import make_queries
    from recsys.eval.report import segment_table, sweep_table, test_table
    from recsys.eval.runner import lift, run, summarize, to_rows
    from recsys.eval.split import split_orders
    from recsys.models import CoPurchase, Popularity

    orders = list(read_jsonl(PUBLIC_DIR / "orders.jsonl"))
    products = list(read_jsonl(PUBLIC_DIR / "products.jsonl"))
    index = Index(orders, products)
    train, val, test = split_orders(orders)
    out_dir = ROOT / "results"; out_dir.mkdir(exist_ok=True)

    # --- validation sweep: fit on train, score on val ---------------------------------
    families = {
        "popularity": [Popularity(hl) for hl in (None, 30, 90, 180)],
        "copurchase": [CoPurchase(ms, tb) for ms in (1, 2, 3) for tb in (False, True)],
    }
    val_q = make_queries(val, index)
    sweep, chosen = [], {}
    for fam, cands in families.items():
        best = None
        for m in cands:
            m.fit(train, index)
            s = summarize(run(m, val_q, index), index, Popularity().fit(train, index).counts, args.bootstrap, args.seed)
            sweep.append((m.name, s))
            if best is None or s["hit10"]["mean"] > best[1]:
                best = (m, s["hit10"]["mean"])
        chosen[fam] = best[0]
    sweep_md = sweep_table(sweep)
    (out_dir / "val_sweep.md").write_text(sweep_md + "\n")

    # --- test: refit the chosen settings on train+val, score once ----------------------
    fit_set = train + val
    baseline = CoPurchase(3, False).fit(fit_set, index)          # the production setting, as-is
    models = [Popularity().fit(fit_set, index), chosen["popularity"].__class__(chosen["popularity"].half_life_days).fit(fit_set, index),
              baseline, CoPurchase(chosen["copurchase"].min_support, chosen["copurchase"].pop_tiebreak).fit(fit_set, index)]
    seen_names, uniq = set(), []
    for m in models:
        if m.name not in seen_names:
            uniq.append(m); seen_names.add(m.name)
    test_q = make_queries(test, index)
    train_pop = Popularity().fit(fit_set, index).counts
    results = {m.name: run(m, test_q, index) for m in uniq}
    summaries = [(name, summarize(r, index, train_pop, args.bootstrap, args.seed)) for name, r in results.items()]
    lifts = {name: lift(r, results[baseline.name], args.bootstrap, args.seed) for name, r in results.items() if name != baseline.name}

    test_md = test_table(summaries, lifts, baseline.name) + "\n\n" + segment_table(summaries)
    (out_dir / "test.md").write_text(test_md + "\n")
    (out_dir / "test.json").write_text(json.dumps({
        "split": {"train_end": "2026-03-31", "val_end": "2026-05-31", "fit_for_test": "train+val"},
        "seed": args.seed, "bootstrap": args.bootstrap, "baseline": baseline.name,
        "summaries": dict(summaries), "lift_vs_baseline": lifts,
    }, indent=1) + "\n")
    (out_dir / "test_queries.jsonl").write_text("".join(
        json.dumps({"model": name, **row}) + "\n" for name, r in results.items() for row in to_rows(r)))
    print("## Validation sweep\n" + sweep_md + "\n\n## Test\n" + test_md)

    if args.update_readme:
        readme = ROOT / "README.md"
        body = ("**Chosen on validation** (fit on train, scored on Apr–May 2026):\n\n" + sweep_md +
                "\n\n**Test** (fit on train+validation, scored once on Jun 2026 onward):\n\n" + test_md)
        readme.write_text(_replace_between(readme.read_text(), RESULTS_START, RESULTS_END, body))
        print("README results updated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recsys")
    sub = p.add_subparsers(dest="command", required=True)

    pull = sub.add_parser("pull", help="fetch raw orders + catalog from Shopify (needs credentials)")
    pull.add_argument("--env-file", required=True, help="file with SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET")
    pull.add_argument("--lookback-days", type=int, default=730)
    pull.set_defaults(func=cmd_pull)

    build = sub.add_parser("build", help="clean + anonymize data/raw into data/public")
    build.add_argument("--exclude-emails", help="comma-separated order emails to drop (e.g. the owner's)")
    build.set_defaults(func=cmd_build)

    rep = sub.add_parser("report", help="print the data table from data/public")
    rep.add_argument("--json", action="store_true")
    rep.add_argument("--update-readme", action="store_true", help="rewrite the table between the README markers")
    rep.set_defaults(func=cmd_report)

    ev = sub.add_parser("evaluate", help="validation sweep + one test run, from data/public")
    ev.add_argument("--bootstrap", type=int, default=1000)
    ev.add_argument("--seed", type=int, default=0)
    ev.add_argument("--update-readme", action="store_true")
    ev.set_defaults(func=cmd_evaluate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
