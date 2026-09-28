# TradingView acceptance — model contract v2

Actual Pine v5 compilation, inline analytical diagnostics, rendering controls,
warmup/sparse-history checks, durable-label replay, and page-reload stability
**passed in TradingView on 2026-09-28**. The additional exported-market-data
comparison remains pending; it is recorded separately from those runtime checks.
The required Pine acceptance gates are satisfied; the supplemental comparison is
not a release gate and no successful market-data parity result is claimed.
Local Python source checks are separate evidence and do not execute Pine. Overall
release status is tracked in the [release checklist](RELEASE_CHECKLIST.md).

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
| Compile | Save/add the exact Pine v5 source with no errors | Passed; editor source matched the SHA-256 above after LF normalization |
| Inline analytical diagnostics | Enable **Diagnostics → Run analytical self-tests**; top-center table reads **DIAGNOSTICS PASS - contract v2**, with no runtime error | Passed in the actual Pine runtime |
| Normal rendering | Both tables, banner, ribbon, text-size options, toggles, and positions render correctly with diagnostics off | Passed for tested settings: huge/normal text, top-left/bottom-left banner, overlays hidden and restored; diagnostics-off rendering verified |
| Warmup/sparse history | Warmup has no ribbon/regime; unseen outgoing rows and incomplete stationary mix show `N/A`, never invented probabilities | Passed on earliest available history and after 25 loaded bars |
| Replay/confirmation | A four-bar durable change creates no marker before the fourth confirmed close and exactly one afterward | Passed on the April 2026 sequence below |
| Raw-count independence | Changing label hold/display controls does not alter either numerical table | Passed: hold 4→1, labels off, diagnostics off; sparse numerical tables unchanged |
| Reload stability | Reload with identical data/settings; final model tables and confirmed markers agree | Passed after user-approved private script/layout save; actual page reload retained diagnostic PASS, numerical tables, and confirmed markers |

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

## Additional same-data market comparison — pending

The shared analytical fixtures test the model contract through the actual Pine
production helpers. An exported-market comparison adds coverage of feed values,
history boundaries, and price adjustment alignment. It was added as a supplemental
integration check; no successful market-data comparison is claimed here. This
pending check should not be confused with the completed compile, diagnostics,
rendering, replay, and reload checks above.

1. Use an exported close series from the exact chart instrument and interval.
   Comparing Yahoo BTC-USD against exchange BTCUSDT is not a parity test.
2. Match the entire loaded history, including the initial lookback bars, and
   exclude the current unconfirmed bar. Record the first and final included bar.
3. Run Python on that CSV with identical lookback and symmetric threshold.
4. Compare current confirmed regime, each named transition cell, and stationary
   status/distribution. Account for Pine's integer-percent display rounding;
   compare unrounded values through temporary Pine Logs if needed and restore
   the exact source afterward before recording the comparison result.
5. Record evidence and tolerances here. A fixture-only comparison is not a
   market-data parity run.

## Runtime evidence record — 2026-09-28

The exact source was pasted into Pine Editor, compiled, and added to the chart.
The editor text, normalized to LF line endings, matched the recorded SHA-256.
All inline assertions completed and the chart displayed
**DIAGNOSTICS PASS - contract v2**. This includes the asymmetric stationary fixture
`[Bear=0.2, Sideways=0.3, Bull=0.5]`, whose display helper must return
`[Bull=50%, Bear=20%, Sideways=30%]`.

The chart URL used `BATS:AAPL`; TradingView's instrument UI identified AAPL as
NASDAQ. Tests used daily bars with **ADJ off**, lookback 20, Bull/Bear thresholds
5%, and initially a four-bar minimum hold. Preserve that feed/adjustment context
when collecting prices for the outstanding parity check. The earliest available
replay bar was 1980-12-12. The normal chart's final displayed daily bar was
2026-09-25; account-specific history limits were not separately recorded.

With huge text, the normal chart displayed this transition matrix and stationary
mix, both in Bull/Bear/Sideways display order:

