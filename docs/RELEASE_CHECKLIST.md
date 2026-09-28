# v2 release evidence

Implementation date: 2026-09-28. **All required v2 acceptance checks passed:**
remote Python CI, exact-source Pine compilation and diagnostics, asymmetric
display checks, confirmed-bar replay, and frozen offline research. Private
script/layout reload also passed. The additional exported-market-data comparison
remains unverified; its scope and limitation are recorded below.

## Original priority findings

| Finding | Implemented correction | Regression evidence |
|---|---|---|
| Invalid sparse probabilities/stationarity | Missing rows remain unavailable; structural uniqueness and numerical residual checks | [Model regressions](../tests/test_model.py): `test_missing_rows_are_unknown_not_zero_probability`, `test_slow_mixing_is_not_misclassified_as_nonunique`; [analytical fixtures](../tests/test_shared_contract.py): `test_shared_stationary_examples` |
| Pine long-run values under wrong headings | Canonical states and shared display accessors for both tables | [Shared asymmetric/matrix checks](../tests/test_pine_contract.py); [actual Pine runtime evidence](TRADINGVIEW_ACCEPTANCE.md): exact source compiled, diagnostics PASS, asymmetric market tables rendered, replay passed |
| Initial drawdown omitted | Initial equity 1 participates in every peak/drawdown calculation | [Accounting regression](../tests/test_integration_contract.py): `test_initial_equity_loss_is_not_erased_by_the_first_recorded_peak` |
| Negative windows introduce future dependence | Public parameter validation; causal labels, forecasts, and delayed execution | [Input validation](../tests/test_model.py): `test_analysis_rejects_invalid_parameters`; [causality regression](../tests/test_integration_contract.py): `test_future_suffix_cannot_change_orders_or_earned_returns_in_the_past` |
| Nonstandard JSON NaN | JSON-safe missing results, reasons, and strict serialization | [CLI regressions](../tests/test_cli.py): `test_cli_short_history_is_one_strict_json_object`, `test_json_argument_errors_have_json_on_stdout` |
| HMM required during core installation | Core PEP 723 dependencies exclude HMM; explicit opt-in | [Installation regression](../tests/test_installation.py): `test_core_script_does_not_require_optional_hmm`; isolated locked core launch without HMM |

## Verification record

| Check | Status and evidence |
|---|---|
| Local Windows / Python 3.13.5 | PASS: 98 tests and 8 subtests before LF regressions; NumPy 2.5.3, pandas 3.0.6 |
| Local Windows / Python 3.10.20 | PASS: 98 tests and 8 subtests before LF regressions; NumPy 2.2.6, pandas 2.3.3 |
| Remote CI: Windows and Ubuntu / Python 3.10 and 3.13 | PASS: all 4 matrix jobs; each reports 100 tests and 8 subtests passed, optional HMM absent, locked standalone command and strict JSON verified. [Run 36381098658](https://github.com/rmabry/markov-hedge-fund-method/actions/runs/36381098658), commit `7aff580c846453e2fd5bffe76226cafda14062d1`, attempt 1 |
| Locked standalone core command | PASS, local CSV, strict JSON v2; HMM absent |
| Core regression-first evidence | Initial 40 failures before fixes; subsequent threshold, CAGR, HMM and near-identity regressions failed before correction |
| Shared Pine fixture synchronization | PASS; five source checks, plus Python analytical fixtures. These are not Pine execution |
| TradingView compilation/diagnostics/replay | PASS: exact source compiled, actual Pine diagnostics PASS; first durable run initializes silently, subsequent confirmed change creates exactly one marker. See [runtime evidence](TRADINGVIEW_ACCEPTANCE.md) |
| TradingView private save/reload | PASS: user-approved private script and test layout saved; actual reload retained diagnostic PASS, both numerical tables, settings, and confirmed markers |
| Additional exported-market-data parity | UNVERIFIED: CSV download did not complete. This supplemental feed/history comparison was added during implementation; the plan's shared-fixture and actual Pine runtime checks passed independently |
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

## Release status and limits

The six original findings have fixes and passing regression evidence. The
user-approved plan's required runtime checks and benchmark are complete; no
required gate remains open for the recorded source/dependency versions. Remote
CI ran against `7aff580c846453e2fd5bffe76226cafda14062d1`; subsequent changes only
record this evidence and exclude local screenshots from Git.

The [additional exported-chart comparison](TRADINGVIEW_ACCEPTANCE.md#additional-same-data-market-comparison--pending)
is still unverified because the browser did not deliver the CSV. Shared analytical
fixtures passed in both languages; this does not establish equality between
different market feeds, adjustment policies, or loaded histories. The frozen
SPY/BTC benchmark is a retrospective study, not point-in-time vendor data or a
claim of future trading performance.

Browser screenshots remain local in ignored `docs/evidence/`; they were not
published. The indicator and test layout are saved privately. No merge, public
indicator publication, or production trading deployment is part of this work.
