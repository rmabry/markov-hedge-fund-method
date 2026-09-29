# Regime signal information audit

Post-evaluation diagnostic; not an untouched holdout.

Validated baseline: `3d077ae7ce9b3ab0246f3962daf937331bc565fe`. Frozen observations only: 2020-2025; 20-bar simple returns, +/-5% regimes, minimum training 252 labels. No price acquisition or parameter search.

Input manifest SHA-256: `f18196b540cc0164e3fdbb039ca1c8798a9ba9152894c64e459af24229e509d6`. Source hashes and the original acquisition provenance are recorded in audit.json.

The question is whether the estimated transition probabilities changed the declared trading decisions. Identical decisions can coexist with better probability forecasts of regime labels.

## SPY

On these inspected dates the learned score was negative in Bear and positive in Sideways/Bull. Positive 20-bar momentum cannot be Bear under the +/-5% labels. The positive-score gate therefore vetoed no positive-momentum decisions and was empirically redundant for this policy. This sign pattern is observed, not guaranteed for other histories or future dates.

1508 decision dates; 1050 positive-momentum decisions; **0 filter vetoes**. Eligible unavailable scores: 0; ineligible: 0. Positive scores while momentum already held cash: 314 (these are not vetoes).

| State | Dates | Available | Momentum long | Positive / zero / negative scores | Min | Median | Max |
|---|---:|---:|---:|---|---:|---:|---:|
| Bear | 144 | 144 | 0 | 0 / 0 / 144 | -0.822917 | -0.801760 | -0.776316 |
| Sideways | 1103 | 1103 | 789 | 1103 / 0 / 0 | 0.003556 | 0.021407 | 0.027579 |
| Bull | 261 | 261 | 261 | 261 / 0 / 0 | 0.703583 | 0.736842 | 0.764706 |

Pre-evaluation decision (2019-12-31) identical: **True**. Full ledgers exactly identical at all 0/5/10/25 bps cost assumptions: **True**. Comparison includes the initial fill and final liquidation, not only rounded report metrics.

### Forecast diagnostics

Changed/unchanged labels are realized outcomes used only to explain forecast errors. All columns within each row use identical dates; summed multiclass Brier is lower when better.

| Realized next state | Observations | Adaptive Markov | Persistence | Historical frequency |
|---|---:|---:|---:|---:|
| unchanged | 1296 | 0.031710 | 0.000000 | 0.388967 |
| changed | 211 | 1.480000 | 2.000000 | 0.761318 |

A state-conditioned transition table fitted only before 2020 is held fixed throughout this diagnostic. It tests whether the ongoing updates improve on a fixed table, rather than only on an overconfident persistence forecast.

Matched dates: 1507; excluded due to missing frozen outgoing rows: 0. Adaptive-available opportunities: 1507/1507.

| Forecast on matched dates | Brier |
|---|---:|
| markov | 0.234490 |
| persistence | 0.280027 |
| historical_frequency | 0.441101 |
| frozen_development | 0.236227 |

## BTC-USD

On these inspected dates the learned score was negative in Bear and positive in Sideways/Bull. Positive 20-bar momentum cannot be Bear under the +/-5% labels. The positive-score gate therefore vetoed no positive-momentum decisions and was empirically redundant for this policy. This sign pattern is observed, not guaranteed for other histories or future dates.

2192 decision dates; 1205 positive-momentum decisions; **0 filter vetoes**. Eligible unavailable scores: 0; ineligible: 0. Positive scores while momentum already held cash: 420 (these are not vetoes).

| State | Dates | Available | Momentum long | Positive / zero / negative scores | Min | Median | Max |
|---|---:|---:|---:|---|---:|---:|---:|
| Bear | 567 | 567 | 0 | 0 / 0 / 567 | -0.880000 | -0.868829 | -0.856879 |
| Sideways | 789 | 789 | 369 | 789 / 0 / 0 | 0.010288 | 0.021672 | 0.034370 |
| Bull | 836 | 836 | 836 | 836 / 0 / 0 | 0.896069 | 0.902301 | 0.915976 |

Pre-evaluation decision (2019-12-31) identical: **True**. Full ledgers exactly identical at all 0/5/10/25 bps cost assumptions: **True**. Comparison includes the initial fill and final liquidation, not only rounded report metrics.

### Forecast diagnostics

Changed/unchanged labels are realized outcomes used only to explain forecast errors. All columns within each row use identical dates; summed multiclass Brier is lower when better.

| Realized next state | Observations | Adaptive Markov | Persistence | Historical frequency |
|---|---:|---:|---:|---:|
| unchanged | 1821 | 0.042838 | 0.000000 | 0.656728 |
| changed | 370 | 1.490185 | 2.000000 | 0.703554 |

A state-conditioned transition table fitted only before 2020 is held fixed throughout this diagnostic. It tests whether the ongoing updates improve on a fixed table, rather than only on an overconfident persistence forecast.

Matched dates: 2191; excluded due to missing frozen outgoing rows: 0. Adaptive-available opportunities: 2191/2191.

| Forecast on matched dates | Brier |
|---|---:|
| markov | 0.287255 |
| persistence | 0.337745 |
| historical_frequency | 0.664635 |
| frozen_development | 0.288114 |

## Interpretation limits

- The inspected 2020-2025 period is not an untouched holdout for selecting another rule.
- A lower regime Brier score does not establish a useful forecast of an executable price return.
- Regimes use overlapping trailing 20-bar returns; next-state persistence is partly mechanical.
- The frozen-development state-conditioned table is an added diagnostic, not a preregistered original comparator.
- No returns of newly selected strategies are evaluated here; no future profitability is established.
- Yahoo adjusted prices are retrospective and may contain later source revisions, not point-in-time vendor data.
