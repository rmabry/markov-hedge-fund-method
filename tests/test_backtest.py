import numpy as np
import pandas as pd
import pytest

from scripts import markov_regime as m


def prices(values):
    return pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values)))


def test_execution_waits_a_close_then_earns_the_following_return():
    assert hasattr(m, "execution_ledger"), "The shared causal execution ledger is missing"
    x = prices([100., 200., 220., 198.])
    targets = pd.Series([1., 1., -1., 1.], index=x.index)
    ledger = m.execution_ledger(x, targets, cost_bps=10)
    np.testing.assert_allclose(ledger.position, [0, 1, 1, 0])
    np.testing.assert_allclose(ledger.gross_return, [0, 0, .1, -.1], atol=1e-12)
    np.testing.assert_allclose(ledger.turnover, [0, 1, 0, 1])
    np.testing.assert_allclose(ledger.cost, [0, .001, 0, .001])
    np.testing.assert_allclose(ledger.equity, np.cumprod(1 + ledger.net_return))


def test_evaluation_begins_flat_and_allows_previous_decision_to_fill():
    assert hasattr(m, "execution_ledger")
    x = prices([100., 90., 81., 90.])
    ledger = m.execution_ledger(x, pd.Series(1., index=x.index), start=x.index[1])
    np.testing.assert_allclose(ledger.position, [1, 1, 0])
    np.testing.assert_allclose(ledger.gross_return, [0, -.1, 1 / 9], atol=1e-12)
    result = m.summarize_ledger(ledger)
    assert result["max_drawdown"] == pytest.approx(-.1)
    assert result["n_trades"] == 1
    assert result["n_periods"] == 3
    assert result["turnover"] == 2


def test_signal_prefix_equivalence_and_future_suffix_invariance():
    assert hasattr(m, "walk_forward_signals")
    x = prices(100 * np.cumprod(1 + np.random.default_rng(7).normal(0, .04, 200)))
    labels = m.label_regimes(x, window=3, threshold=.025)
    signals = m.walk_forward_signals(x, labels, min_train=5)
    for t in range(5, len(labels)):
        p = m.build_transition_matrix(labels.iloc[:t])
        np.testing.assert_allclose(signals.iloc[t][["bear", "sideways", "bull"]].to_numpy(float),
                                   p[int(labels.iloc[t])], equal_nan=True)
    changed = x.copy()
    changed.iloc[100:] *= 1.5
    changed_labels = m.label_regimes(changed, window=3, threshold=.025)
    other = m.walk_forward_signals(changed, changed_labels, min_train=5)
    pd.testing.assert_frame_equal(signals.loc[:x.index[99]], other.loc[:x.index[99]])


def test_unknown_forecasts_remain_missing_and_backtest_counts_them():
    assert hasattr(m, "walk_forward_signals")
    x = prices([100., 100., 100., 100., 110., 120., 130.])
    labels = pd.Series([1, 1, 1, 1, 2, 2, 2], index=x.index)
    signals = m.walk_forward_signals(x, labels, min_train=2)
    assert signals.loc[x.index[4], "eligible"]
    assert np.isnan(signals.loc[x.index[4], "signal"])
    result = m.walk_forward_backtest(x, labels, min_train=2)
    assert result["unavailable_forecast_bars"] >= 1


def test_annualization_and_flat_strategy_metrics():
    assert hasattr(m, "summarize_ledger")
    x = prices([100., 101., 104., 102., 106.])
    ledger = m.execution_ledger(x, pd.Series(1., index=x.index))
    a = m.summarize_ledger(ledger, periods_per_year=252)
    b = m.summarize_ledger(ledger, periods_per_year=365)
    assert b["sharpe"] == pytest.approx(a["sharpe"] * np.sqrt(365 / 252))
    assert a["max_drawdown"] == b["max_drawdown"]
    flat = m.summarize_ledger(m.execution_ledger(x, pd.Series(0., index=x.index)))
    assert flat["sharpe"] is None
    assert flat["n_trades"] == 0
    assert flat["max_drawdown"] == 0


def test_reversal_cost_and_missing_target_flattening():
    assert hasattr(m, "execution_ledger")
    x = prices([100.] * 6)
    target = pd.Series([1., -1., np.nan, 1., 1., 1.], index=x.index)
    ledger = m.execution_ledger(x, target, cost_bps=10)
    np.testing.assert_allclose(ledger.position, [0, 1, -1, 0, 1, 0])
    np.testing.assert_allclose(ledger.turnover, [0, 1, 2, 1, 1, 1])
    assert m.summarize_ledger(ledger)["n_trades"] == 3


def test_cagr_uses_elapsed_calendar_time_not_bar_annualization():
    x = pd.Series([100., 100., 110.], index=pd.date_range("2020-01-01", periods=3, freq="365D"))
    ledger = m.execution_ledger(x, pd.Series(1., index=x.index))
    a = m.summarize_ledger(ledger, periods_per_year=252)
    b = m.summarize_ledger(ledger, periods_per_year=365)
    assert a["cagr"] == pytest.approx(1.1 ** (365.2425 / 730) - 1)
    assert a["cagr"] == b["cagr"]
    single = m.summarize_ledger(ledger.iloc[:1])
    assert single["cagr"] is None
    assert "cagr" in single["unavailable"]
