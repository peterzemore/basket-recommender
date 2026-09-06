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
