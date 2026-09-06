# Dataset card

Anonymized order history and catalog for one retail store (Funko Pops, collectibles,
and related merchandise), produced by `recsys build` from a raw Shopify pull. The raw
pull is not committed.

## `orders.jsonl` — one basket per line

| Field | Type | Meaning |
|---|---|---|
| `order_id` | int | Sequential in date order; carries no relation to the store's order numbers |
| `date` | `YYYY-MM-DD` | Order creation date, day resolution; the split key |
| `source` | `pos` / `web` / `app` / `draft` / `other` | Sales channel. `app` is a sales-channel app id on this store's mobile app; `draft` is a staff-created order, kept because it is a real sale |
| `customer` | 16-hex string or `null` | Keyed HMAC of the customer id; stable within a snapshot, unlinkable to anything outside it. `null` when the sale had no customer attached (most in-store sales) |
| `items[]` | list | Distinct variants in the basket. Duplicate lines are merged |
| `items[].variant_id` | int | Shopify product-variant id — the unit the recommender ranks; joins to `products.jsonl` |
| `items[].product_id` | int | Parent product |
| `items[].title` | string | Line-item title as sold |
| `items[].quantity` | int ≥ 1 | Net of refunds |
| `items[].unit_price` | float or `null` | Discounted unit price paid |

## `products.jsonl` — one variant per line

| Field | Type | Meaning |
|---|---|---|
| `variant_id`, `product_id` | int | As above |
| `title` | string | Product title, with the variant title appended when it is not the default |
| `tags` | list of strings, sorted | The store's own tags: franchise, category, product line. The only structured content signal; `productType` is unused on this store |
| `price` | float | Current list price |
| `created_at` | `YYYY-MM-DD` | When the variant was created in the catalog — a listing date, not a first-sale date |
| `status` | `ACTIVE` / `ARCHIVED` / `DRAFT` | Catalog status at pull time |
| `image_url` | string or `null` | Public CDN URL of the product image |

## `clean_stats.json`

Per-rule counts from the last build. See the README for what each rule means.

## Caveats a model should respect

- Variants that no longer exist in the catalog do not appear in orders at all (the
  API returns no variant for them and the line is dropped), so every sold variant
  joins to the catalog by construction.
- `created_at` on a product is when it was listed, which can precede its first sale
  by a long time or, for items entered at the register, follow it by minutes.
- Quantities and prices reflect what was paid after discounts and refunds, which is
  the right signal for demand and the wrong one for list-price analysis.
- Nothing here identifies a person. The customer hash key is not in the repo.
