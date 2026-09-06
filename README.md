# basket-recommender

Item-to-item basket completion for a real retail store, with an offline evaluation
that is held to a protocol stated before any model was written.

The store is a Funko Pop shop with about a hundred orders a month. The data is its
actual order history, anonymized and committed to this repo, so the whole evaluation
runs from a clean clone with no credentials. Every number in this README is computed
from that snapshot by `recsys report`.

**Status: milestone 2 of 6 — the evaluation harness and two baselines.** The data
pipeline, the split, the candidate rules, the metrics, and the bootstrap all exist and
are tested; the models so far are popularity and co-purchase counts, and the numbers
are in [Results](#results). The protocol below was written before any of them.

## The data

<!-- data-table:start -->
| | |
|---|---|
| Orders | 2,653 over 25 months (2024-09-06 to 2026-09-05), median 95/month |
| Sales channel mix | pos 78%, web 11%, app 9%, draft 2% |
| Orders with a customer attached | 53% overall; 40% of in-store |
| Customers | 1,111 unique; 139 (13%) ordered twice or more; 15 ordered five or more times |
| Multi-item orders | 1,388 (52%); median 2 units per order |
| Distinct variants sold | 3,283; 61% appear in only one order |
| Top-20 variants | 6% of all units |
| Cold start (last 90 days) | 45% of line items are variants first sold inside that window |
| Catalog | 8,182 variants; 100% of sold variants still listed; tags on 99% (477 distinct) |
<!-- data-table:end -->

Three of those rows decided the design before any modelling:

- **13% repeat customers, 15 people with five or more orders.** There are no user
  histories to learn from, and in-store orders — 78% of the total — mostly have no
  customer attached at all. User-based collaborative filtering and user-item matrix
  factorization are ruled out by the data, not by preference. The problem is
  **basket completion**: given the items in front of a customer, rank the rest of the
  catalog. That framing serves a web cart, the store's app, and an in-store suggestion
  with one model.
- **61% of variants appear in exactly one order, and the top 20 sell 6% of units.**
  A popularity baseline will be weak here, and item-item co-occurrence will be sparse.
- **45% of recent line items are variants that had never sold before the last 90
  days.** New releases are most of what sells. A model that only knows item ids is
  blind to half the demand, so content features (tags cover 99% of the catalog, 477
  distinct) are the core of the cold-start path, not a refinement.

## What was cleaned out, and how much

Counts are written to [`data/public/clean_stats.json`](data/public/clean_stats.json)
on every build.

| Rule | Dropped | Why |
|---|---:|---|
| Cancelled orders | 76 orders | Never fulfilled |
| The owner's own orders | 4 orders | Test purchases, not demand |
| Fully refunded line items | 71 lines | Returned; partial refunds reduce quantity instead (13 lines) |
| Line items with no variant | 632 lines (9%) | POS tips, hand-typed custom sales, and products deleted since the sale |
| Orders with nothing left after the above | 225 orders | Baskets made entirely of the previous row |
| Duplicate variant lines within an order | 27 merged | Same item rung up twice |

The last two rows are the honest cost of this dataset: about 9% of line items and
8% of orders are gone because the product no longer exists in the catalog, so the
"still listed" figure in the table above is true by construction, not a finding.

## Anonymization

What survives: variant and product ids (public catalog identifiers), titles, tags,
prices, quantities net of refunds, the order date to the day, and a coarse sales
channel (`pos`, `web`, `app`, `draft`, `other`). Customers are a keyed hash — repeat
purchases stay linkable, the id does not survive, and the key lives outside the
repo. What does not survive: emails, names, order numbers, timestamps, and anything
else the API returned.

[`tests/test_public_data.py`](tests/test_public_data.py) asserts these invariants
against the committed snapshot on every push, so a rebuild that leaked a field
fails CI. Field-level documentation is in [`data/public/DATASET.md`](data/public/DATASET.md).

## Reproduce

```bash
git clone https://github.com/peterzemore/basket-recommender.git && cd basket-recommender
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/recsys report            # the table above, from data/public/
```

Refreshing the snapshot needs a Shopify custom app with `read_orders` and
`read_products` and an env file carrying `SHOPIFY_STORE`, `SHOPIFY_CLIENT_ID`,
`SHOPIFY_CLIENT_SECRET`:

```bash
.venv/bin/pip install -e ".[pull]"
.venv/bin/recsys pull --env-file /path/to/shopify.env --lookback-days 730
.venv/bin/recsys build --exclude-emails owner@example.com
.venv/bin/recsys report --update-readme
```

## The evaluation protocol, stated in advance

These are the rules the results in later milestones will be held to. They are
written down now so they cannot be adjusted to fit a number.

- **Time-based split, never random.** Train through 2026-03, validate on
  2026-04 to 2026-05, test on 2026-06 onward. A random split leaks future
  baskets into training and overstates every model.
- **Leave-one-out per test basket.** For each test basket with two or more distinct
  variants, hide one item, present the rest, rank the catalog.
- **Candidates are restricted to variants that existed before the basket's date.**
  No recommending an item that had not been released yet.
- **Metrics:** Hit@5, Hit@10, NDCG@10, MRR — and **catalog coverage** and
  **novelty**, because a model that only ever suggests the twenty best-sellers scores
  respectably on hit rate and is useless in a store.
- **Segments reported separately:** cold vs warm target item, in-store vs online,
  one-item vs multi-item context.
- **Bootstrap confidence intervals** over baskets. A difference inside the interval
  is reported as not distinguishable, not as a win.
- **Production baseline:** the store already runs a co-purchase-count analysis in
  production. It is model #2, and it is the number to beat.

Expected honestly: on roughly five hundred test baskets over a three-thousand-item
long tail, absolute Hit@10 will be modest. The result of interest is lift over the
production baseline and behavior on cold items.

## Results

Milestone 2 adds the evaluation harness and the two baselines. Everything below is
written by `recsys evaluate` and regenerated from `data/public/` with a fixed seed;
per-query records are in [`results/test_queries.jsonl`](results/test_queries.jsonl).

Hyperparameters were chosen on the validation window only. Test was scored once,
after the choice, with the models refit on train+validation. The production
setting of the co-purchase baseline (`min_support=3`) is always reported as-is,
whatever validation preferred.

<!-- results:start -->
**Chosen on validation** (fit on train, scored on Apr–May 2026):

| Model (fit on train, scored on validation) | Hit@10 [95% CI] | NDCG@10 | Answered | queries (cold targets) |
|---|---|---|---|---:|
| `popularity` | 1.8% [0.7%, 3.1%] | 1.2% | 100.0% | 398 (40.5%) |
| `popularity(hl=30d)` | 3.8% [1.7%, 6.0%] | 1.7% | 100.0% | 398 (40.5%) |
| `popularity(hl=90d)` | 2.0% [0.7%, 3.5%] | 1.3% | 100.0% | 398 (40.5%) |
| `popularity(hl=180d)` | 2.0% [0.7%, 3.5%] | 1.3% | 100.0% | 398 (40.5%) |
| `copurchase(min_support=1)` | 10.3% [6.6%, 14.6%] | 6.1% | 79.9% | 398 (40.5%) |
| `copurchase(min_support=1)+pop` | 9.5% [6.1%, 13.6%] | 6.8% | 100.0% | 398 (40.5%) |
| `copurchase(min_support=2)` | 5.3% [2.5%, 8.6%] | 4.2% | 25.4% | 398 (40.5%) |
| `copurchase(min_support=2)+pop` | 6.8% [3.8%, 10.1%] | 5.7% | 100.0% | 398 (40.5%) |
| `copurchase(min_support=3)` | 1.3% [0.0%, 3.3%] | 0.9% | 3.0% | 398 (40.5%) |
| `copurchase(min_support=3)+pop` | 2.8% [1.0%, 5.1%] | 2.1% | 100.0% | 398 (40.5%) |

**Test** (fit on train+validation, scored once on Jun 2026 onward):

| Model | Hit@5 | Hit@10 [95% CI] | NDCG@10 | MRR | Answered | Coverage@10 | Novelty@10 |
|---|---|---|---|---|---|---|---|
| `popularity` | 1.8% | 2.0% [0.9%, 3.1%] | 1.4% | 0.013 | 100.0% | 0.1% | 9.27 bits |
| `popularity(hl=30d)` | 2.3% | 2.5% [1.4%, 3.7%] | 1.5% | 0.014 | 100.0% | 0.1% | 10.22 bits |
| `copurchase(min_support=3)` | 0.3% | 0.3% [0.0%, 1.1%] | 0.3% | 0.004 | 7.1% | 0.2% | 13.41 bits |
| `copurchase(min_support=1)` | 3.8% | 5.3% [3.0%, 7.9%] | 3.7% | 0.034 | 81.0% | 10.7% | 12.37 bits |

606 leave-one-out queries over 163 test baskets; 45.4% of targets are cold (never sold in the fitting window). Intervals are cluster bootstraps over baskets. *Answered* is the share of queries where the model gave any candidate a positive score; coverage and novelty are only meaningful when it is high.

**Lift over the production baseline (`copurchase(min_support=3)`)**

| Model | ΔHit@10 [95% CI] | ΔNDCG@10 [95% CI] | Distinguishable from baseline? |
|---|---|---|---|
| `popularity` | +1.7 pts [+0.3, +3.0] | +1.0 pts [-0.1, +2.1] | yes |
| `popularity(hl=30d)` | +2.1 pts [+1.0, +3.5] | +1.2 pts [+0.2, +2.1] | yes |
| `copurchase(min_support=1)` | +5.0 pts [+2.7, +7.5] | +3.4 pts [+1.6, +5.3] | yes |

| Hit@10 by segment | target: warm (n=331) | target: cold (n=275) | source: pos (n=544) | source: online (n=62) | context: 1 item (n=138) | context: 2+ items (n=468) |
|---|---|---|---|---|---|---|
| `popularity` | 3.6% | 0.0% | 2.2% | 0.0% | 1.4% | 2.1% |
| `popularity(hl=30d)` | 4.5% | 0.0% | 2.4% | 3.2% | 5.8% | 1.5% |
| `copurchase(min_support=3)` | 0.6% | 0.0% | 0.4% | 0.0% | 0.0% | 0.4% |
| `copurchase(min_support=1)` | 9.7% | 0.0% | 3.7% | 19.4% | 2.9% | 6.0% |
<!-- results:end -->

### What the baselines say

- **The production analysis is not a recommender.** With `min_support=3` it has
  something to say on 7% of queries and lands the hidden item in its top ten 0.3%
  of the time. That is not a criticism of the analysis — it was built to
  surface recurring bundles for a human, and it does — but it means the store's
  existing number is a floor, not a bar.
- **Dropping the support threshold is the whole gain so far.** Plain pair counts
  with `min_support=1` reach 5.3% Hit@10 [3.0%, 7.9%] on test, distinguishable from
  the baseline, and 19% on online orders (n=62, so a wide interval). On this
  little data, every pair is evidence.
- **Every model scores exactly 0.0% on cold targets, and cold targets are 45% of
  test queries.** An item that never sold in the fitting window cannot be ranked by
  its id, so it sits in the middle of a tie block thousands wide. Nearly half of
  what the store sells is invisible to everything in this table. That number is
  the case for milestone 3, and it was measured rather than assumed.
- **Validation flattered co-purchase.** It scored 10.3% on Apr–May and 5.3% on
  Jun onward. Cold targets are 40% of validation queries and 45% of test queries,
  and the test window's warm baskets are further from the fitting data. The gap
  is reported rather than tuned away.

How to read the ties: a popularity model gives thousands of long-tail variants the
same score. The rank used is the *expected* rank under random tie-breaking — one
plus the candidates scored strictly higher, plus half of those tied — so a model
is neither flattered nor punished for emitting ties.

## Plan

1. **Data pipeline** — done.
2. **Evaluation harness with leakage tests; popularity and co-purchase baselines** — done.
3. Item-item association, tag/price content similarity, and a hybrid with content
   backoff for cold items; ablation table.
4. FastAPI service, Docker image, `docker compose up` from a clean clone.
5. A dashboard a store owner would leave open: pick a product or a basket, see what
   each model suggests, see the evaluation.
6. Gate file and CI on the evaluation; publish.

## License

MIT
