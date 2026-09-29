# Information-value decision

Decision date: 2026-09-28 America/Chicago (2026-09-29 UTC).

## Current conclusion

Retain v2 as a validated regime-description and probabilistic research tool.
Its prescribed positive-score momentum filter has **no demonstrated incremental
trading value** on the frozen SPY and BTC-USD evaluation. The evidence supports
testing one specific source of additional information: changes in probability
magnitude as transition counts expand. It does not support a trading deployment.

This is a conclusion about the tested model, assets, period, and policy. It does
not establish that all Markov models are ineffective, or that these results will
persist in future data.

## Why no trades changed

The rule requires both a positive 20-bar return and a positive score,
`P(next=Bull | current) - P(next=Bear | current)`. During every inspected
2020–2025 decision, the score was negative in Bear and positive in Sideways and
Bull. A positive 20-bar return already excludes Bear by definition. The score's
sign therefore added no restriction to the momentum rule on these data.

| Evaluation decisions | SPY | BTC-USD |
|---|---:|---:|
| Total decisions, including the terminal date | 1,508 | 2,192 |
| Momentum long | 1,050 | 1,205 |
| Long decisions in Sideways | 789 | 369 |
| Long decisions in Bull | 261 | 836 |
| Markov vetoes of momentum longs | 0 | 0 |
| Unavailable scores | 0 | 0 |

That equivalence is an observed property of the expanding estimates, not a
universal mathematical restriction on Markov chains. A different transition
history could make a Sideways or Bull score zero, negative, or unavailable. The
audit tests exercise those cases explicitly. The two policy arrays are separate
objects, and an independent scalar ledger reproduced the equal results.

The complete [generated audit](results/information-audit-v1/report.md) reports
score distributions by regime, veto reasons, signal/momentum disagreements, and
exact ledger equality at all four predeclared costs. Its per-decision CSV files
make every count inspectable. The preceding development decision that can fill
at the first evaluation close is checked separately from the 1,508/2,192 counts.

## What the forecast improvement does establish

As an additional diagnostic, freeze each asset's transition matrix using only
labels before 2020, then use its row for the current regime throughout 2020–2025.
All comparisons below use identical available next-regime forecast dates.

| Mean multiclass Brier score; lower is better | SPY | BTC-USD |
|---|---:|---:|
| Hard persistence | 0.280027 | 0.337745 |
| Frozen pre-2020 transition rows | 0.236227 | 0.288114 |
| Expanding transition rows | 0.234490 | 0.287255 |
| Expanding minus frozen | -0.001737 | -0.000859 |

The fixed regime-conditioned forecast accounts for approximately 96.2% and
98.3% of the expanding model's improvement over hard persistence. These are
descriptive point estimates; this audit does not claim statistical significance
for the small expanding-versus-frozen differences.

Persistence has zero error when the next regime is unchanged and an error of
two when it changes. A probability row can improve the aggregate Brier score by
allowing some probability of change, while making no new directional trading
decision. Adjacent 20-bar labels also share 19 observations. Better forecasts of
those labels do not establish better forecasts of the executable price return
from close t+1 to close t+2.

## One next experiment

The [preregistered prospective experiment](NEXT_EXPERIMENT.md) compares continuous
Markov sizing against fixed regime-conditioned sizing, with momentum eligibility
and v2 decision/fill timing held constant. The fixed control separates the
current regime's information from the additional value of updating transition
probabilities. Plain momentum remains a descriptive reference.

The prospective ledger must account for passive weight drift when charging
fractional rebalances. V2's target-change cost convention does not include those
maintenance trades; the completed 0/1 long-or-cash benchmark is unaffected. The
new protocol specifies self-financing accounting for all three prospective
policies and requires synthetic accounting tests before activation.

The evaluation is 2026-10-01 through 2027-09-30. The protocol fixes the policy,
costs, success criteria, uncertainty method, data checks, and failure/inconclusive
outcomes before this period. The inspected 2015–2025 snapshots remain diagnostic
evidence; the new sizing rules have not been backtested against that period.
No post-2025 price series was acquired or evaluated for this research audit.

The prospective outcome cannot be known now. If its predeclared gates do not
pass, the default project role remains descriptive regime analysis; a favorable
result would justify further validation, not establish a deployable trading edge.

## Frozen baseline and review evidence

- Baseline commit: `3d077ae7ce9b3ab0246f3962daf937331bc565fe`.
- Baseline merge: `main` fast-forwarded to this exact reviewed commit on
  2026-09-28 America/Chicago, with explicit user approval. The audit is a
  separate follow-up branch.
- Input manifest SHA-256:
  `f18196b540cc0164e3fdbb039ca1c8798a9ba9152894c64e459af24229e509d6`.
- [Exact baseline CI](https://github.com/rmabry/markov-hedge-fund-method/actions/runs/36383408841):
  all four Windows/Ubuntu × Python 3.10/3.13 jobs passed.
- Independent review found no blocking aliasing, look-ahead, execution, or scoring
  defect; it reproduced every eligible transition forecast, all three 10 bps
  scalar ledgers, and the saved Brier scores. Fourteen targeted tests passed.
- [v2 release checklist](../docs/RELEASE_CHECKLIST.md) records the earlier full
  regression suite and actual TradingView runtime evidence.
- Audit regression sequence: all six new tests failed because the audit did
  not yet exist, then passed after implementation. The full offline Windows
  Python 3.13 suite passed **106 tests and 8 subtests**. Tests cover causal
  decisions, actual vetoes versus already-cash observations, known Brier errors,
  missing frozen rows, independent real-data counts, exact ledgers, deterministic
  output, strict JSON, LF serialization, and preservation of baseline results.
- The documented `uv run --locked --offline python scripts/signal_audit.py`
  command reproduced all four audit files byte for byte. Frozen protocol
  reference hashes also verified.

The baseline data, evaluation results, model parameters, and Pine source remain
unchanged by this audit. The follow-up artifacts explicitly label 2020–2025 as
already inspected; the original historical report remains the record of that
earlier, predeclared retrospective evaluation.
