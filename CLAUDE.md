# basket-recommender — working notes

Read the README first; it is the source of truth for the protocol and the numbers.
This file is what a session needs that the README doesn't say.

## The rules that protect the numbers

- **Every number in the README is generated.** `recsys report --update-readme` rewrites
  the data table, `recsys evaluate --update-readme` rewrites the results block, between
  HTML-comment markers. Never hand-edit inside the markers.
- **CI re-runs the evaluation and fails on drift.** `results/test.json` is compared to a
  fresh run to nine decimals (point estimates only). If a code change legitimately
  moves a number: run `recsys evaluate --bootstrap 1000 --seed 0 --update-readme`, then
  commit `results/` and `README.md` **together**. Committing one without the other
  fails the `evaluate-and-gate` job by design.
- **Gates sit just under today's numbers, never above.** Raise a threshold in
  `gates.toml` only after the model already clears it. The protocol dates in
  `gates.toml` and the README must agree; changing the split is a deliberate edit to
  both, never a side effect.
- **Hyperparameters are chosen on validation only; test is scored once.** Don't re-run
  the sweep until a test number looks better. If a different blend is wanted (e.g.
  cold-first weights), that is a product decision to state, not a re-sweep.

## Things that are not obvious from the code

- The unit to learn on is the attribute, not the variant: the store buys 6–12 pieces
  per release, so history adds items rather than evidence per item. Content carries the
  ranking; item evidence is a boost. Don't "fix" the low id-model numbers.
- "Sold once" in the data table counts *orders containing the variant*, not units.
- The evaluation knows when an item existed, not whether it was in stock. Stock is a
  serving-time filter (`recsys/stock.py`), never a feature. Don't try to add it to the
  eval; there is no stock history to add.
- Many catalog items share identical feature vectors (same tags + price band), so the
  top of a list is often a tie block ordered by popularity. That's expected.
- `ROOT` resolves from the module path; when the package is pip-installed (the
  container) set `RECSYS_ROOT` to the directory holding `data/` and `results/`.
- Product titles legitimately contain `@` ("Only @ Target"); the leak test matches
  email *shapes*, not the character.

## Running it here

- `.venv/bin/recsys {pull,build,report,evaluate,gate,serve}`. `pull` needs an env file
  with `SHOPIFY_STORE`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET` (a read-only custom
  app); everything else runs from `data/public/` with no credentials.
- `build` takes `--exclude-emails` for the owner's own orders; the current exclusion
  list is in the milestone-1 commit message and in memory, not in the repo.
- `docker compose up` → dashboard on host port 8150 (8000 is taken by another service
  on this machine). A `shopify.env` next to `compose.yaml` (gitignored) turns on the
  live stock filter. The container survives reboots (`unless-stopped`).
- The dashboard is reached from the store over Tailscale, not the LAN, because this
  machine is at home. Docker publishes ports past `ufw`; don't assume the firewall
  covers 8150.
- Tests: `.venv/bin/pytest -q` (≈50). `tests/test_public_data.py` guards the committed
  snapshot's invariants on every push.

## Where this is going

Peter's preferred integration is the online cart, not the counter: nightly precompute
of each product's top picks → a product metafield via a **write-scoped custom app of
its own** (Ada's app stays read-only) → a pure-Liquid block above the checkout button
that keeps `variant.available` items and adds via `/cart/add` with a
`_suggested_by` line-item property so Ada can count attach rate. Check whether
Shopify's native "complementary products" metafield is API-writable before inventing a
custom one. A Shopify *app* only makes sense if this is ever sold to other stores.

## Shared with sell-through (2026-09-07)

`~/Projects/personal/sell-through` reads this repo's `data/raw/{products,orders}.jsonl` and the
local `shopify.env` (Ada's read-only app) for its cohort, live stock, and cost pulls. Do not move,
rename, or re-anonymize those without re-running sell-through's `build`. The public write-up for
this repo is `docs/writeup.md`, linked from the README; keep its numbers in step with the
results table.
