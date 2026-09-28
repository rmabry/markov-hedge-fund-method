import json

import numpy as np
import pandas as pd
import pytest

from scripts import markov_regime as m


def prices(values):
    return pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values)))


def test_missing_rows_are_unknown_not_zero_probability():
    p = m.build_transition_matrix(pd.Series([1, 1, 2]))
    np.testing.assert_allclose(p[1], [0, .5, .5])
    assert np.isnan(p[[0, 2]]).all()
    assert np.isnan(m.signal_from_matrix(p, 2))
    with pytest.raises(ValueError, match="evidence"):
        m.stationary_distribution(p)


def test_forecast_preserves_supported_unreachable_rows():
    p = np.array([[np.nan] * 3, [0., 1., 0.], [np.nan] * 3])
    np.testing.assert_equal(m.nstep_forecast(p, 0), np.eye(3))
    np.testing.assert_allclose(m.nstep_forecast(p, 20)[1], [0, 1, 0])
    p[1] = [0, .5, .5]
    np.testing.assert_allclose(m.nstep_forecast(p, 1)[1], p[1])
    assert np.isnan(m.nstep_forecast(p, 2)[1]).all()


def test_stationary_distribution_unique_periodic_and_nonunique():
    p = np.array([[0., 1., 0.], [0., 0., 1.], [1., 0., 0.]])
    pi = m.stationary_distribution(p)
    np.testing.assert_allclose(pi, [1 / 3] * 3)
    np.testing.assert_allclose(pi @ p, pi)
    with pytest.raises(ValueError, match="unique"):
        m.stationary_distribution(np.eye(3))
    absorbing = np.array([[1., 0., 0.], [.5, .5, 0.], [0., .5, .5]])
    np.testing.assert_allclose(m.stationary_distribution(absorbing), [1, 0, 0], atol=1e-10)


@pytest.mark.parametrize("matrix", [np.zeros((3, 3)), np.ones((2, 2)),
    np.array([[np.nan, 0, 0], [0, 1, 0], [0, 0, 1]]),
    np.array([[-.1, 1.1, 0], [0, 1, 0], [0, 0, 1]])])
def test_invalid_matrices_are_rejected(matrix):
    with pytest.raises(ValueError):
        m.nstep_forecast(matrix, 2)


@pytest.mark.parametrize("kwargs", [{"window": -1}, {"window": 0}, {"window": 1.5},
    {"threshold": -1}, {"threshold": float("nan")}, {"min_train": -1},
    {"min_train": 1}, {"horizon": -1}, {"periods_per_year": 0}, {"cost_bps": -1}])
def test_analysis_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        m.analyze(prices([100.] * 40), source="fixture", hmm=False, **kwargs)


@pytest.mark.parametrize("values", [[100, 0, 110], [100, -1, 110],
    [100, np.inf, 110], [100, np.nan, 110]])
def test_prices_must_be_positive_and_finite(values):
    with pytest.raises(ValueError):
        m.label_regimes(prices(values), window=1)


def test_duplicate_and_unsorted_library_dates_are_rejected():
    x = prices([100., 110., 120.])
    for bad in [x.iloc[::-1], pd.concat([x, x.iloc[-1:]])]:
        with pytest.raises(ValueError):
            m.analyze(bad, source="bad", window=1, hmm=False)


def test_labels_use_simple_return_and_exclude_threshold_equality():
    x = prices([100., 125., 100., 80.])
    np.testing.assert_equal(m.label_regimes(x, window=1, threshold=.25).to_numpy(), [1, 1, 1])
    np.testing.assert_equal(m.label_regimes(x, window=1, threshold=.21).to_numpy(), [2, 1, 1])


def test_analysis_sparse_results_are_versioned_strict_json():
    result = m.analyze(prices([100., 100., 100., 110.]), source="fixture", window=1, hmm=False)
    assert result["schema_version"] == 2
    assert result["signal"] is None
    assert result["transition_matrix"][1] == [0., .5, .5]
    assert result["transition_matrix"][0] == [None] * 3
    assert set(result["stationary_distribution"].values()) == {None}
    assert result["walk_forward"]["sharpe"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("rows", ["2020-01-01,100\nbad,101", "2020-01-01,100\n2020-01-02,nope",
    "2020-01-01,100\n2020-01-01,101", "1577836800,100\n1577923200,101"])
def test_csv_rejects_bad_rows_instead_of_dropping_them(tmp_path, rows):
    path = tmp_path / "invalid.csv"
    path.write_text("date,close\n" + rows, encoding="utf-8")
    with pytest.raises(ValueError):
        m.load_csv(str(path))


def test_csv_still_autodetects_and_sorts(tmp_path):
    path = tmp_path / "valid.csv"
    path.write_text("Date,Adj Close\n2020-01-02,101\n2020-01-01,100\n", encoding="utf-8")
    assert m.load_csv(str(path)).tolist() == [100., 101.]


def test_overflowing_price_returns_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        m.label_regimes(prices([1e-300, 1e300]), window=1)


def test_slow_mixing_is_not_misclassified_as_nonunique():
    p = np.full((3, 3), 1e-11)
    np.fill_diagonal(p, 1 - 2e-11)
    np.testing.assert_allclose(m.stationary_distribution(p), [1 / 3] * 3, atol=1e-10)


def test_one_regime_label_preserves_current_regime_without_forecast():
    result = m.analyze(prices([100., 110.]), source="one-label", window=1, hmm=False)
    assert result["current_regime"] == "Bull"
    assert result["signal"] is None
    assert result["transition_matrix"] == [[None] * 3] * 3
    assert result["walk_forward"]["n_periods"] == 0
    json.dumps(result, allow_nan=False)
