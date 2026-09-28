# TradingView acceptance — model contract v2

Pine runtime acceptance is **pending**. Local Python checks do not compile or
execute Pine. The TradingView editor was reached on 2026-09-28, but the existing
two-factor authentication prompt prevents completing the runtime checks. Sign-in
must be completed directly by the account owner; credentials are not test inputs.

## Source under review

- File: `pine-script/markov-hedge-fund-method.pine`
- SHA-256: `913634fe1dd8f06a0f5bd4e235b2750a3ad88038bb8457f577f47624c52e5a12`
- Contract: `tests/fixtures/model_contract.json`, version 2.
- Local synchronization check: `python -m unittest discover -s tests -p test_pine_contract.py -v`
- Local result: **5 tests passed**. Before implementation the same test suite
  failed on missing named states and diagnostic vectors. A subsequent row-mapping
  fixture check also failed before its corresponding vector was added.
- These are source/fixture synchronization checks only. They verify the numeric
  literals embedded in the actual Pine diagnostics match the shared fixtures.
  They do not establish Pine syntax validity, execution, rendering, or replay.

Any change to the Pine file invalidates this source fingerprint and requires a
new compiler/diagnostics result. Do not mark this document passed from Python
results or from a Python translation of Pine logic.

## Contract and expected behavior

The canonical state order is Bear=0, Sideways=1, Bull=2. Both visual tables use
Bull/Bear/Sideways through the same mapping helpers. The default return is the
simple percentage change over 20 bars, with symmetric 5% thresholds and absolute
boundary tolerance `1e-12`. Pine retains independent Bull/Bear threshold controls;
Python parity requires those thresholds to be equal.

Warmup and invalid prices have no regime. Transition counts use raw states on
confirmed bars only. A state with no outgoing observations has an unavailable
row, displayed as `N/A`; it does not acquire a synthetic prior. The stationary
mix requires complete rows and a unique solution. Three-state tree weights solve
`pi P = pi`, with normalization/residual tolerance `1e-10`. Nonunique or incomplete
models show `N/A` and an explanatory status. A periodic chain can have a stationary
mix even when its successive state distributions do not converge.

The first durable run initializes the label state silently. Later durable changes
produce one marker after the configured number of confirmed bars. Markers retain
the historical run-origin placement, with a tooltip explaining the confirmation
delay. They were not available at that earlier origin. The forming-bar banner is
identified separately; model tables use confirmed observations.

## Required runtime checks

Use the exact fingerprinted file in TradingView's Pine Editor as a personal
script. Record the chart symbol including exchange, interval, visible account
plan limitations, first/last loaded bars, input settings, date, and source hash.
Do not publish the indicator as part of these checks.

| Gate | Acceptance criterion | Result |
|---|---|---|
| Compile | Save/add the exact Pine v5 source with no errors; review any warnings | Pending |
| Inline analytical diagnostics | Enable **Diagnostics → Run analytical self-tests**; top-center table reads **DIAGNOSTICS PASS - contract v2**, with no runtime error | Pending |
| Normal rendering | Turn diagnostics off; both tables, banner, ribbon, text-size options, toggles, and positions render correctly | Pending |
| Warmup/sparse history | Warmup has no ribbon/regime; unseen outgoing rows and incomplete stationary mix show `N/A`, never invented probabilities | Pending |
| Replay/confirmation | A four-bar durable change creates no marker before the fourth confirmed close and exactly one afterward | Pending |
| Raw-count independence | Changing label hold/display controls does not alter either numerical table | Pending |
| Reload stability | Reload with identical data/settings; final model tables and confirmed markers agree | Pending |
| Same-data parity | Python and actual Pine agree on identical close values, bar boundaries, thresholds, and history | Pending |

The diagnostic mode calls the same production return, label, transition-count,
matrix, stationary, durable-label, and display-lookup helpers as normal execution.
It checks:

- Exact threshold boundaries, values within/outside `1e-12`, and the simple-return
  examples 100→105.1 (Bull) and 100→95.1 (Sideways).
- Known transition counts and row normalization, unavailable sparse rows, and
  unconfirmed updates that must not count.
- An asymmetric stationary vector, a slowly mixing chain, a periodic cycle,
  a uniquely absorbing chain, a nonunique identity matrix, and incomplete data.
- Stationary column mapping and transition-table row/column mapping, including
  a matrix whose rows differ.
- Warmup followed by Bull for four bars, Sideways for three, and Bear for at
  least four. There must be exactly one Bull→Bear event at fixture index 11,
  displayed at origin index 8. Hold=1 also initializes silently before emitting
  the next transition; unconfirmed updates never advance a run.

Failures deliberately stop the indicator with a named `runtime.error()`. PASS is
assigned only after all assertions execute. This diagnostic result validates the
helpers in Pine; chart replay is still necessary to validate execution-state and
visual behavior.

## Same-data parity procedure

1. Use an exported close series from the exact chart instrument and interval.
   Comparing Yahoo BTC-USD against exchange BTCUSDT is not a parity test.
2. Match the entire loaded history, including the initial lookback bars, and
   exclude the current unconfirmed bar. Record the first and final included bar.
3. Run Python on that CSV with identical lookback and symmetric threshold.
4. Compare current confirmed regime, each named transition cell, and stationary
   status/distribution. Account for Pine's integer-percent display rounding;
   compare unrounded values through temporary Pine Logs if needed and restore
   the exact source afterward before recording final acceptance.
5. Record evidence and tolerances here. A fixture-only comparison is not a
   market-data parity run.

## Runtime evidence record

No compiler result, diagnostic PASS, screenshot of a successful run, or replay
result has been obtained for the fingerprint above. Replace the pending entries
only after actual TradingView execution, recording any source changes and the
final SHA-256. If access remains unavailable, this gate remains pending and
Pine runtime verification must be reported as incomplete.

TradingView documents [Pine v5 debugging](https://www.tradingview.com/pine-script-docs/v5/writing/debugging/),
[confirmed-bar semantics](https://www.tradingview.com/pine-script-docs/v5/concepts/bar-states/),
and [runtime limits](https://www.tradingview.com/pine-script-docs/v5/writing/limitations/).
