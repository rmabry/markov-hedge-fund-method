"""Offline diagnostic of the inspected 2020-2025 regime-filter evaluation.

This module never acquires prices or changes the validated model or baseline.
Its frozen-development comparison is diagnostic, not a newly untouched test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

if __package__:
    from . import markov_regime as core
    from . import research_evaluation as research
else:
    import markov_regime as core
    import research_evaluation as research


ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "3d077ae7ce9b3ab0246f3962daf937331bc565fe"
START = "2020-01-01"
END = "2025-12-31"
WINDOW = 20
THRESHOLD = 0.05
MIN_TRAIN = 252
PROBABILITIES = ["bear", "sideways", "bull"]
STUDY_KIND = "Post-evaluation diagnostic; not an untouched holdout"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def decision_frame(close: pd.Series) -> pd.DataFrame:
    """All observed dates, including explicit unlabeled/ineligible warmup rows."""
    labels = core.label_regimes(close, window=WINDOW, threshold=THRESHOLD)
    signals = core.walk_forward_signals(close, labels, min_train=MIN_TRAIN)
    targets = research.strategy_targets(close, signals)
    frame = pd.DataFrame(index=close.index)
    frame.index.name = "date"
    frame["close"] = close
    frame["rolling_return_20"] = close / close.shift(WINDOW) - 1
    frame["state"] = labels.reindex(close.index).astype("Int64")
    frame["regime"] = frame.state.map(dict(enumerate(core.STATES)))
    frame[PROBABILITIES + ["signal"]] = signals.reindex(close.index)[PROBABILITIES + ["signal"]]
    frame["eligible"] = signals.eligible.reindex(close.index, fill_value=False)
    frame["momentum"] = targets["momentum"]
    frame["filtered_momentum"] = targets["filtered_momentum"]
    return frame


def _score_summary(scores: pd.Series) -> dict:
    names = ["min", "q05", "median", "q95", "max", "mean", "std"]
    if scores.empty:
        return dict.fromkeys(names)
    return {"min": float(scores.min()), "q05": float(scores.quantile(.05)),
            "median": float(scores.median()), "q95": float(scores.quantile(.95)),
            "max": float(scores.max()), "mean": float(scores.mean()),
            "std": float(scores.std(ddof=0))}


def summarize_decisions(frame: pd.DataFrame) -> dict:
    """Separate actual momentum vetoes from signals observed while already cash.

    Score distributions and sign counts use eligible, finite forecasts only.
    Ineligible bars and eligible-but-unavailable bars are separate categories.
    """
    eligible = frame.eligible.eq(True)
    finite = pd.Series(np.isfinite(frame.signal.to_numpy(dtype=float)), index=frame.index)
    available = eligible & finite
    long = frame.momentum.eq(1)
    veto = long & frame.filtered_momentum.eq(0)
    reasons = {"negative_score": int((veto & available & frame.signal.lt(0)).sum()),
               "zero_score": int((veto & available & frame.signal.eq(0)).sum()),
               "unavailable_score": int((veto & eligible & ~finite).sum()),
               "ineligible": int((veto & ~eligible).sum())}
    if sum(reasons.values()) != int(veto.sum()):
        raise ValueError("Filtered targets contain a veto not explained by the declared policy.")
    by_state = {}
    for state, name in enumerate(core.STATES):
        selected = frame.state.eq(state).fillna(False)
        observed = selected & available
        scores = frame.loc[observed, "signal"]
        by_state[name] = {
            "observations": int(selected.sum()), "eligible": int((selected & eligible).sum()),
            "available": int(observed.sum()), "unavailable": int((selected & eligible & ~finite).sum()),
            "ineligible": int((selected & ~eligible).sum()), "momentum_long": int((selected & long).sum()),
            "filter_vetoes": int((selected & veto).sum()), "positive_scores": int(scores.gt(0).sum()),
            "zero_scores": int(scores.eq(0).sum()), "negative_scores": int(scores.lt(0).sum()),
            "score_summary": _score_summary(scores),
        }
    known = available & frame.state.notna()
    sign_match = (np.sign(frame.loc[known, "signal"].to_numpy()) ==
                  np.where(frame.loc[known, "state"].eq(0), -1, 1))
    return {
        "observations": len(frame), "eligible": int(eligible.sum()), "available": int(available.sum()),
        "unavailable": int((eligible & ~finite).sum()), "ineligible": int((~eligible).sum()),
        "unlabeled": int(frame.state.isna().sum()), "momentum_long": int(long.sum()),
        "filtered_long": int(frame.filtered_momentum.eq(1).sum()), "filter_vetoes": int(veto.sum()),
        "veto_reasons": reasons,
        "positive_score_while_momentum_cash": int((available & frame.signal.gt(0) & ~long).sum()),
        "target_mismatches": int(frame.momentum.ne(frame.filtered_momentum).sum()),
        "same_sign_as_non_bear_rule": bool(len(sign_match) and sign_match.all()),
        "sign_comparison_observations": int(known.sum()), "by_state": by_state,
    }


def decompose_forecasts(labels: pd.Series, signals: pd.DataFrame, *, start: str, end: str) -> dict:
    """Compare identical dates, explicitly counting unavailable frozen rows.

    The frozen table fits only labels strictly before start; it is selected
    after inspection as a diagnostic and is not an independent validation set.
    Changed/unchanged groups describe realized outcomes, never entry features.
    """
    start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
    if start_date > end_date:
        raise ValueError("Forecast start must not follow end.")
    if not isinstance(labels.index, pd.DatetimeIndex) or not labels.index.is_unique or not labels.index.is_monotonic_increasing:
        raise ValueError("Labels require unique sorted dates.")
    core.build_transition_matrix(labels)  # Validate the discrete state contract.
    development = labels.loc[labels.index < start_date]
    frozen = core.build_transition_matrix(development)
    following = labels.shift(-1)
    next_dates = pd.Series(labels.index, index=labels.index).shift(-1)
    mask = (labels.index >= start_date) & next_dates.le(end_date) & following.notna()
    dates = labels.index[mask]
    evidence = signals.reindex(dates)
    predictions = evidence[PROBABILITIES].to_numpy(dtype=float)
    eligible = evidence.eligible.eq(True).to_numpy(dtype=bool)
    available = eligible & np.isfinite(predictions).all(axis=1)
    if ((predictions[available] < 0).any() or
            not np.allclose(predictions[available].sum(axis=1), 1, rtol=0, atol=1e-10)):
        raise ValueError("Available forecast rows must be normalized nonnegative probabilities.")
    errors = {key: [] for key in ("markov", "persistence", "historical_frequency", "frozen_development")}
    changed, frozen_available = [], []
    counts = np.eye(3)[labels.to_numpy(dtype=int)].cumsum(axis=0)
    for offset in np.flatnonzero(available):
        date = dates[offset]
        pos = labels.index.get_loc(date)
        if pos < 1:
            raise ValueError("Eligible forecasts require observations before their decision date.")
        current, actual = int(labels.loc[date]), int(following.loc[date])
        truth = np.eye(3)[actual]
        probabilities = {"markov": predictions[offset], "persistence": np.eye(3)[current],
                         "historical_frequency": counts[pos - 1] / pos,
                         "frozen_development": frozen[current]}
        for key, prediction in probabilities.items():
            errors[key].append(float(np.square(prediction - truth).sum()))
        changed.append(current != actual)
        frozen_available.append(bool(np.isfinite(frozen[current]).all()))
    errors = {key: np.asarray(values, dtype=float) for key, values in errors.items()}
    changed = np.asarray(changed, dtype=bool)
    matched = np.asarray(frozen_available, dtype=bool)
    usual = ["markov", "persistence", "historical_frequency"]

    def scores(selected, names):
        n = int(selected.sum())
        return {"observations": n,
                "brier": {key: float(errors[key][selected].mean()) if n else None for key in names}}

    all_available = np.ones(len(changed), dtype=bool)
    frozen_comparison = scores(matched, usual + ["frozen_development"])
    frozen_comparison["excluded_missing_frozen_row"] = int((~matched).sum())
    frozen_comparison["unavailable_reason"] = None if matched.any() else "no_matched_available_frozen_rows"
    return _json_safe({
        "opportunities": len(dates), "eligible": int(eligible.sum()),
        "markov_available": int(available.sum()), "markov_unavailable": int((~available).sum()),
        "all_markov_available": scores(all_available, usual),
        "by_realized_transition": {"unchanged": scores(~changed, usual), "changed": scores(changed, usual)},
        "matched_with_frozen_development": frozen_comparison,
        "frozen_development": {
            "labels": len(development), "transitions": max(len(development) - 1, 0),
            "date_start": str(development.index.min().date()) if len(development) else None,
            "date_end": str(development.index.max().date()) if len(development) else None,
            "transition_matrix": frozen.tolist(),
        },
        "brier_definition": "Mean sum of squared class errors, range 0..2; lower is better",
        "grouping_warning": "Changed/unchanged is an ex-post outcome decomposition, not a tradable feature",
    })


def audit_snapshot(directory: Path | str) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Verify frozen inputs and audit decisions/ledgers without running a new strategy."""
    directory = Path(directory)
    prices, manifest = research.load_snapshot(directory)
    source_paths = ["scripts/markov_regime.py", "scripts/research_evaluation.py", "scripts/signal_audit.py"]
    result = {
        "schema_version": 1, "study_kind": STUDY_KIND, "baseline_commit": BASELINE_COMMIT,
        "protocol": {"start": START, "end": END, "window": WINDOW, "threshold": THRESHOLD,
                     "min_train": MIN_TRAIN, "cost_bps": list(research.COSTS_BPS),
                     "training": "Transitions strictly within labels[:t] before the decision date",
                     "execution": "Decision t, fill t+1, earn return ending t+2; initial flat and terminal liquidation"},
        "provenance": {"manifest_sha256": _sha256(directory / "manifest.json"),
                       "snapshot": manifest,
                       "dependency_versions": research._versions(),
                       "source_sha256": {path: _sha256(ROOT / path) for path in source_paths},
                       "validated_baseline_result_sha256": _sha256(ROOT / "research/results/baseline-v1/evaluation.json")},
        "assets": {},
    }
    holdout_frames = {}
    for asset, close in prices.items():
        full = decision_frame(close)
        frame = full.loc[START:END].copy()
        holdout_frames[asset] = frame
        summary = summarize_decisions(frame)
        first = close.index.get_loc(frame.index[0])
        if first == 0:
            raise ValueError("The audit requires the pre-evaluation decision observation.")
        preceding = full.iloc[first - 1]
        previous_identical = bool(preceding.momentum == preceding.filtered_momentum)
        cases = {}
        for cost in research.COSTS_BPS:
            baseline = core.execution_ledger(close, full.momentum, cost_bps=cost, start=START, end=END)
            filtered = core.execution_ledger(close, full.filtered_momentum, cost_bps=cost, start=START, end=END)
            cases[str(cost)] = {
                "identical": baseline.equals(filtered),
                "position_mismatches": int(baseline.position.ne(filtered.position).sum()),
                "net_return_mismatches": int(baseline.net_return.ne(filtered.net_return).sum()),
                "max_absolute_net_return_difference": float((filtered.net_return - baseline.net_return).abs().max()),
                "max_absolute_equity_difference": float((filtered.equity - baseline.equity).abs().max()),
            }
        labels = core.label_regimes(close, window=WINDOW, threshold=THRESHOLD)
        signals = core.walk_forward_signals(close, labels, min_train=MIN_TRAIN)
        explanation = (
            "On these inspected dates the learned score was negative in Bear and positive in Sideways/Bull. "
            "Positive 20-bar momentum cannot be Bear under the +/-5% labels. The positive-score gate therefore "
            "vetoed no positive-momentum decisions and was empirically redundant for this policy. "
            "This sign pattern is observed, not guaranteed for other histories or future dates."
            if summary["same_sign_as_non_bear_rule"] and not summary["filter_vetoes"] and not summary["unavailable"] and not summary["ineligible"]
            else "The observed eligibility/sign pattern does not establish complete gate redundancy; inspect the veto counts and ledger differences."
        )
        result["assets"][asset] = {
            "date_start": str(frame.index.min().date()), "date_end": str(frame.index.max().date()),
            "decisions": summary,
            "execution": {"pre_evaluation_decision_date": str(full.index[first - 1].date()),
                          "pre_evaluation_momentum": float(preceding.momentum),
                          "pre_evaluation_filtered_momentum": float(preceding.filtered_momentum),
                          "pre_evaluation_decision_identical": previous_identical,
                          "cost_cases": cases,
                          "all_cost_cases_identical": bool(all(case["identical"] for case in cases.values()))},
            "forecasts": decompose_forecasts(labels, signals, start=START, end=END),
            "interpretation": explanation,
        }
    result["limits"] = [
        "The inspected 2020-2025 period is not an untouched holdout for selecting another rule.",
        "A lower regime Brier score does not establish a useful forecast of an executable price return.",
        "Regimes use overlapping trailing 20-bar returns; next-state persistence is partly mechanical.",
        "The frozen-development state-conditioned table is an added diagnostic, not a preregistered original comparator.",
        "No returns of newly selected strategies are evaluated here; no future profitability is established.",
        "Yahoo adjusted prices are retrospective and may contain later source revisions, not point-in-time vendor data.",
    ]
    result = _json_safe(result)
    json.dumps(result, allow_nan=False)
    return result, holdout_frames


