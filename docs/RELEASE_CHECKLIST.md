# v2 release evidence

Implementation date: 2026-09-28. **Release gate remains open until TradingView
runtime acceptance and the remote CI matrix are verified.**

## Original priority findings

| Finding | Implemented correction | Regression evidence |
|---|---|---|
| Invalid sparse probabilities/stationarity | Missing rows remain unavailable; structural uniqueness and numerical residual checks | `test_missing_rows_are_unknown_not_zero_probability`, `test_shared_stationary_examples`, `test_slow_mixing_is_not_misclassified_as_nonunique` |
| Pine long-run values under wrong headings | Canonical states and shared display accessors for both tables | Shared asymmetric/matrix fixtures synchronized; actual Pine diagnostics await sign-in |
| Initial drawdown omitted | Initial equity 1 participates in every peak/drawdown calculation | `test_initial_equity_loss_is_not_erased_by_the_first_recorded_peak` |
| Negative windows introduce future dependence | Public parameter validation; causal labels, forecasts, and delayed execution | `test_analysis_rejects_invalid_parameters`, `test_future_suffix_cannot_change_orders_or_earned_returns_in_the_past` |
| Nonstandard JSON NaN | JSON-safe missing results, reasons, and strict serialization | `test_cli_short_history_is_one_strict_json_object`, `test_json_argument_errors_have_json_on_stdout` |
| HMM required during core installation | Core PEP 723 dependencies exclude HMM; explicit opt-in | `test_core_script_does_not_require_optional_hmm`, isolated locked core launch without HMM |

## Verification record

| Check | Status and evidence |
|---|---|
| Windows / Python 3.13.5 | PASS: 98 tests and 8 subtests; NumPy 2.5.3, pandas 3.0.6 |
| Windows / Python 3.10.20 | PASS: 98 tests and 8 subtests; NumPy 2.2.6, pandas 2.3.3 |
| Ubuntu / Python 3.10 and 3.13 | CI configured; remote execution pending |
| Locked standalone core command | PASS, local CSV, strict JSON v2; HMM absent |
| Core regression-first evidence | Initial 40 failures before fixes; subsequent threshold, CAGR, HMM and near-identity regressions failed before correction |
| Shared Pine fixture synchronization | PASS; five source checks, plus Python analytical fixtures. These are not Pine execution |
| TradingView compilation/diagnostics/replay | PENDING: browser is requesting two-factor authentication; user asked to sign in directly |
| Frozen Yahoo inputs | PASS: SPY 2,766 rows and BTC-USD 4,018 rows; metadata and SHA-256 verified |
| Offline research reproducibility | PASS: consecutive real evaluations byte-identical; shipped-result regression checks numeric reproducibility across supported dependencies |
| Whitespace/diff checks | PASS before release preparation |

Local test commands (temporary directories were needed for this Windows sandbox):

```powershell
.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\python313-final
.venv310\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\python310-final
```

Normal developer command: `uv run --locked python -m pytest -q`.

## Research outcome

The filter selected exactly the same exposures as ordinary momentum for both
assets and all four cost cases. The evaluated filter therefore added **no
incremental trading benefit**. No parameters were changed after this result.

At 10 bps per unit of exposure change:

| Asset | Momentum/filtered return | Sharpe | Maximum drawdown |
|---|---:|---:|---:|
| SPY | 50.89% | 0.6187 | -22.16% |
| BTC-USD | 665.92% | 1.0170 | -66.71% |

Markov next-regime forecasts improved Brier scores over persistence on matched
dates, with 100% forecast coverage. That improvement did not change trades in
the prescribed filter. See the [full research report](../research/results/baseline-v1/report.md)
and [protocol](../research/PROTOCOL.md).

## Remaining release gate

Complete the [TradingView acceptance procedure](TRADINGVIEW_ACCEPTANCE.md) against
the exact source hash recorded there, and record the remote CI matrix result.
Until those checks pass, v2 is an implemented candidate, not a fully verified
release. No merge or production trading deployment is part of this work.
