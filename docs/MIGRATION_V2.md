# Migration to v2

v2 declares `schema_version: 2`. Consumers must handle null values before using
probabilities or metrics. Changed behavior is intentional and versioned.

| Area | v1 | v2 |
|---|---|---|
| Unobserved transition rows | Three zeros | Three nulls and observed transition counts |
| Unsupported current state | Zero signal despite absent evidence | Null signal and probabilities, with a reason |
| Stationary output | Nearest eigenvalue without uniqueness validation | Unique validated solution or nulls with a reason |
| JSON unavailable metrics | Nonstandard NaN tokens | Standard nulls; strict serialization |
| Drawdown | First post-return equity establishes peak | Starting equity of 1 included |
| Execution | Same-close fill implicit | Next-observed-close fill; return starts one close later |
| Trade count | Evaluated bars called trades | n_periods for bars; n_trades for entries/reversals |
| Costs/annualization | Zero costs; fixed 252 | Explicit cost_bps and periods_per_year |
| HMM setup | Installed for every script launch | Explicit opt-in dependency |
| Pine regimes | Log returns | Simple returns matching Python defaults |
| Manual onboarding | Separate generated implementation | Same maintained source as plugin |

`next_state_probabilities` continues to describe one observation ahead.
`forecast` contains the requested `horizon` and `probabilities`; horizon zero
is the known current-state distribution. Internal numerical helpers use an
entirely NaN row for an unsupported distribution. JSON converts this to nulls;
do not replace missing evidence with an unstated prior in a downstream client.

The sign-based standalone backtest differs from the long-or-cash benchmark.
Proportional signal sizing and stationary-based sizing are not validated by that
benchmark. Risk integrations must check availability and evaluate their own policy.
