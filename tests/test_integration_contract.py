"""Release regressions that cross model, execution, and reporting boundaries."""
import numpy as np
import pandas as pd
import pytest

import markov_regime as model


def test_initial_equity_loss_is_not_erased_by_the_first_recorded_peak():
    # Ten-percent synthetic entry cost makes the first evaluated equity 0.9.
    # Prices subsequently rise enough that the initial loss is the worst loss.
    close = pd.Series([100., 100., 110., 121., 133.1],
                      index=pd.date_range("2024-01-01", periods=5))
    ledger = model.execution_ledger(close, pd.Series(1., index=close.index),
                                    cost_bps=1000, start=close.index[1])
    assert ledger.equity.iloc[0] == pytest.approx(.9)
    assert model.summarize_ledger(ledger)["max_drawdown"] == pytest.approx(-.1)


def test_future_suffix_cannot_change_orders_or_earned_returns_in_the_past():
    rng = np.random.default_rng(1987)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, .035, 200))),
                      index=pd.date_range("2024-01-01", periods=200))
    changed = close.copy()
    changed.iloc[120:] *= 1.2
    ledgers = []
    for prices in (close, changed):
        labels = model.label_regimes(prices, window=5)
        signals = model.walk_forward_signals(prices, labels, min_train=10)
        targets = np.sign(signals.signal)
        ledgers.append(model.execution_ledger(prices, targets, cost_bps=10))
    pd.testing.assert_frame_equal(ledgers[0].iloc[:120], ledgers[1].iloc[:120])


def test_unavailable_forecast_closes_position_and_pays_exit_cost():
    dates = pd.date_range("2024-01-01", periods=6)
    close = pd.Series(100., index=dates)
    targets = pd.Series([1., np.nan, 0., 0., 0., 0.], index=dates)
    ledger = model.execution_ledger(close, targets, cost_bps=10)
    assert ledger.position.iloc[1] == 1
    assert ledger.position.iloc[2] == 0
    assert ledger.cost.iloc[2] == pytest.approx(.001)
    assert model.summarize_ledger(ledger)["n_periods"] == len(dates)
