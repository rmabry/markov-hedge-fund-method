# Frozen regime research evaluation

Retrospective walk-forward evaluation: development 2015-2019; holdout 2020-2025. Fixed 20-observation simple returns, +/-5% regimes, 252-observation minimum training.

Decide at close t, fill at close t+1, earn t+1 to t+2. Start flat; liquidate at the final close. Cash earns zero. Costs are assumptions per unit of exposure change, including initial and final trades. SPY uses adjusted closes and 252 observations/year; BTC-USD uses closes and 365 observations/year for volatility and Sharpe. CAGR uses actual elapsed calendar time with 365.2425 days/year.

These policies are long/cash: buy-and-hold; positive 20-observation momentum; the same momentum gated by an available positive Markov signal. An unavailable signal means cash.

Snapshot acquired: 2026-09-28T04:59:17.444376+00:00. Manifest SHA-256: `f18196b540cc0164e3fdbb039ca1c8798a9ba9152894c64e459af24229e509d6`.

Profitability is not a release gate. The requirements are reproducibility, correct chronology, explicit unavailable evidence, and an honest comparison. Regime probabilities are not probabilities of a profitable trade. Adjusted historical prices may reflect later source revisions; this is a frozen retrospective dataset, not point-in-time vendor data.

## SPY

2020-01-02 to 2025-12-31; 1508 observations.

| Policy | Cost bps | Return | CAGR | Volatility | Sharpe | Max drawdown | Exposure | Turnover | Entries |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| buy_and_hold | 0 | 129.06% | 14.82% | 20.74% | 0.7719 | -33.72% | 99.93% | 2.0000 | 1 |
| buy_and_hold | 5 | 128.83% | 14.80% | 20.74% | 0.7711 | -33.72% | 99.93% | 2.0000 | 1 |
| buy_and_hold | 10 | 128.60% | 14.79% | 20.74% | 0.7703 | -33.72% | 99.93% | 2.0000 | 1 |
| buy_and_hold | 25 | 127.92% | 14.73% | 20.74% | 0.7678 | -33.72% | 99.93% | 2.0000 | 1 |
| momentum | 0 | 69.47% | 9.20% | 12.33% | 0.7770 | -20.58% | 69.56% | 116.0000 | 58 |
| momentum | 5 | 59.92% | 8.14% | 12.34% | 0.6979 | -21.37% | 69.56% | 116.0000 | 58 |
| momentum | 10 | 50.89% | 7.10% | 12.35% | 0.6187 | -22.16% | 69.56% | 116.0000 | 58 |
| momentum | 25 | 26.75% | 4.03% | 12.40% | 0.3815 | -24.49% | 69.56% | 116.0000 | 58 |
| filtered_momentum | 0 | 69.47% | 9.20% | 12.33% | 0.7770 | -20.58% | 69.56% | 116.0000 | 58 |
| filtered_momentum | 5 | 59.92% | 8.14% | 12.34% | 0.6979 | -21.37% | 69.56% | 116.0000 | 58 |
| filtered_momentum | 10 | 50.89% | 7.10% | 12.35% | 0.6187 | -22.16% | 69.56% | 116.0000 | 58 |
| filtered_momentum | 25 | 26.75% | 4.03% | 12.40% | 0.3815 | -24.49% | 69.56% | 116.0000 | 58 |

At the main **10 bps** assumption, filtered-minus-momentum return is 0.00% and max-drawdown difference is 0.00% (positive means a shallower drawdown).

The regime filter did not improve total return over the momentum baseline in this evaluation.

Forecast coverage: 1507/1507 (100.00%); 0 unavailable. All three Brier scores use the same available eligible dates; lower is better.

| Forecast | Multiclass Brier |
|---|---:|
| markov | 0.2345 |
| persistence | 0.2800 |
| historical_frequency | 0.4411 |

| Current state | Available / opportunities | Coverage |
|---|---:|---:|
| Bear | 144/144 | 100.00% |
| Sideways | 1102/1102 | 100.00% |
| Bull | 261/261 | 100.00% |

Snapshot unusually long observed calendar gaps: 0 (details in manifest).

## BTC-USD

2020-01-01 to 2025-12-31; 2192 observations.

| Policy | Cost bps | Return | CAGR | Volatility | Sharpe | Max drawdown | Exposure | Turnover | Entries |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| buy_and_hold | 0 | 1115.37% | 51.64% | 60.95% | 0.9927 | -76.63% | 99.95% | 2.0000 | 1 |
| buy_and_hold | 5 | 1114.15% | 51.62% | 60.95% | 0.9924 | -76.63% | 99.95% | 2.0000 | 1 |
| buy_and_hold | 10 | 1112.93% | 51.59% | 60.95% | 0.9921 | -76.63% | 99.95% | 2.0000 | 1 |
| buy_and_hold | 25 | 1109.27% | 51.52% | 60.95% | 0.9913 | -76.63% | 99.95% | 2.0000 | 1 |
| momentum | 0 | 864.72% | 45.92% | 41.90% | 1.1093 | -64.85% | 54.97% | 230.0000 | 115 |
| momentum | 5 | 759.61% | 43.14% | 41.91% | 1.0631 | -65.79% | 54.97% | 230.0000 | 115 |
| momentum | 10 | 665.92% | 40.41% | 41.93% | 1.0170 | -66.71% | 54.97% | 230.0000 | 115 |
| momentum | 25 | 441.58% | 32.53% | 42.00% | 0.8785 | -69.32% | 54.97% | 230.0000 | 115 |
| filtered_momentum | 0 | 864.72% | 45.92% | 41.90% | 1.1093 | -64.85% | 54.97% | 230.0000 | 115 |
| filtered_momentum | 5 | 759.61% | 43.14% | 41.91% | 1.0631 | -65.79% | 54.97% | 230.0000 | 115 |
| filtered_momentum | 10 | 665.92% | 40.41% | 41.93% | 1.0170 | -66.71% | 54.97% | 230.0000 | 115 |
| filtered_momentum | 25 | 441.58% | 32.53% | 42.00% | 0.8785 | -69.32% | 54.97% | 230.0000 | 115 |

At the main **10 bps** assumption, filtered-minus-momentum return is 0.00% and max-drawdown difference is 0.00% (positive means a shallower drawdown).

The regime filter did not improve total return over the momentum baseline in this evaluation.

Forecast coverage: 2191/2191 (100.00%); 0 unavailable. All three Brier scores use the same available eligible dates; lower is better.

| Forecast | Multiclass Brier |
|---|---:|
| markov | 0.2873 |
| persistence | 0.3377 |
| historical_frequency | 0.6646 |

| Current state | Available / opportunities | Coverage |
|---|---:|---:|
| Bear | 566/566 | 100.00% |
| Sideways | 789/789 | 100.00% |
| Bull | 836/836 | 100.00% |

Snapshot unusually long observed calendar gaps: 0 (details in manifest).

## Limits

No parameter search, live trades, leverage, short borrowing, taxes, or intraday fill simulation. The cost grid is a sensitivity analysis, not measured brokerage costs. Daily close-only prices cannot model intraday execution or market impact. This comparison does not validate continuous signal sizing or stationary-distribution risk sizing. Undefined metrics are null in JSON with an unavailable reason.
