"""Behavioral checks for the offline, post-evaluation information audit."""
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def audit():
    path = ROOT / "scripts/signal_audit.py"
    assert path.exists(), "The reproducible signal audit has not been implemented"
    return importlib.import_module("scripts.signal_audit")


def test_audit_distinguishes_vetoes_from_positive_scores_while_momentum_is_cash():
    a = audit()
    frame = pd.DataFrame({
        "state": [1, 1, 1, 1, 1, 1, 0],
        "signal": [0.02, -0.1, 0.0, np.nan, 0.2, 0.01, -0.8],
        "eligible": [True, True, True, True, False, True, True],
        "momentum": [1., 1., 1., 1., 1., 0., 0.],
        "filtered_momentum": [1., 0., 0., 0., 0., 0., 0.],
    }, index=pd.date_range("2020-01-01", periods=7))
    summary = a.summarize_decisions(frame)
    assert summary["momentum_long"] == 5
    assert summary["filter_vetoes"] == 4
    assert summary["veto_reasons"] == {"negative_score": 1, "zero_score": 1,
                                        "unavailable_score": 1, "ineligible": 1}
    assert summary["positive_score_while_momentum_cash"] == 1
    assert summary["by_state"]["Sideways"]["positive_scores"] == 2
    assert summary["by_state"]["Sideways"]["available"] == 4
    assert summary["by_state"]["Bull"]["score_summary"]["min"] is None
    assert summary["same_sign_as_non_bear_rule"] is False
    json.dumps(summary, allow_nan=False)


def test_audit_decisions_are_causal_when_later_prices_change():
    a = audit()
    dates = pd.date_range("2015-01-01", periods=500)
    close = pd.Series(100 * np.exp(np.arange(500) * .001 + .15 * np.sin(np.arange(500) / 25)), index=dates)
    altered = close.copy()
    altered.iloc[400:] *= np.linspace(1, 3, 100)
    first = a.decision_frame(close)
    second = a.decision_frame(altered)
    pd.testing.assert_frame_equal(first.iloc[:400], second.iloc[:400])


def test_brier_decomposition_and_frozen_development_baseline_have_known_answers():
    a = audit()
    dates = pd.to_datetime(["2019-12-28", "2019-12-29", "2019-12-30", "2019-12-31",
                            "2020-01-01", "2020-01-02", "2020-01-03"])
    labels = pd.Series([0, 1, 2, 2, 2, 1, 0], index=dates)
    signals = pd.DataFrame({"bear": [0., .5, .5], "sideways": [.25, .5, .5],
                            "bull": [.75, 0., 0.], "eligible": True}, index=dates[-3:])
    result = a.decompose_forecasts(labels, signals, start="2020-01-01", end="2020-01-03")
    # Both scored dates change state. The frozen development row is Bull->Bull;
    # Sideways->Bull. Its squared error is therefore 2 on each date.
    assert result["matched_with_frozen_development"]["observations"] == 2
    assert result["matched_with_frozen_development"]["brier"]["frozen_development"] == 2
    assert result["matched_with_frozen_development"]["brier"]["markov"] == pytest.approx((1.125 + .5) / 2)
    assert result["by_realized_transition"]["changed"]["observations"] == 2
    assert result["by_realized_transition"]["unchanged"]["observations"] == 0
    assert result["by_realized_transition"]["unchanged"]["brier"]["markov"] is None


def test_frozen_baseline_missing_rows_do_not_silently_change_comparison_dates():
    a = audit()
    dates = pd.to_datetime(["2019-12-30", "2019-12-31", "2020-01-01", "2020-01-02", "2020-01-03"])
    labels = pd.Series([0, 0, 1, 2, 2], index=dates)
    signals = pd.DataFrame({"bear": 0., "sideways": 0., "bull": 1., "eligible": True}, index=dates[-3:])
    result = a.decompose_forecasts(labels, signals, start="2020-01-01", end="2020-01-03")
    assert result["markov_available"] == 2
    assert result["matched_with_frozen_development"]["observations"] == 0
    assert result["matched_with_frozen_development"]["excluded_missing_frozen_row"] == 2
    assert result["matched_with_frozen_development"]["brier"]["markov"] is None


def test_frozen_signal_audit_reproduces_independent_counts_and_ledgers():
    a = audit()
    result, decisions = a.audit_snapshot(ROOT / "research/data/baseline-v1")
    expected = {"SPY": (1508, 1050, 789, 261), "BTC-USD": (2192, 1205, 369, 836)}
    for asset, (observations, longs, sideways, bull) in expected.items():
        item = result["assets"][asset]
        summary = item["decisions"]
        assert summary["observations"] == observations
        assert summary["momentum_long"] == longs
        assert summary["filter_vetoes"] == 0
        assert summary["by_state"]["Sideways"]["momentum_long"] == sideways
        assert summary["by_state"]["Bull"]["momentum_long"] == bull
        assert summary["same_sign_as_non_bear_rule"] is True
        assert summary["unavailable"] == 0
        assert item["execution"]["all_cost_cases_identical"] is True
        assert item["execution"]["pre_evaluation_decision_identical"] is True
        assert decisions[asset].index.min() >= pd.Timestamp("2020-01-01")
        assert decisions[asset].index.max() <= pd.Timestamp("2025-12-31")
    assert result["study_kind"] == "Post-evaluation diagnostic; not an untouched holdout"
    json.dumps(result, allow_nan=False)


def test_audit_files_are_deterministic_strict_and_do_not_modify_baseline(tmp_path):
    a = audit()
    baseline = ROOT / "research/results/baseline-v1/evaluation.json"
    original = baseline.read_bytes()
    a.main(["--output-dir", str(tmp_path)])
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    a.main(["--output-dir", str(tmp_path)])
    second = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert first == second
    assert baseline.read_bytes() == original
    assert {"audit.json", "report.md", "SPY-decisions.csv", "BTC-USD-decisions.csv"} == first.keys()
    for content in first.values():
        assert b"\r\n" not in content
    parsed = json.loads(first["audit.json"], parse_constant=lambda x: pytest.fail(x))
    assert parsed["schema_version"] == 1
    report = first["report.md"].decode("utf-8")
    assert "not an untouched holdout" in report
    assert "redundant" in report.lower()
