"""Offline regression checks for the frozen research protocol."""
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def research():
    path = Path(__file__).resolve().parents[1] / "scripts" / "research_evaluation.py"
    assert path.exists(), "The offline research runner has not been implemented"
    return importlib.import_module("scripts.research_evaluation")


@pytest.fixture
def prices():
    result = {}
    for asset, freq in (("SPY", "B"), ("BTC-USD", "D")):
        dates = pd.date_range("2015-01-01", "2025-12-31", freq=freq)
        t = np.arange(len(dates))
        result[asset] = pd.Series(100 * np.exp(0.0002 * t + 0.18 * np.sin(t / 31)), index=dates)
    return result


def test_freeze_records_provenance_and_refuses_overwrite(tmp_path, prices):
    r = research()
    manifest = r.freeze_snapshot(tmp_path / "snapshot", prices,
                                 acquired_at="2026-09-28T00:00:00Z", versions={"yfinance": "test"})
    assert b"\r\n" not in (tmp_path / "snapshot" / "manifest.json").read_bytes()
    assert manifest["requested_start"] == "2015-01-01"
    assert manifest["requested_end_inclusive"] == "2025-12-31"
    assert manifest["assets"]["SPY"]["adjustment"] == "dividend_and_split_adjusted"
    assert manifest["assets"]["SPY"]["source_url"] == "https://finance.yahoo.com/quote/SPY/history/"
    assert manifest["assets"]["BTC-USD"]["adjustment"] == "unadjusted_close"
    assert manifest["assets"]["BTC-USD"]["rows"] > manifest["assets"]["SPY"]["rows"]
    loaded, restored = r.load_snapshot(tmp_path / "snapshot")
    assert restored == manifest
    np.testing.assert_allclose(loaded["SPY"], prices["SPY"])
    with pytest.raises(FileExistsError, match="overwrite"):
        r.freeze_snapshot(tmp_path / "snapshot", prices, acquired_at="later")


def test_snapshot_checksum_rejects_changed_prices(tmp_path, prices):
    r = research()
    r.freeze_snapshot(tmp_path, prices, acquired_at="2026-09-28T00:00:00Z")
    path = tmp_path / "SPY.csv"
    path.write_text(path.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        r.load_snapshot(tmp_path)


def test_targets_do_not_trade_unavailable_regime_signals():
    r = research()
    dates = pd.date_range("2020-01-01", periods=25)
    close = pd.Series(np.arange(100, 125), index=dates)
    signals = pd.DataFrame({"signal": [0.8, np.nan, -0.2, 0.8, 0.8],
                            "eligible": [True, True, True, False, True]}, index=dates[-5:])
    targets = r.strategy_targets(close, signals)
    assert targets["buy_and_hold"].eq(1).all()
    assert targets["momentum"].iloc[-5:].tolist() == [1, 1, 1, 1, 1]
    assert targets["filtered_momentum"].iloc[-5:].tolist() == [1, 0, 0, 0, 1]


def test_brier_uses_next_state_and_matched_available_dates():
    r = research()
    dates = pd.date_range("2019-12-30", periods=6)
    labels = pd.Series([0, 0, 1, 2, 2, 0], index=dates)
    signals = pd.DataFrame({"bear": [np.nan, np.nan, 0, np.nan, 1, np.nan],
                            "sideways": [np.nan, np.nan, 0, np.nan, 0, np.nan],
                            "bull": [np.nan, np.nan, 1, np.nan, 0, np.nan],
                            "signal": [np.nan, np.nan, 1, np.nan, -1, np.nan],
                            "eligible": [False, False, True, True, True, True]}, index=dates)
    result = r.forecast_scores(labels, signals, start="2020-01-01", end="2020-01-04")
    assert result["opportunities"] == 3
    assert result["available"] == 2
    assert result["coverage"] == pytest.approx(2 / 3)
    assert result["brier"]["markov"] == 0
    assert result["brier"]["persistence"] == 2
    assert result["brier"]["historical_frequency"] == pytest.approx((2 + 0.375) / 2)
    assert result["by_current_state"]["Bull"]["opportunities"] == 2


def test_evaluation_is_offline_deterministic_and_has_all_fixed_cases(tmp_path, prices, monkeypatch):
    r = research()
    r.freeze_snapshot(tmp_path / "snapshot", prices, acquired_at="2026-09-28T00:00:00Z")
    monkeypatch.setattr(r, "fetch_snapshot", lambda *a, **kw: pytest.fail("Evaluation tried to download"))
    first = r.evaluate_snapshot(tmp_path / "snapshot")
    second = r.evaluate_snapshot(tmp_path / "snapshot")
    assert json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(second, sort_keys=True, allow_nan=False)
    assert first["schema_version"] == 2
    assert first["protocol"]["holdout"] == {"start": "2020-01-01", "end": "2025-12-31"}
    for asset in ("SPY", "BTC-USD"):
        cases = first["assets"][asset]["strategies"]
        assert set(cases) == {"buy_and_hold", "momentum", "filtered_momentum"}
        assert set(cases["momentum"]) == {"0", "5", "10", "25"}
        assert first["assets"][asset]["periods_per_year"] == (252 if asset == "SPY" else 365)
        metrics = cases["buy_and_hold"]["10"]
        dates = prices[asset].loc["2020-01-01":"2025-12-31"].index
        elapsed_years = (dates[-1] - dates[0]).total_seconds() / (365.2425 * 86400)
        assert metrics["cagr"] == pytest.approx((1 + metrics["total_return"]) ** (1 / elapsed_years) - 1)
    report = r.render_report(first)
    assert "retrospective" in report.lower()
    assert "Profitability" in report
    assert "BTC-USD" in report and "10 bps" in report


def test_no_available_forecast_is_null_with_explicit_coverage():
    r = research()
    dates = pd.date_range("2020-01-01", periods=3)
    labels = pd.Series([0, 1, 2], index=dates)
    signals = pd.DataFrame({"bear": np.nan, "sideways": np.nan, "bull": np.nan,
                            "signal": np.nan, "eligible": True}, index=dates)
    result = r.forecast_scores(labels, signals, start="2020-01-01", end="2020-01-03")
    assert result["opportunities"] == 2
    assert result["available"] == 0 and result["coverage"] == 0
    assert all(value is None for value in result["brier"].values())
    assert result["unavailable_reason"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("name", ["evaluation.json", "report.md"])
def test_cli_outputs_use_platform_independent_lf(tmp_path, prices, name):
    r = research()
    data = tmp_path / "snapshot"
    output = tmp_path / "result"
    r.freeze_snapshot(data, prices, acquired_at="2026-09-28T00:00:00Z")
    assert r.main(["evaluate", "--data-dir", str(data), "--output-dir", str(output)]) == 0
    content = (output / name).read_bytes()
    assert b"\n" in content
    assert b"\r\n" not in content


@pytest.mark.parametrize("bad", ["duplicate", "zero", "infinite", "unsorted"])
def test_snapshot_rejects_invalid_prices(tmp_path, prices, bad):
    r = research()
    series = prices["SPY"].copy()
    if bad == "duplicate":
        series.index = series.index.to_list()[:-1] + [series.index[-2]]
    elif bad == "zero":
        series.iloc[5] = 0
    elif bad == "infinite":
        series.iloc[5] = np.inf
    else:
        series = series.iloc[::-1]
    prices["SPY"] = series
    with pytest.raises(ValueError):
        r.freeze_snapshot(tmp_path, prices, acquired_at="2026-09-28T00:00:00Z")
