# Next experiment: adaptive sizing versus frozen state sizing

Specification date: **2026-09-28**. Experiment ID: `adaptive-sizing-v1`.
Status: **specified, not started**. No new prices have been acquired for this
experiment. This document and its [machine-readable settings](next-experiment-v1.json)
must be committed before 2026-10-01 and before acquiring the new training dataset.
The initial snapshot and frozen model described below do not yet exist.

## One question

Does updating the Markov transition counts improve net returns over a frozen
state-conditioned sizing rule, when both rules already use the same momentum
signal and regime labels?

The inspected 2020-2025 experiment established that requiring a positive Markov
signal vetoed no momentum longs. Bull momentum was already positive, Bear momentum
was already negative, and the Sideways signal was always slightly positive. The
frozen pre-2020 transition rows also explain almost all of the forecast-score
improvement over a persistence forecast. These are retrospective findings. They
motivate testing **magnitude and updating**, with a control that already receives
the same current-state information.

This is one experiment with two primary policies, two fixed assets and one primary
cost assumption. Plain momentum is a descriptive reference. No alternative
thresholds, windows, horizons, universes or policy candidates will be selected.
**This new sizing rule has not been evaluated on the inspected 2015-2025 period;
do not run such an evaluation.** The additional 2026 initialization data is for
fitting the preregistered initial model, not for a performance rehearsal or tuning.

## Information boundary and dates

The research audit and this specification used only the frozen 2015-2025 prices.
No post-2025 price series was fetched or evaluated for this research work. This
does not claim that analysts have never encountered current market information;
it is not a reason to call already elapsed 2026 dates a pristine holdout.

| Purpose | Dates |
|---|---|
| Already inspected development evidence | 2015-01-01 through 2025-12-31 |
| Initial model input, acquired only after preregistration | 2015-01-01 through 2026-09-30 |
| Genuinely prospective evaluation | **2026-10-01 through 2027-09-30** |

Acquire and freeze the initial input only after both assets' 2026-09-30 daily bars
have completed, and before the first evaluation-period close or ingestion of any
evaluation-period prices. Treat daily bar dates in the source's asset-specific
calendar; the BTC bar completes at the following UTC midnight. If this launch
condition is missed, mark this experiment **not started**. Do not backdate it or
silently slide the evaluation window.

There is one terminal evaluation after both 2027-09-30 bars complete. No interim
performance inspection, winner selection, optional stopping or automatic
extension is allowed. Operational checks may inspect timestamps, missing rows,
data integrity and availability, but must not choose parameters or stopping dates
from realized performance. An inconclusive result requires a separately
preregistered follow-up, not an extension of this experiment.

## Data integrity and fixed estimator

Use SPY dividend/split-adjusted daily close and BTC-USD daily close from the same
Yahoo/yfinance source as v2. The initial training acquisition must be one
**contiguous, single-vintage** price history per asset through 2026-09-30. Do not
append newly adjusted 2026 SPY prices to the older adjusted-price snapshot: a
change in adjustment basis can create a false boundary return. Preserve the
existing v2 CSVs, manifest and results unchanged.

Freeze initial CSVs, their acquisition timestamps and source/adjustment metadata,
SHA-256 hashes, observed calendars, the frozen matrices, source commit and locked
dependency versions before evaluation begins. This is a paper research experiment,
with no orders or live trades.

For **every completed decision bar**, archive the full available price prefix from
2015-01-01 through that bar from a single as-of acquisition per asset. Normalize
SPY's entire prefix using that acquisition's coherent dividend/split-adjusted basis;
do not concatenate adjusted price levels from different vintages. Recompute the
adaptive labels and strict-prefix counts from that as-of history. `P_fixed` stays
frozen even when the vendor later revises history.

Record the source/raw and normalized prefix hashes, acquisition timestamp,
decision-bar date and completion timestamp, current regime, adaptive probabilities,
fixed-matrix hash, availability, all three targets, source commit, dependency
versions and decision-record timestamp. A decision record must be fixed **before
the next observed close at which it would fill**. In particular, the September 30
initialization decision must be recorded after its complete inputs exist and
before the first October 1 fill; do not retroactively invent this record after
seeing the fill or outcome price. Preserve previous forecasts and positions
unchanged. An end-of-year price download alone does not satisfy this prospective
experiment's evidence requirement.

