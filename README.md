# Markov Hedge Fund Method — v2

A research tool for describing Bull, Bear, and Sideways regimes and evaluating
whether a regime filter improves a simple momentum strategy. Framework by
**Roan ([@RohOnChain](https://x.com/RohOnChain))**; original plugin and video
resources by **Lewis Jackson**.

## Run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
uv run --locked --script scripts/markov_regime.py --ticker SPY --json --no-hmm
uv run --locked --script scripts/markov_regime.py --csv my_prices.csv --horizon 5 --json
uv run --locked --script scripts/markov_regime.py --ticker BTC-USD --periods-per-year 365 --cost-bps 10
```

CSV input needs a date column and a positive, finite close-price column. Common
column names are detected automatically; valid dates are sorted. Invalid dates,
prices, or duplicate timestamps are errors rather than silently discarded rows.
Windows paths containing spaces must be quoted.

Core dependencies are NumPy, pandas, and yfinance. HMM fitting is optional:

```bash
uv run --with hmmlearn --script scripts/markov_regime.py --ticker SPY --json
```

The core command does not install HMM dependencies. Missing or broken HMM imports
and fitting errors leave observable analysis available. HMM output summarizes
latent-state means; it is not a validated HMM trading strategy.

For Claude Code:

```text
/plugin marketplace add jackson-video-resources/markov-hedge-fund-method
/plugin install markov-hedge-fund-method@markov-hedge-fund-method
/markov-hedge-fund-method:regime
```

These commands install the version published by that upstream repository.
To use this checkout's v2 changes before upstream publication, add this
repository's absolute local path as the marketplace instead.

## Model and v2 contract

- State order is **Bear, Sideways, Bull**. Defaults are 20 observations and
  simple-return thresholds of ±5%; equality within `1e-12` is Sideways.
- Observed transition rows use empirical counts. An unobserved row is
  `[null, null, null]` in JSON, never an invented probability distribution.
- One-step probabilities and `signal = bull − bear` can be unavailable. A valid
  zero signal and missing evidence have different meanings.
- Stationary probabilities require complete outgoing-transition evidence and a
  unique solution. Stationarity does not imply finite-horizon convergence from
  every starting state.
- `--horizon` adds an n-step forecast while preserving one-step output.
  Unsupported paths make the affected forecast unavailable.
- JSON declares `schema_version: 2`; unavailable values are `null`, with reasons
  in `unavailable`. NaN and infinities never appear in JSON.

See the [full contract and examples](skills/regime/SKILL.md) and
[migration notes](docs/MIGRATION_V2.md). The signed score measures direction,
not a calibrated probability of making money. Long-run Bear share is a regime
occupancy estimate, not a measured tail-loss probability.

## Backtest and research

The standalone backtest takes the sign of an available signal; missing evidence
means flat exposure. A signal using close t fills at close t+1 and first earns
the return from t+1 to t+2. Transition estimates use only transitions ending
before the signal bar. Costs apply to exposure changes, including initial entry
and final liquidation. Starting capital is included in maximum drawdown.

`n_periods` counts evaluated observations; `n_trades` counts entries, including
reversals. Annualization defaults to 252 periods/year; use 365 for daily crypto.
Windows and horizons are measured in observations, not calendar days.

The [research protocol](research/PROTOCOL.md) freezes daily SPY and BTC-USD inputs
for 2015–2025 and evaluates 2020–2025 without parameter retuning. It compares
buy-and-hold, positive 20-bar momentum, and momentum gated by the Markov score,
using long-or-cash exposure and predeclared costs. See the
[research report](research/results/baseline-v1/report.md) for results and limitations.

The [follow-up signal audit](research/INFORMATION_VALUE_DECISION.md) explains why
the filter changed no trades: its score was positive on every momentum-long
decision. Most next-regime Brier improvement was also available from fixed
pre-2020 transition rows. The current evidence supports a descriptive research
tool; incremental trading value remains unproven. A single
[prospective sizing experiment](research/NEXT_EXPERIMENT.md) is specified before
its evaluation period.

Reproduce the audit from the same frozen inputs, entirely offline:

```bash
uv run --locked --offline python scripts/signal_audit.py
```

Outputs are in `research/results/information-audit-v1/`; baseline results are
preserved.

## Tests and release evidence

```bash
uv sync --locked
uv run --locked python -m pytest -q
```

Tests use deterministic local fixtures; they do not fetch market prices. CI
runs Windows and Ubuntu with Python 3.10 and 3.13 and separately checks
the standalone core command without HMM installed.

The [release checklist](docs/RELEASE_CHECKLIST.md) records actual verification.
Configured CI is not evidence that remote jobs have run.

## TradingView

Paste [the Pine indicator](pine-script/markov-hedge-fund-method.pine) into
TradingView's Pine Editor and add it to a chart. It shares Python's simple-return
definition and missing-evidence policy. Separate Bull/Bear thresholds are a Pine
extension; use equal values for parity. Data source, dates, and adjustment policy
must also match when comparing outputs.

An off-by-default diagnostic mode executes analytical fixtures through the same
helpers used by the indicator. Follow the [TradingView acceptance procedure](docs/TRADINGVIEW_ACCEPTANCE.md).
Python fixture checks do not establish Pine compilation or chart correctness.

The [manual setup guide](markov-hedge-fund-method.md) uses the maintained source
instead of generating another copy of the algorithm.

## License

MIT — see [LICENSE](LICENSE).
