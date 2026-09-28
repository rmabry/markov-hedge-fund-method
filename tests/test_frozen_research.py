"""Verify the shipped Yahoo snapshots and reproduce the saved research numbers."""
import json
import math
from pathlib import Path

import research_evaluation as research


ROOT = Path(__file__).resolve().parents[1]


def assert_same_result(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_same_result(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for found, wanted in zip(actual, expected):
            assert_same_result(found, wanted)
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10)
    else:
        assert actual == expected


def test_shipped_snapshots_reproduce_saved_results_offline():
    expected = json.loads((ROOT / "research/results/baseline-v1/evaluation.json").read_text(encoding="utf-8"))
    actual = research.evaluate_snapshot(ROOT / "research/data/baseline-v1")
    # The supported Python/dependency matrix differs; numerical conclusions must not.
    expected.pop("evaluation_dependencies")
    actual.pop("evaluation_dependencies")
    assert_same_result(actual, expected)