Use coherent as-of **ratios**, not a splice of adjusted close levels, for scoring.
When observation `t` completes, calculate the return ending at that observation as
`C_t_in_vintage_t / C_previous_observation_in_vintage_t - 1`, with both prices taken
from the same archived full-prefix acquisition. Record that return and its two
source prices/vintage once; never revise an already scored return using a later
vintage. Feed the recorded return to the prospective self-financing ledger below,
using the previously recorded position. Compounding these recorded ratios creates
a coherent research return index despite adjusted-price rebasing. The v2 decision
delay and metric definitions are retained, but fractional execution costs and
turnover use the new accounting specified below. The future collector/runner must
accept recorded as-of returns rather than reconstruct them from mixed-vintage levels.

Report vendor historical value/label revisions separately from ordinary
dividend/split rebasing. Because adaptive counts use currently available historical
data while the control is frozen, any source revisions are part of the recorded
information change and limit attributing a benefit solely to additional transition
observations. No filling gaps or resampling calendars. Missing or late decisions
must be logged as unavailable, with zero target; never backfill a forecast. These
explicitly unavailable forecasts remain in cash and count against the 95% coverage
gate; they do not by themselves invalidate the run. Explain and resolve unexpected
missing/invalid price observations. Unresolved data defects, missing as-of evidence
for a **claimed available forecast or a scored return**, or reconstruction from
future data make the run inconclusive.

The regime model, forecast cutoff, decision delay and metric definitions are pinned
to v2 at commit `3d077ae7ce9b3ab0246f3962daf937331bc565fe`. The prospective
fractional-position cost accounting below is a new implementation requirement;
the source hash does not claim that the existing v2 ledger implements it.

- Window 20 observed bars; simple return `close[t] / close[t-20] - 1`.
- Bull above +5%, Bear below -5%, otherwise Sideways; equality within the v2
  numerical tolerance `1e-12` is Sideways. Exclude warm-up labels.
- Minimum 252 valid regime observations; expanding transition counts.
- At decision `t`, fit transitions strictly inside `labels[:t]`, ending before
  the current observation. Select the probability row using the known current state.
- Missing transition evidence means unavailable, never an invented probability.

Let `t0` be the 2026-09-30 observation. Freeze `P_fixed` using exactly the
strict-prefix matrix used by the adaptive policy for the decision at `t0`:
`build_transition_matrix(labels.loc[:t0].iloc[:-1])`. The snapshot includes the
September 30 close so its current label is known, but the final transition is
excluded from fitting under the existing convention. Both policies therefore
begin with identical matrix estimates. On the next decision the adaptive policy
can add the newly completed transition; `P_fixed` never changes. Do not refit the
frozen control on the final evaluation dataset.

## Policies and execution

Let `momentum[t] = 1` when the 20-bar simple return is positive, otherwise `0`.

```text
adaptive_score[t] = P_adaptive[t][current_state, Bull] - P_adaptive[t][current_state, Bear]
fixed_score[t] = P_fixed[current_state, Bull] - P_fixed[current_state, Bear]
adaptive_target[t] = momentum[t] * clip(adaptive_score[t], 0, 1)
fixed_target[t] = momentum[t] * clip(fixed_score[t], 0, 1)
reference_target[t] = momentum[t]
```

An unavailable score produces a zero target for that policy and is counted in
coverage. The estimated probability difference is a prescribed sizing input,
**not** a probability of profit or an established optimal capital allocation.

Retain the v2 timing: decide at close `t`, fill at close `t+1`, and earn the return
from `t+1` to `t+2`. Start flat immediately before the first evaluation close; the
September 30 decision may fill there, with no prior return credited. Liquidate at
the final close. Cash earns zero.

Apply the following **self-financing, drift-aware accounting to all three
policies**. A target is the desired risky-asset fraction of equity **after paying
that close's transaction costs**. A constant fractional target can require a trade
because the risky asset's return changes its weight relative to cash. Unlike the
v2 target-change approximation, this prospective ledger charges for that trade.
Preserve the frozen v2 implementation and results; do not recalculate them with
this new accounting.

