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
