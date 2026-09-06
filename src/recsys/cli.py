"""`recsys` command line: pull (needs credentials), build (no credentials), report."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from recsys.data import PUBLIC_DIR, RAW_DIR, ROOT, load_env_file, read_jsonl, write_jsonl

README_START, README_END = "<!-- data-table:start -->", "<!-- data-table:end -->"


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
        pattern = re.compile(re.escape(README_START) + r".*?" + re.escape(README_END), re.S)
        if not pattern.search(text):
            print(f"README has no {README_START} / {README_END} markers", file=sys.stderr)
            return 1
        readme.write_text(pattern.sub(f"{README_START}\n{md}\n{README_END}", text))
        print("README table updated")
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
