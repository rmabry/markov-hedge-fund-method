"""Independent analytical examples shared with the actual Pine diagnostics."""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import markov_regime as model


CONTRACT = json.loads((Path(__file__).parent / "fixtures/model_contract.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CONTRACT["threshold_cases"], ids=lambda case: case["id"])
def test_shared_threshold_examples(case):
    if case["return"] is None:
        close = pd.Series([100.0], index=pd.date_range("2024-01-01", periods=1))
        assert model.label_regimes(close, window=1).empty
    else:
        close = pd.Series([100.0, 100.0 * (1 + case["return"])],
                          index=pd.date_range("2024-01-01", periods=2))
        assert model.label_regimes(close, window=1).iloc[0] == case["expected"]


@pytest.mark.parametrize("case", CONTRACT["transition_cases"], ids=lambda case: case["id"])
def test_shared_transition_examples(case):
    matrix = model.build_transition_matrix(pd.Series(case["labels"]))
    np.testing.assert_allclose(matrix, np.asarray(case["expected_matrix"], dtype=float), equal_nan=True)
    returns = np.asarray([-0.1, 0.0, 0.1])[case["labels"]]
    prices = np.r_[100.0, 100.0 * np.cumprod(1 + returns)]
    close = pd.Series(prices, index=pd.date_range("2024-01-01", periods=len(prices)))
    result = model.analyze(close, source="shared fixture", window=1, min_train=2, hmm=False)
    assert result["transition_counts"] == case["expected_counts"]


@pytest.mark.parametrize("case", CONTRACT["stationary_cases"], ids=lambda case: case["id"])
def test_shared_stationary_examples(case):
    matrix = np.asarray(case["matrix"], dtype=float)
    if case["expected_distribution"] is None:
        with pytest.raises(model.UnavailableEstimate):
            model.stationary_distribution(matrix)
    else:
        actual = model.stationary_distribution(matrix)
        np.testing.assert_allclose(actual, case["expected_distribution"], atol=1e-10)
        np.testing.assert_allclose(actual @ matrix, actual, atol=1e-10)


@pytest.mark.parametrize("permutation", list(itertools.permutations(range(3))))
def test_stationary_semantics_survive_state_reordering(permutation):
    expected = np.array([0.2, 0.3, 0.5])
    matrix = np.tile(expected, (3, 1))
    order = np.array(permutation)
    permuted = matrix[np.ix_(order, order)]
    np.testing.assert_allclose(model.stationary_distribution(permuted), expected[order], atol=1e-10)


@pytest.mark.parametrize("horizon", [0, 1, 2, 5, 50])
def test_full_evidence_forecasts_match_independent_matrix_powers(horizon):
    matrix = np.array([[0.8, 0.2, 0], [0.1, 0.6, 0.3], [0.05, 0.15, 0.8]])
    actual = model.nstep_forecast(matrix, horizon)
    np.testing.assert_allclose(actual, np.linalg.matrix_power(matrix, horizon), atol=1e-10)
    np.testing.assert_allclose(actual.sum(axis=1), 1.0, atol=1e-10)
