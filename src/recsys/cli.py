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
    """Validation sweep picks each family's setting and the hybrid weights; one run on
    test with everything refit on train+validation; results written and, optionally,
    the README's results block replaced."""
    from itertools import product as iproduct

    from recsys.eval.index import Index
    from recsys.eval.queries import make_queries
    from recsys.eval.report import segment_table, sweep_table, test_table
    from recsys.eval.runner import lift, run, summarize, to_rows
    from recsys.eval.split import split_orders
    from recsys.features import build_features
    from recsys.models import AttributeCooccurrence, ContentCosine, CoPurchase, Hybrid, ItemItem, Popularity

    orders = list(read_jsonl(PUBLIC_DIR / "orders.jsonl"))
    products = list(read_jsonl(PUBLIC_DIR / "products.jsonl"))
    index = Index(orders, products)
    feats = build_features(products, index)
    train, val, test = split_orders(orders)
    out_dir = ROOT / "results"; out_dir.mkdir(exist_ok=True)

    def evaluate(model, queries, fit_set):
        return summarize(run(model, queries, index), index, Popularity().fit(fit_set, index).counts, args.bootstrap, args.seed)

    # --- validation sweep: fit on train, score on val --------------------------------
    families = {
        "popularity": [Popularity(hl) for hl in (None, 30, 90, 180)],
        "copurchase": [CoPurchase(ms, tb) for ms in (1, 2, 3) for tb in (False, True)],
        "itemitem": [ItemItem(sim, sh) for sim in ("cosine", "lift") for sh in (0.0, 2.0, 5.0, 20.0)],
        "content": [ContentCosine(feats)],
        "attr": [AttributeCooccurrence(feats, mc) for mc in (1, 2, 5, 10)],
    }
    val_q = make_queries(val, index)
    sweep, winners = [], {}
    for fam, cands in families.items():
        best = None
        for m in cands:
            m.fit(train, index)
            s_ = evaluate(m, val_q, train)
            sweep.append((m.name, s_))
            if best is None or s_["hit10"]["mean"] > best[1]["hit10"]["mean"]:
                best = (m, s_)
        winners[fam] = best
    item_fam = "itemitem" if winners["itemitem"][1]["hit10"]["mean"] >= winners["copurchase"][1]["hit10"]["mean"] else "copurchase"
    comps = {"attr": winners["attr"][0], "content": winners["content"][0], "item": winners[item_fam][0]}
    grid = [w for w in iproduct((0.0, 0.5, 1.0), repeat=3) if sum(w) > 0 and sum(1 for x in w if x > 0) > 1]
    best_h = None
    for wa, wc, wi in grid:
        h = Hybrid([(comps["attr"], wa), (comps["content"], wc), (comps["item"], wi)],
                   label=f"hybrid(attr={wa:g}, content={wc:g}, item={wi:g})").fit(train, index)
        s_ = evaluate(h, val_q, train)
        sweep.append((h.name, s_))
        if best_h is None or s_["hit10"]["mean"] > best_h[1]["hit10"]["mean"]:
            best_h = ((wa, wc, wi), s_, h.name)
    sweep_md_full = sweep_table(sweep)
    (out_dir / "val_sweep.md").write_text(sweep_md_full + "\n")
    shown = [(n, s_) for n, s_ in sweep if n in {w[0].name for w in winners.values()} or n == best_h[2]]
    sweep_md = sweep_table(shown) + f"\n\nAll {len(sweep)} validation rows, including the hybrid grid, are in [`results/val_sweep.md`](results/val_sweep.md)."

    # --- test: refit on train+val, score once ----------------------------------------
    fit_set = train + val
    def refit(m):
        return m.__class__(**_ctor_args(m)).fit(fit_set, index)
    baseline = CoPurchase(3, False).fit(fit_set, index)
    t_attr, t_content, t_item = refit(comps["attr"]), refit(comps["content"]), refit(comps["item"])
    wa, wc, wi = best_h[0]
    hybrid = Hybrid([(t_attr, wa), (t_content, wc), (t_item, wi)], label=best_h[2]).fit(fit_set, index)
    rows = [refit(winners["popularity"][0]), baseline, CoPurchase(1, False).fit(fit_set, index),
            t_item, t_content, t_attr, hybrid]
    uniq, names = [], set()
    for m in rows:
        if m.name not in names:
            uniq.append(m); names.add(m.name)
    test_q = make_queries(test, index)
    results = {m.name: run(m, test_q, index) for m in uniq}
    train_pop = Popularity().fit(fit_set, index).counts
    summaries = [(n, summarize(r, index, train_pop, args.bootstrap, args.seed)) for n, r in results.items()]
    lifts = {n: lift(r, results[baseline.name], args.bootstrap, args.seed) for n, r in results.items() if n != baseline.name}

    test_md = test_table(summaries, lifts, baseline.name) + "\n\n" + segment_table(summaries)
    (out_dir / "test.md").write_text(test_md + "\n")
    (out_dir / "test.json").write_text(json.dumps({
        "split": {"train_end": "2026-03-31", "val_end": "2026-05-31", "fit_for_test": "train+val"},
        "seed": args.seed, "bootstrap": args.bootstrap, "baseline": baseline.name,
        "chosen_on_validation": {fam: w[0].name for fam, w in winners.items()} | {"hybrid": best_h[2]},
        "summaries": dict(summaries), "lift_vs_baseline": lifts,
    }, indent=1) + "\n")
    (out_dir / "test_queries.jsonl").write_text("".join(
        json.dumps({"model": n, **row}) + "\n" for n, r in results.items() for row in to_rows(r)))
    print("## Validation sweep\n" + sweep_md + "\n\n## Test\n" + test_md)

    if args.update_readme:
        readme = ROOT / "README.md"
        body = ("**Chosen on validation** (fit on train, scored on Apr–May 2026; family winners and the best blend):\n\n" + sweep_md +
                "\n\n**Test** (fit on train+validation, scored once on Jun 2026 onward):\n\n" + test_md)
        readme.write_text(_replace_between(readme.read_text(), RESULTS_START, RESULTS_END, body))
        print("README results updated")
    return 0


def _ctor_args(m) -> dict:
    """Enough to rebuild a model with the same settings on a different fitting set."""
    from recsys.models import AttributeCooccurrence, ContentCosine, CoPurchase, ItemItem, Popularity
    if isinstance(m, Popularity):
        return {"half_life_days": m.half_life_days}
    if isinstance(m, CoPurchase):
        return {"min_support": m.min_support, "pop_tiebreak": m.pop_tiebreak}
    if isinstance(m, ItemItem):
        return {"similarity": m.similarity, "shrink": m.shrink}
    if isinstance(m, ContentCosine):
        return {"features": m.f}
    if isinstance(m, AttributeCooccurrence):
        return {"features": m.f, "min_count": m.min_count}
    raise TypeError(type(m))

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
