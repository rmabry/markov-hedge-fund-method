# Frozen research protocol

This release tests the documented regime-confirmation use case. It is a retrospective
research comparison, not a live trading system. The protocol and parameters are fixed
before its results are inspected; no parameter search is performed. Historical dates
that researchers may already know are not represented as a pristine unseen experiment.

## Run the saved evaluation offline

From the repository root, install the locked development environment once:

```sh
uv sync --locked --group dev
```

Then evaluate the committed snapshots without network access:

```sh
uv run --offline python scripts/research_evaluation.py evaluate
```

The default input is `research/data/baseline-v1/`. The command verifies CSV SHA-256
hashes and the manifest's dates, coverage and adjustment policy before analysis. Missing
or changed inputs fail; they never trigger a download. Outputs are
`research/results/baseline-v1/evaluation.json` (strict JSON, schema version 2) and
`research/results/baseline-v1/report.md`. Repeated evaluation with the same inputs,
code and environment generates identical output; no run timestamp is injected.
The JSON includes the manifest hash and evaluation dependency versions.
Snapshot CSVs and manifests, evaluation JSON and Markdown reports use UTF-8 with
LF line endings so their file hashes are stable across Windows and Unix checkouts.

To select existing inputs or a different output directory explicitly:

```sh
uv run --offline python scripts/research_evaluation.py evaluate --data-dir research/data/baseline-v1 --output-dir research/results/baseline-v1
```

## Explicit acquisition, only when a new snapshot is wanted

```sh
uv run python scripts/research_evaluation.py fetch --data-dir research/data/baseline-v2
```

`fetch` is the only network command. It refuses an existing nonempty destination;
choose a new snapshot name to acquire revised source data. It downloads both assets,
validates them, then writes normalized date/close CSVs and a manifest with the
acquisition timestamp, source URLs, adjustment policy, package versions, exact
coverage, unusually long gaps and file hashes. Acquisition failure leaves no invented
price observations or substitute dataset. The committed `baseline-v1` is an actual
Yahoo Finance acquisition, not the synthetic prices used in automated tests.

## Data and fixed split

- SPY: dividend/split-adjusted Yahoo daily close, `auto_adjust=True`.
- BTC-USD: Yahoo daily close, `auto_adjust=False`.
- Requested observations: 2015-01-01 through 2025-12-31, inclusive.
- Development period: 2015-01-01 through 2019-12-31.
- Evaluation period: 2020-01-01 through 2025-12-31.
- Preserve each asset's observed dates. Do not resample or fill weekends/gaps.
- Reject duplicate/unsorted dates and missing, nonfinite or nonpositive prices.
- Disclose gaps greater than four calendar days for SPY or one day for BTC.

Yahoo historical adjustments can be revised after the observation date. These are
frozen retrospective prices, not a point-in-time vendor feed. The daily adjusted-SPY
series also represents dividend reinvestment through its price adjustment convention.

## Model and missing evidence

Use 20-observation **simple returns**, `close[t] / close[t-20] - 1`, with strictly
greater than +5% defining Bull and strictly less than -5% defining Bear. Remaining
valid observations are Sideways. Exclude the initial warm-up observations.

The minimum training history is 252 valid regime observations on both assets. At
decision time `t`, estimate transitions strictly inside `labels[:t]`: the training
sample ends before the current state. The current state is known and selects the
forecast row. This convention is deliberately preserved across the core and research
runner. Re-estimate as history expands, without tuning parameters on the evaluation
period. Never include future labels.

An unobserved source row has unavailable probabilities and signal, not uniform or
zero probability estimates. The research policy moves to cash when its forecast is
unavailable. Stationary distribution is not used by any evaluated strategy. This
experiment does not establish that its Bear share measures tail risk.

## Three strategies, one execution model

| Policy | Exposure decided at close t |
|---|---|
| Buy-and-hold | 1 |
| Momentum | 1 when the 20-observation simple return is positive, otherwise 0 |
| Filtered momentum | Momentum exposure, additionally requiring an eligible, available `bull_prob - bear_prob > 0`; otherwise 0 |

All strategies are long/cash. Cash earns zero. A decision at close `t` fills at
close `t+1` and earns the return from `t+1` to `t+2`. Every simulation starts flat
immediately before the first evaluation close. A decision from the last development
observation may fill at that first close; no return earned before the first close is
credited. Liquidate at the final evaluation close and charge its cost. All policies
use the same observation calendar and endpoints.

Costs are **0, 5, 10 and 25 basis points** per unit of absolute exposure change.
The main case is **10 bps**; the others are a fixed sensitivity grid, not optimized
choices or claims about actual brokerage costs. For each ledger row:

```text
gross_return = previous_position * close_to_close_simple_return
turnover = abs(position_after_fill - previous_position)
cost = cost_bps / 10000 * turnover
net_return = gross_return - cost
equity = cumulative_product(1 + net_return)
```

Initial entry and final liquidation incur costs. No leverage, short borrowing,
financing return, taxes or intraday fill assumptions are added.

## Metrics and forecast comparison

Report total return, CAGR, annualized sample-standard-deviation volatility, zero-cash-rate
Sharpe, maximum drawdown, average absolute filled exposure, turnover and entry count.
Drawdown includes initial capital 1. Entry count counts entries/reversals, not every
held bar or exits. The denominator includes all evaluation observations, including
the initial zero-gross-return row. CAGR uses the actual elapsed time between the
first and last evaluation closes: `(final_equity ** (1 / elapsed_years)) - 1`,
where `elapsed_years = elapsed_seconds / (365.2425 * 86400)`. Volatility and Sharpe
annualize with the square root of 252 observations/year for SPY and 365 for BTC.
Undefined metrics are JSON `null` with
reasons under `unavailable`, never NaN/Infinity. Report filtered-minus-momentum return,
CAGR, drawdown and Sharpe for every cost case.

Score one-observation state forecasts on decision dates within the evaluation period
whose next observed label also falls inside that period. Coverage includes every
such opportunity; publish eligible, available and unavailable counts overall and by
current state. Score only matched eligible dates with all Markov probabilities
available. On those exact dates compare:

- Markov's predicted probability row.
- Persistence: probability 1 for the current state.
- Historical frequency: state frequencies strictly before the decision date.

Multiclass Brier score is the mean **sum** of squared class errors, ranging from 0 to
2; smaller is better. With no matched forecasts scores are null with a reason.
Missing forecasts cannot improve the score invisibly because their coverage is
reported separately. Forecast skill is separate from trading profitability.

## Acceptance and interpretation

The release passes when its input hashes verify, offline runs are deterministic,
chronology/cost/drawdown/missing-evidence regressions pass, and every predeclared
comparison is reported. Profitability and outperforming the baseline are not release
gates. If the filter reduces return or fails to beat forecast baselines, preserve and
state that result. Do not retune against this period and keep calling it held out.

This validates only these explicitly simulated policies. It does not validate the
older sign-based long/short backtest, continuous signal sizing, stationary-distribution
position sizing, or future performance. Close-only prices cannot model market impact
or intraday execution. Further strategy changes require a newly specified evaluation.
