# basket-recommender

Item-to-item basket completion for a real retail store, with an offline evaluation
that is held to a protocol stated before any model was written.

The store is a Funko Pop shop with about a hundred orders a month. The data is its
actual order history, anonymized and committed to this repo, so the whole evaluation
runs from a clean clone with no credentials. Every number in this README is computed
from that snapshot by `recsys report`.

**Status: milestone 1 of 6 — the data pipeline.** There is no model yet. What exists
is the pull, the cleaning rules with their counts, the anonymization with tests that
guard it, and the dataset itself. The evaluation protocol below is a commitment, not
a result.

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

## Plan

1. **Data pipeline** — this milestone.
2. Evaluation harness with leakage tests; popularity and co-purchase baselines.
3. Item-item association, tag/price content similarity, and a hybrid with content
   backoff for cold items; ablation table.
4. FastAPI service, Docker image, `docker compose up` from a clean clone.
5. A dashboard a store owner would leave open: pick a product or a basket, see what
   each model suggests, see the evaluation.
6. Gate file and CI on the evaluation; publish.

## License

MIT
