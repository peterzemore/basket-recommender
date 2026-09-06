| Model | Hit@5 | Hit@10 [95% CI] | NDCG@10 | MRR | Answered | Coverage@10 | Novelty@10 |
|---|---|---|---|---|---|---|---|
| `popularity(hl=30d)` | 2.3% | 2.5% [1.4%, 3.7%] | 1.5% | 0.014 | 100.0% | 0.1% | 10.22 bits |
| `copurchase(min_support=3)` | 0.3% | 0.3% [0.0%, 1.1%] | 0.3% | 0.004 | 7.1% | 0.2% | 13.41 bits |
| `copurchase(min_support=1)` | 3.8% | 5.3% [3.0%, 7.9%] | 3.7% | 0.034 | 81.0% | 10.7% | 12.37 bits |
| `itemitem(cosine, shrink=5)` | 4.1% | 6.4% [3.7%, 9.6%] | 4.4% | 0.039 | 81.0% | 11.6% | 12.60 bits |
| `content_cosine` | 4.8% | 7.8% [4.6%, 11.8%] | 4.5% | 0.046 | 100.0% | 17.6% | 13.11 bits |
| `attr_cooccurrence(min_count=5)` | 2.0% | 3.5% [1.3%, 6.1%] | 2.3% | 0.026 | 100.0% | 12.8% | 13.01 bits |
| `hybrid(attr=1, content=1, item=0.5)` | 7.8% | 11.9% [8.3%, 15.7%] | 7.6% | 0.072 | 100.0% | 18.5% | 12.27 bits |

606 leave-one-out queries over 163 test baskets; 45.4% of targets are cold (never sold in the fitting window). Intervals are cluster bootstraps over baskets. *Answered* is the share of queries where the model gave any candidate a positive score; coverage and novelty are only meaningful when it is high.

**Lift over the production baseline (`copurchase(min_support=3)`)**

| Model | ΔHit@10 [95% CI] | ΔNDCG@10 [95% CI] | Distinguishable from baseline? |
|---|---|---|---|
| `popularity(hl=30d)` | +2.1 pts [+1.0, +3.5] | +1.2 pts [+0.2, +2.1] | yes |
| `copurchase(min_support=1)` | +5.0 pts [+2.7, +7.5] | +3.4 pts [+1.6, +5.3] | yes |
| `itemitem(cosine, shrink=5)` | +6.1 pts [+3.4, +9.1] | +4.0 pts [+2.1, +6.3] | yes |
| `content_cosine` | +7.4 pts [+4.2, +11.4] | +4.2 pts [+1.8, +7.0] | yes |
| `attr_cooccurrence(min_count=5)` | +3.1 pts [+1.1, +5.6] | +1.9 pts [+0.2, +4.1] | yes |
| `hybrid(attr=1, content=1, item=0.5)` | +11.6 pts [+8.0, +15.4] | +7.3 pts [+4.8, +10.3] | yes |

| Hit@10 by segment | target: warm (n=331) | target: cold (n=275) | source: pos (n=544) | source: online (n=62) | context: 1 item (n=138) | context: 2+ items (n=468) |
|---|---|---|---|---|---|---|
| `popularity(hl=30d)` | 4.5% | 0.0% | 2.4% | 3.2% | 5.8% | 1.5% |
| `copurchase(min_support=3)` | 0.6% | 0.0% | 0.4% | 0.0% | 0.0% | 0.4% |
| `copurchase(min_support=1)` | 9.7% | 0.0% | 3.7% | 19.4% | 2.9% | 6.0% |
| `itemitem(cosine, shrink=5)` | 11.8% | 0.0% | 4.6% | 22.6% | 2.9% | 7.5% |
| `content_cosine` | 5.1% | 10.9% | 7.5% | 9.7% | 11.6% | 6.6% |
| `attr_cooccurrence(min_count=5)` | 4.8% | 1.8% | 3.3% | 4.8% | 2.9% | 3.6% |
| `hybrid(attr=1, content=1, item=0.5)` | 16.0% | 6.9% | 10.5% | 24.2% | 10.9% | 12.2% |