At each evaluation close let `E_prev` be prior post-cost equity, `q_prev` its risky-asset
weight, `r` the newly observed same-vintage asset return, `q` the delayed target
being filled, and `c = cost_bps / 10000`. At the final close force `q = 0` instead
of opening a new position. The initial `E_prev = 1, q_prev = 0` ensures no prior
return is credited. For `E_prev > 0`, `r > -1`, `0 <= q_prev,q <= 1` and the
prescribed costs:

```text
E_before = E_prev * (1 + q_prev * r)
H_before = E_prev * q_prev * (1 + r)
weight_before = H_before / E_before

if q * E_before >= H_before:
    E_after = (E_before + c * H_before) / (1 + c * q)
else:
    E_after = (E_before - c * H_before) / (1 - c * q)

signed_traded_value = q * E_after - H_before
transaction_cost_value = c * abs(signed_traded_value)
turnover = abs(signed_traded_value) / E_before
gross_return = q_prev * r
cost_fraction_of_prior_equity = transaction_cost_value / E_prev
net_return = E_after / E_prev - 1
next_weight = q
```

The piecewise solution satisfies `E_after = E_before - transaction_cost_value`
without an external cash injection. Post-trade risky holdings are `q * E_after`
and cash is `(1-q) * E_after`. Zero cost reduces to the gross weighted-return
ledger. An unchanged target incurs costs when it differs from the drifted weight;
equal target and drifted weight incur none. Initial entry and terminal liquidation
use the same equations. Report turnover as the sum of traded value divided by
pretrade equity, rather than a sum of target-fraction changes. All other metric
definitions, including entry counts, use the resulting post-cost equity and
filled weights as specified in v2.

The primary cost is **10 bps**. Publish **0, 5 and 25 bps** sensitivity results
without using them to select the winner. No leverage, short positions, taxes or
additional borrowing/financing assumptions are introduced.

Before activation, a deterministic hand fixture must pass: prior equity `1`, prior
weight `0.5`, asset return `0.10`, unchanged target `0.5`, and cost rate `0.001`
give pretrade equity `1.05`, drifted weight `0.5238095238095238`, transaction cost
`1 / 39980 = 0.00002501250625312656`, and post-cost equity
`1.0499749874937469`. The existing target-change approximation would charge zero.
Also require cash/equity conservation, zero-cost equivalence, all-cash and fully
invested holding cases, nonnegative cash and holdings, entry/exit costs, delay and
terminal-liquidation tests. This is an
activation requirement for future code, not an implementation or market simulation
performed by this specification.

## Primary endpoint and fixed uncertainty procedure

Analyze each asset separately on its identical paired ledger dates. Keep all
periods, including cash, unavailable-score periods and initial/final costs:

```text
d[t] = adaptive_net_return[t] - fixed_net_return[t]
delta_annual_mean = periods_per_year * mean(d)
```

Use 252 periods/year for SPY and 365 for BTC. This endpoint is an annualized
**arithmetic mean return difference**, not CAGR or a pooled portfolio return.
Compute a separate paired circular moving-block bootstrap for each asset:

1. Block length: **20 consecutive observed periods**; resamples: **10,000**.
2. Generator: NumPy `Generator(PCG64(seed))`; SPY seed **2026092801**, BTC-USD seed
   **2026092802**. Record the locked NumPy version.
3. For each replicate with `n` original periods, draw `ceil(n / 20)` independent
   block starts uniformly from integers `0` through `n-1`. Each block takes 20
   consecutive indices modulo `n`. Concatenate and truncate to `n` indices.
4. Resample the paired differences using those indices and compute
   `periods_per_year * mean(resampled_d)`.
5. Report the 2.5th and 97.5th percentiles using NumPy's `method="linear"`:
   a two-sided **95% percentile interval**. The advancement rule uses its lower end.

