---
name: regime
description: >-
  Analyze Bull, Bear, and Sideways regimes from ticker or CSV prices using a
  validated observable Markov contract, explicit missing-evidence handling,
  n-step forecasts, and a causal historical backtest. Use for regime analysis
  and research integrations. Framework by Roan (@RohOnChain).
---

# Regime analysis — v2

Use the maintained script and its adjacent lockfile:

```bash
uv run --locked --script "${CLAUDE_PLUGIN_ROOT}/scripts/markov_regime.py" --ticker SPY --json --no-hmm
uv run --locked --script "${CLAUDE_PLUGIN_ROOT}/scripts/markov_regime.py" --csv my_prices.csv --horizon 5 --json
```

For daily crypto, add `--periods-per-year 365`; the default is 252.
HMM is optional and excluded from core installation:

```bash
uv run --with hmmlearn --script "${CLAUDE_PLUGIN_ROOT}/scripts/markov_regime.py" --ticker SPY --json
```

Do not install HMM to perform observable analysis. A missing/broken HMM or failed
fit yields an unavailable HMM summary while other supported results remain valid.

## Parameters and input

Defaults: window 20 observations, threshold 0.05, minimum training 252 labeled
observations, horizon 1, annualization 252, cost 0 bps. Windows/horizons refer to
observations, not calendar days. Thresholds use simple returns. Equality within
1e-12 is Sideways.

CSV parsing detects common date/close column names and sorts valid timestamps.
Malformed or duplicate dates and missing/nonpositive/nonfinite prices are
errors. Library price inputs must be chronological. No silently discarded rows.

## JSON contract

Successful JSON calls emit exactly one object with `schema_version: 2`.
Failures emit one object with `error` and exit nonzero. Unavailable numeric values
are JSON null; no NaN or Infinity tokens are emitted.

| Field | Meaning |
|---|---|
| schema_version | 2 |
| source, rows, date_start, date_end | Source and actual data coverage |
| params | Parameters used, including horizon, periods_per_year, and cost_bps |
| states | Fixed order: Bear, Sideways, Bull |
| current_regime | Regime at the last observation |
| transition_counts | Observed 3×3 counts, row=from and column=to |
| transition_matrix | Observed rows sum to 1; unsupported rows are three nulls |
| next_state_probabilities | One-step bear/sideways/bull probabilities, or three nulls |
| signal | One-step bull minus bear, or null when unsupported |
| forecast | Requested horizon and bear/sideways/bull probabilities |
| persistence_diagonal | Probability of remaining in each state, or null |
| stationary_distribution | Unique stationary regime mix, or three nulls |
| unavailable | Reasons keyed by unavailable output component |
| walk_forward | Signed-strategy backtest metrics and assumptions |
| hmm | Availability, ranked latent-state means, and caveat or reason |
| framework, disclaimer | Attribution and historical-analysis limitation |

An unavailable current-state forecast is not equivalent to a valid zero signal.
N-step forecasts remain available only when all required positive-probability
paths have observed transitions. Stationary output requires evidence for every
outgoing row and a unique solution. It does not claim convergence from every
initial state.

## Integration examples

Check version and availability before consuming the score:

```python
assert result["schema_version"] == 2
score = result["signal"]
take_long = my_strategy_says_long and score is not None and score > 0
```

The standalone backtest evaluates this signed position rule:

```python
score = result["signal"]
position = 0 if score is None else (1 if score > 0 else -1 if score < 0 else 0)
```

The score is directional, not calibrated return confidence. Proportional sizing
and sizing based on stationary Bear share require separate policy evaluation.
Bear occupancy is not a measured tail-loss probability. If stationary output
is unavailable, do not invent a sizing value.

## Backtest interpretation

The matrix at signal observation t includes only transitions ending before t.
The current regime uses close t. An order fills at close t+1 and earns its first
return from t+1 to t+2. The same execution ledger serves research comparisons.

Costs are basis points per unit of exposure change, including entry, reversal,
and terminal liquidation. Starting equity is 1. n_periods counts evaluated
observations; n_trades counts entries/reversals. Undefined metrics are null with
reasons. Flat periods caused by unavailable forecasts are retained.

The separate frozen-data study compares long-or-cash buy-and-hold, positive
20-bar momentum, and momentum gated by the Markov score. It does not validate
the standalone shorting strategy, HMM signals, or stationary-based sizing.

## TradingView parity

The indicator shares simple returns, threshold tolerance, named state ordering,
and missing-evidence handling. Pine permits asymmetric Bull/Bear thresholds;
use symmetric settings for parity. Compare identical price data, date coverage,
and adjustment policy. Diagnostics and chart acceptance must execute in
TradingView; Python checks alone do not prove Pine runtime behavior.