def _format(value) -> str:
    return "unavailable" if value is None else f"{value:.6f}"


def render_report(result: dict) -> str:
    lines = ["# Regime signal information audit", "", result["study_kind"] + ".", "",
             f"Validated baseline: `{result['baseline_commit']}`. Frozen observations only: 2020-2025; "
             "20-bar simple returns, +/-5% regimes, minimum training 252 labels. No price acquisition or parameter search.", "",
             f"Input manifest SHA-256: `{result['provenance']['manifest_sha256']}`. "
             "Source hashes and the original acquisition provenance are recorded in audit.json.", "",
             "The question is whether the estimated transition probabilities changed the declared trading decisions. "
             "Identical decisions can coexist with better probability forecasts of regime labels.", ""]
    for asset, item in result["assets"].items():
        summary, execution, forecasts = item["decisions"], item["execution"], item["forecasts"]
        lines += [f"## {asset}", "", item["interpretation"], "",
                  f"{summary['observations']} decision dates; {summary['momentum_long']} positive-momentum decisions; "
                  f"**{summary['filter_vetoes']} filter vetoes**. Eligible unavailable scores: {summary['unavailable']}; "
                  f"ineligible: {summary['ineligible']}. Positive scores while momentum already held cash: "
                  f"{summary['positive_score_while_momentum_cash']} (these are not vetoes).", "",
                  "| State | Dates | Available | Momentum long | Positive / zero / negative scores | Min | Median | Max |",
                  "|---|---:|---:|---:|---|---:|---:|---:|"]
        for name, state in summary["by_state"].items():
            scores = state["score_summary"]
            lines.append(f"| {name} | {state['observations']} | {state['available']} | {state['momentum_long']} | "
                         f"{state['positive_scores']} / {state['zero_scores']} / {state['negative_scores']} | "
                         f"{_format(scores['min'])} | {_format(scores['median'])} | {_format(scores['max'])} |")
        lines += ["", f"Pre-evaluation decision ({execution['pre_evaluation_decision_date']}) identical: "
                  f"**{execution['pre_evaluation_decision_identical']}**. Full ledgers exactly identical at all "
                  f"0/5/10/25 bps cost assumptions: **{execution['all_cost_cases_identical']}**. "
                  "Comparison includes the initial fill and final liquidation, not only rounded report metrics.", "",
                  "### Forecast diagnostics", "",
                  "Changed/unchanged labels are realized outcomes used only to explain forecast errors. "
                  "All columns within each row use identical dates; summed multiclass Brier is lower when better.", "",
                  "| Realized next state | Observations | Adaptive Markov | Persistence | Historical frequency |",
                  "|---|---:|---:|---:|---:|"]
        for name, group in forecasts["by_realized_transition"].items():
            lines.append(f"| {name} | {group['observations']} | " + " | ".join(
                _format(group["brier"][key]) for key in ("markov", "persistence", "historical_frequency")) + " |")
        matched = forecasts["matched_with_frozen_development"]
        lines += ["", "A state-conditioned transition table fitted only before 2020 is held fixed throughout "
                  "this diagnostic. It tests whether the ongoing updates improve on a fixed table, rather than "
                  "only on an overconfident persistence forecast.", "",
                  f"Matched dates: {matched['observations']}; excluded due to missing frozen outgoing rows: "
                  f"{matched['excluded_missing_frozen_row']}. Adaptive-available opportunities: "
                  f"{forecasts['markov_available']}/{forecasts['opportunities']}.", "",
                  "| Forecast on matched dates | Brier |", "|---|---:|"]
        for name, score in matched["brier"].items():
            lines.append(f"| {name} | {_format(score)} |")
        lines.append("")
    lines += ["## Interpretation limits", ""] + [f"- {limit}" for limit in result["limits"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "research/data/baseline-v1")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "research/results/information-audit-v1")
    args = parser.parse_args(argv)
    try:
        output = args.output_dir.resolve()
        for protected in (args.data_dir.resolve(), (ROOT / "research/results/baseline-v1").resolve()):
            if output == protected or protected in output.parents:
                raise ValueError("Audit output must be separate from frozen inputs and baseline results.")
        result, decisions = audit_snapshot(args.data_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "audit.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
                                            encoding="utf-8", newline="\n")
        (output / "report.md").write_text(render_report(result), encoding="utf-8", newline="\n")
        for asset, frame in decisions.items():
            frame.to_csv(output / f"{asset}-decisions.csv", date_format="%Y-%m-%d", float_format="%.17g",
                         encoding="utf-8", lineterminator="\n")
        print(json.dumps({"audit": str(output / "audit.json"), "report": str(output / "report.md")}, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, allow_nan=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