| From / to | Bull | Bear | Sideways |
|---|---:|---:|---:|
| Bull | 89% | 0% | 11% |
| Bear | 0% | 86% | 14% |
| Sideways | 13% | 10% | 77% |
| Stationary mix | 39% | 26% | 35% |

These market percentages are observed rendering evidence, not an independent
same-data numerical comparison. Normal text and relocating the banner to the
bottom left were also verified. Ribbon, banner, matrix, stationary table, and
diagnostics were switched off together, then restored; visibility followed the
controls. See the local [hidden-overlays capture](evidence/pine-display-hidden.jpg).

### Confirmation timing and deduplication

Selecting replay start 2026-04-14 positioned the chart at April 13. Replay then
advanced through April 14–23. April 15 was Sideways; the Bull run comprised
April 16, 17, 20, and 21. With April 21 still forming, only three Bull bars were
confirmed and no transition marker appeared. Advancing to April 22 confirmed
April 21, producing exactly one SIDE→BULL marker at the April 16 origin. Advancing
to April 23 did not create a duplicate. This confirms both delayed availability
and the deliberately retrospective placement of the marker.

The screenshots linked below remain in local, ignored `docs/evidence/`. They
include browser account UI and are not published with the repository source.

- [Diagnostic PASS](evidence/pine-diagnostics.jpg)
- [Before fourth-bar confirmation](evidence/pine-replay-before-confirmation.jpg)
- [Confirmed transition at its historical origin](evidence/pine-replay-confirmed.jpg)
- [Next bar without a duplicate](evidence/pine-replay-no-duplicate.jpg)

### Warmup and sparse initialization

At the earliest available bar, 1980-12-12, the banner showed insufficient history,
there was no regime ribbon, and both numerical tables showed unavailable values.
After 24 additional replay steps (25 bars total), the Bull row displayed
100%/0%/0%, the other outgoing rows remained `N/A`, and the stationary mix remained
`N/A` with insufficient-evidence status. The first durable Bull run produced no
transition marker.

- [First-bar warmup](evidence/pine-warmup.jpg)
- [Sparse evidence and silent initial durable run](evidence/pine-sparse-initialization.jpg)

### Display independence and reload persistence

The raw-count independence check passed: hold 4→1, transition labels off, and
diagnostics off left the sparse numerical tables unchanged. See the local
[display-independence screenshot](evidence/pine-display-independence.jpg).

Automatic approval review initially rejected saving a private script because it
creates persistent account content. The user then explicitly approved saving the
private script and test layout, resolving that approval requirement. The script
was saved privately as **Markov Regime v2 - validated research**, and the layout
as **Markov v2 acceptance**. The indicator was not published.

A real page reload subsequently passed: **DIAGNOSTICS PASS - contract v2**
reappeared, confirmed markers remained, and the transition rows were unchanged
at Bull 89%/0%/11%, Bear 0%/86%/14%, Sideways 13%/10%/77%. The stationary display
remained Bull 39%, Bear 26%, Sideways 35%. The source fingerprint did not change.

- [Private script saved](evidence/pine-private-script-saved.jpg)
- [Before page reload](evidence/pine-before-reload.jpg)
- [After page reload](evidence/pine-after-reload.jpg)

These images remain local, ignored evidence and are not publishable repository
assets. TradingView's separate snapshot command was also rejected by automatic
review because it might upload/share account-associated chart state; local
screenshots were used instead.

### Outstanding supplemental comparison

A same-chart CSV export and a bounded retry timed out without producing a
downloaded file. Exported-market-data parity therefore remains unverified; no
further browser attempts are required for the accepted scope. Shared analytical
fixtures have passed in Pine; they do not establish that additional feed/history
comparison. This supplemental limitation does not reopen the completed required
Pine gates. Overall release completion remains recorded in the release checklist.

TradingView documents [Pine v5 debugging](https://www.tradingview.com/pine-script-docs/v5/writing/debugging/),
[confirmed-bar semantics](https://www.tradingview.com/pine-script-docs/v5/concepts/bar-states/),
and [runtime limits](https://www.tradingview.com/pine-script-docs/v5/writing/limitations/).