Do not pool SPY and BTC observations or assume the assets are independent. Requiring
both separate tests to pass is an intersection requirement; neither asset can
compensate for the other. The block procedure addresses some serial dependence,
but its interval is approximate. One year supplies only about 12-18 nonoverlapping
20-observation blocks, and nonstationarity can invalidate nominal coverage. This
is not a formal power guarantee or proof of a durable trading edge.

## Adequacy gates and terminal classification

Evaluate these gates first, at the primary 10 bps cost:

- Both endpoints were completed without protocol deviation or unresolved data defects.
- At least **200 paired SPY return observations** and **300 paired BTC observations**.
- On at least **95%** of decision opportunities feeding fills before final
  liquidation, both policies have eligible, finite forecast rows. The September 30
  initialization decision is included; the final-close decision is not executed.
  Do not remove unavailable periods from the return comparison.
- For **each asset**, at least **40 filled-position observations** differ between
  adaptive and fixed by **0.01 or more** in absolute exposure. These observations
  must occur in at least **six distinct blocks of the fixed partition** into
  consecutive, nonoverlapping 20-observation blocks from the first evaluation row.
  Qualifying blocks need not be adjacent; the last partial block counts.

If any adequacy gate fails, classify the overall experiment **inconclusive** and
report the actual differences and availability. A nearly identical policy pair
has not provided a meaningful test of incremental sizing, even if a tiny estimated
effect has a narrow numerical interval. These variation gates are ex-ante practical
requirements, not a claim that their sample size guarantees statistical power.

Apply classification in this exact order: **adequacy failure -> inconclusive;
material shortfall or risk-limit failure -> do not advance; all advancement
conditions -> advance; otherwise -> inconclusive**. Specifically, after adequacy
passes, first classify **do not advance under this protocol** if any asset's
interval upper endpoint is **below 0.005**, or its drawdown deterioration exceeds
2 percentage points. This rejection takes precedence even if finite bootstrap
behavior would also satisfy an advancement inequality.

If not rejected, **advance to further research** only if every condition below
holds separately for **both** assets:

1. `delta_annual_mean >= 0.005`: at least **0.5 percentage points/year** improvement.
2. The paired bootstrap interval's lower endpoint is **strictly greater than zero**.
3. `max_drawdown_adaptive - max_drawdown_fixed >= -0.02`: net maximum drawdown
   deteriorates by no more than **2 percentage points**, including initial equity 1.

Otherwise classify **inconclusive**. Boundary equality at 0.005 is not a rejection;
a lower interval endpoint equal to zero is not acceptance.

The 0.5-point return hurdle and 2-point drawdown limit are deliberately fixed
research advancement criteria chosen before evaluation. They are not investor
preferences, investment advice, a risk guarantee or a profitability requirement
for the software release. Passing this experiment does not authorize live trading.

## Reporting and frozen references

Publish all primary results and intervals, adequacy counts, policy exposure
differences, coverage, turnover and entries. Also publish the v2 metrics (total
return, calendar CAGR, volatility, Sharpe and maximum drawdown) for adaptive,
frozen-state and plain momentum at all four costs. Calculate calendar CAGR with
365.2425 days/year. Secondary metrics and cost sensitivities cannot overturn the
primary terminal classification. Preserve an unfavorable or inactive result.

The self-financing ledger, numerical bootstrap and as-of runner are future work; this specification
does not fetch data, fit a new model, backtest the candidate or create a monitoring
automation. Before activation, check an implementation against deterministic
synthetic fixtures and have its chronology independently reviewed.

| Existing reference | SHA-256 |
|---|---|
| `scripts/markov_regime.py` | `08a6b2f84b569cfa36f59ad8cf160a3b3265e1d28d5cabd8e5423cdd420b8088` |
| `uv.lock` | `4c5424a79bdd76c9b3e290ec42e8e35e350e93ab740b1b73c3572a20d7008af8` |
| v2 manifest | `f18196b540cc0164e3fdbb039ca1c8798a9ba9152894c64e459af24229e509d6` |
| v2 SPY CSV | `37566ba5aa8df19b0e9fc61ad6db40c3fa87bf7ad6283fa6b42efcb8866f8a04` |
| v2 BTC-USD CSV | `234ec183c66f9301537493d86baf22ed95006ed6bb2537606c5942ccdbf129b9` |
