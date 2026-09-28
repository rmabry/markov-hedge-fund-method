# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas", "yfinance"]
# ///
"""Markov regime detection — a composable library + CLI.

This is the educational Markov framework from Roan (@RohOnChain), refactored from
the on-camera onboarding prompt into one clean, importable module.

It does five things, all asset-agnostic:

  1. label_regimes(...)        Bull / Bear / Sideways from a rolling return
  2. build_transition_matrix() MLE 3x3 transition matrix from the label sequence
  3. nstep_forecast(P, n)      Chapman-Kolmogorov: P^n is the n-step matrix
  4. stationary_distribution() the long-run regime mix (left eigenvector)
  5. walk_forward_backtest()   no-lookahead, re-estimated-every-step Sharpe + maxDD

Plus fit_hmm(...) for the optional Hidden Markov Model upgrade, and a top-level
analyze(...) that returns one structured dict for agents to consume.

Two ways to feed it data so it drops into any pipeline regardless of asset:
  --ticker SYMBOL   fetch daily history via yfinance (free, no key)
  --csv PATH        your own price series (needs a date column + a close column)

Two output modes:
  (default)         pretty terminal output — the on-camera demo
  --json            the analyze() dict as JSON to stdout, nothing else

Framework: Roan (@RohOnChain). Refactored into a Claude Code plugin by
Lewis Jackson. Backtests are historical, not forward-looking.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# State indices are fixed: 0 = Bear, 1 = Sideways, 2 = Bull.
STATES = ["Bear", "Sideways", "Bull"]

DEFAULT_WINDOW = 20
DEFAULT_THRESHOLD = 0.05  # ±5% rolling return cutoff
DEFAULT_YEARS = 10
DEFAULT_MIN_TRAIN = 252
MATRIX_TOLERANCE = 1e-10
BOUNDARY_TOLERANCE = 1e-12


class UnavailableEstimate(ValueError):
    """Valid inputs do not identify the requested statistical estimate."""


def _integer(value, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return int(value)


def _number(value, name: str, minimum: float = 0, *, positive=False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and numeric.") from exc
    if isinstance(value, (bool, np.bool_)) or not np.isfinite(result) or result < minimum or (positive and result == minimum):
        raise ValueError(f"{name} must be finite and {'>' if positive else '>='} {minimum}.")
    return result


def _prices(close: pd.Series, *, dates=False) -> pd.Series:
    if not isinstance(close, pd.Series) or close.empty:
        raise ValueError("Prices must be a nonempty pandas Series.")
    if dates and not isinstance(close.index, pd.DatetimeIndex):
        raise ValueError("Prices require a DatetimeIndex.")
    if close.index.hasnans or not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError("Price dates must be present, unique, and sorted in increasing order.")
    try:
        values = pd.to_numeric(close, errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Prices must be numeric.") from exc
    if not np.isfinite(values.to_numpy()).all() or (values <= 0).any():
        raise ValueError("Prices must be finite, positive, and have no missing values.")
    return values


def _labels(labels) -> np.ndarray:
    try:
        values = np.asarray(labels, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Labels must be integer states 0, 1, or 2.") from exc
    if values.ndim != 1 or not np.isfinite(values).all() or not np.isin(values, [0, 1, 2]).all():
        raise ValueError("Labels must be integer states 0, 1, or 2.")
    return values.astype(int)


def _matrix(matrix) -> np.ndarray:
    p = np.asarray(matrix, dtype=float)
    if p.shape != (3, 3):
        raise ValueError("Transition matrix must have shape (3, 3).")
    missing = np.isnan(p).all(axis=1)
    observed = p[~missing]
    if not np.isfinite(observed).all() or (observed < 0).any() or not np.allclose(observed.sum(axis=1), 1, rtol=0, atol=MATRIX_TOLERANCE):
        raise ValueError("Transition rows must be normalized probabilities or entirely missing.")
    return p


def _normalize_counts(counts: np.ndarray) -> np.ndarray:
    totals = counts.sum(axis=1, keepdims=True)
    return np.divide(counts, totals, out=np.full((3, 3), np.nan), where=totals != 0)


# --------------------------------------------------------------------------- #
# Data loading — asset-agnostic. Either a ticker or a user's own CSV.
# --------------------------------------------------------------------------- #
def fetch_ticker(ticker: str, years: int = DEFAULT_YEARS) -> pd.Series:
    """Fetch a daily close series via yfinance, with one retry on empty data."""
    years = _integer(years, "years", 1)
    if not isinstance(ticker, str) or not ticker.strip() or any(c.isspace() or c == "," for c in ticker):
        raise ValueError("Provide exactly one nonempty ticker symbol.")
    import yfinance as yf

    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    start = end - pd.DateOffset(years=years)

    df = pd.DataFrame()
    for attempt in (1, 2):
        try:
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ! yfinance error on attempt {attempt}: {exc}", file=sys.stderr)
            df = pd.DataFrame()

        if not df.empty:
            break
        if attempt == 1:
            print(
                "  ! yfinance returned empty data — retrying in 30s.", file=sys.stderr
            )
            time.sleep(30)

    if df.empty:
        raise RuntimeError(
            f"yfinance returned empty data for {ticker} after retry. "
            "Yahoo may be rate-limiting. Try again in a few minutes."
        )

    # Some yfinance versions return a MultiIndex column frame.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        raise ValueError("Ticker returned multiple close series; provide one symbol.")
    close.name = ticker
    return _prices(close, dates=True)


def load_csv(path: str) -> pd.Series:
    """Load a user's own price series from CSV.

    Requirements are deliberately loose so this drops into any pipeline:
      - one column that parses as dates (first match of: date, time,
        timestamp, datetime, or the first column)
      - one close column (first match of: close, adj close, adj_close,
        price, last, or — if only one numeric column exists — that column)
    """
    df = pd.read_csv(path)
    if df.empty:
        raise RuntimeError(f"{path} is empty.")

    cols = {c.lower().strip(): c for c in df.columns}

    date_col = None
    for key in ("date", "time", "timestamp", "datetime"):
        if key in cols:
            date_col = cols[key]
            break
    if date_col is None:
        date_col = df.columns[0]

    close_col = None
    for key in ("close", "adj close", "adj_close", "adjclose", "price", "last"):
        if key in cols:
            close_col = cols[key]
            break
    if close_col is None:
        numeric = df.select_dtypes("number").columns.tolist()
        numeric = [c for c in numeric if c != date_col]
        if len(numeric) == 1:
            close_col = numeric[0]
        else:
            raise RuntimeError(
                f"Could not find a close column in {path}. "
                f"Add a column named one of: close, adj close, price, last. "
                f"Saw columns: {list(df.columns)}"
            )

    out = df[[date_col, close_col]].copy()
    if pd.api.types.is_numeric_dtype(out[date_col]):
        raise ValueError("Numeric dates are ambiguous; supply ISO date or datetime strings.")
    try:
        out[date_col] = pd.to_datetime(out[date_col], utc=True, errors="raise")
        out[close_col] = pd.to_numeric(out[close_col], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid date or price in {path}: {exc}") from exc
    out = out.sort_values(date_col)
    close = pd.Series(
        out[close_col].to_numpy(),
        index=pd.DatetimeIndex(out[date_col]),
        name=Path(path).stem,
    )
    return _prices(close, dates=True)


# --------------------------------------------------------------------------- #
# Core model — pure functions.
# --------------------------------------------------------------------------- #
def label_regimes(
    close: pd.Series,
    window: int = DEFAULT_WINDOW,
    threshold: float = DEFAULT_THRESHOLD,
) -> pd.Series:
    """Label each day from the trailing `window`-day return.

    Bull (2)     : rolling return >  +threshold
    Bear (0)     : rolling return <  -threshold
    Sideways (1) : otherwise
    """
    close = _prices(close)
    window = _integer(window, "window", 1)
    threshold = _number(threshold, "threshold")
    rolling_return = close.pct_change(window, fill_method=None)
    if not np.isfinite(rolling_return.iloc[window:].to_numpy()).all():
        raise ValueError("Rolling returns must be finite; price ratios overflowed.")
    labels = pd.Series(1, index=close.index, dtype=int)  # default Sideways
    labels[(rolling_return - threshold) > BOUNDARY_TOLERANCE] = 2  # Bull
    labels[(rolling_return + threshold) < -BOUNDARY_TOLERANCE] = 0  # Bear
    return labels.loc[rolling_return.notna()]


def _transition_counts(labels) -> np.ndarray:
    counts = np.zeros((3, 3), dtype=int)
    arr = _labels(labels)
    for i in range(len(arr) - 1):
        counts[arr[i], arr[i + 1]] += 1
    return counts


def build_transition_matrix(labels: pd.Series) -> np.ndarray:
    """MLE 3x3 transition matrix; unobserved outgoing rows are entirely NaN."""
    return _normalize_counts(_transition_counts(labels))


def nstep_forecast(matrix: np.ndarray, n: int) -> np.ndarray:
    """P^n, with unavailable rows tracked by positive-probability reachability."""
    p = _matrix(matrix)
    n = _integer(n, "horizon", 0)
    supported = ~np.isnan(p).all(axis=1)
    numeric = np.nan_to_num(p, nan=0.)
    edges = numeric > 0
    available = np.ones(3, dtype=bool)
    for _ in range(n):
        available = supported & ~np.any(edges & ~available[None, :], axis=1)
    forecast = np.linalg.matrix_power(numeric, n)
    forecast[~available] = np.nan
    return forecast


def stationary_distribution(matrix: np.ndarray) -> np.ndarray:
    """Unique stationary vector, without promising convergence for every chain.

    Missing transition evidence or nonuniqueness raises UnavailableEstimate.
    """
    p = _matrix(matrix)
    if np.isnan(p).any():
        raise UnavailableEstimate("Insufficient transition evidence for a stationary distribution.")
    # Uniqueness is structural: exactly one closed communicating class.
    # Numerical rank tolerances would misclassify slowly mixing chains.
    reachable = (p > 0) | np.eye(3, dtype=bool)
    for k in range(3):
        reachable |= reachable[:, k, None] & reachable[None, k, :]
    remaining = set(range(3))
    closed_classes = 0
    while remaining:
        origin = min(remaining)
        component = np.flatnonzero(reachable[origin] & reachable[:, origin])
        remaining.difference_update(component)
        outside = np.setdiff1d(np.arange(3), component)
        if not np.any(p[np.ix_(component, outside)] > 0):
            closed_classes += 1
    if closed_classes != 1:
        raise UnavailableEstimate("Stationary distribution is not unique.")
    # Construct P-I's diagonal from outgoing mass to avoid cancellation when
    # persistence is near one, then scale the balance equations before solving.
    off_diagonal = p.copy()
    np.fill_diagonal(off_diagonal, 0.)
    balance = off_diagonal.T.copy()
    np.fill_diagonal(balance, -off_diagonal.sum(axis=1))
    scale = np.max(np.abs(balance))
    system = np.vstack([balance / scale, np.ones(3)])
    vec, *_ = np.linalg.lstsq(system, [0., 0., 0., 1.], rcond=None)
    if (vec < -MATRIX_TOLERANCE).any():
        raise ValueError("Stationary solution contains negative probabilities.")
    vec = np.maximum(vec, 0)
    vec /= vec.sum()
    if not np.allclose(vec @ p, vec, rtol=0, atol=MATRIX_TOLERANCE):
        raise ValueError("Stationary solution failed its residual check.")
    return vec


def signal_from_matrix(matrix: np.ndarray, current_state: int) -> float:
    """The signal: P(next=Bull | current) - P(next=Bear | current).

    Positive -> long bias, negative -> short bias. This is not calibrated confidence.
    """
    p = _matrix(matrix)
    state = _integer(current_state, "current_state", 0)
    if state > 2:
        raise ValueError("current_state must be 0, 1, or 2.")
    return float(p[state, 2] - p[state, 0])


def walk_forward_signals(close: pd.Series, labels: pd.Series,
                         min_train: int = DEFAULT_MIN_TRAIN) -> pd.DataFrame:
    """Forecast at t from labels strictly before t; NaN represents no evidence.

    The result includes warmup dates, with eligible=False until min_train.
    Labels must be a contiguous suffix of the price index.
    """
    close = _prices(close, dates=True)
    min_train = _integer(min_train, "min_train", 2)
    lab = _labels(labels)
    if not isinstance(labels, pd.Series) or not labels.index.equals(close.index[len(close) - len(labels):]):
        raise ValueError("Labels must align with a contiguous suffix of the price dates.")
    values = np.full((len(lab), 4), np.nan)
    counts = np.zeros((3, 3), dtype=float)
    for t in range(len(lab)):
        # Before scoring t, only transitions ending at t-1 have been added.
        if t >= min_train:
            row = _normalize_counts(counts)[lab[t]]
            values[t, :3] = row
            values[t, 3] = row[2] - row[0]
        if t > 0:
            counts[lab[t - 1], lab[t]] += 1
    result = pd.DataFrame(values, index=labels.index, columns=["bear", "sideways", "bull", "signal"])
    result["eligible"] = np.arange(len(lab)) >= min_train
    return result


def execution_ledger(close: pd.Series, targets: pd.Series, *, cost_bps: float = 0,
                     start=None, end=None) -> pd.DataFrame:
    """Decision at t, fill at close t+1, earn the return ending at t+2.

    Evaluation begins flat immediately before its first close and ends flat.
    A prior-date decision may fill at the first evaluation close. Missing
    targets mean flat, not carry-forward. Costs apply to absolute turnover;
    a reversal is two units and final liquidation is charged.
    """
    close = _prices(close, dates=True)
    cost_bps = _number(cost_bps, "cost_bps")
    if not isinstance(targets, pd.Series) or not targets.index.is_unique or not targets.index.is_monotonic_increasing:
        raise ValueError("Targets must be a Series with unique sorted dates.")
    if not targets.index.isin(close.index).all():
        raise ValueError("Target dates must be present in prices.")
    try:
        targets = pd.to_numeric(targets, errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Targets must be numeric or missing.") from exc
    known = targets.dropna().to_numpy()
    if not np.isfinite(known).all() or (np.abs(known) > 1).any():
        raise ValueError("Targets must be finite and between -1 and 1, or missing.")
    decisions = targets.reindex(close.index).fillna(0.)
    index = close.loc[start:end].index
    ledger = pd.DataFrame(index=index)
    ledger["target"] = decisions.loc[index]
    position = decisions.shift(1, fill_value=0.).loc[index].copy()
    if len(position):
        position.iloc[-1] = 0.  # Liquidate instead of opening a terminal position.
    ledger["position"] = position
    previous = position.shift(1, fill_value=0.)
    ledger["gross_return"] = previous * close.pct_change(fill_method=None).fillna(0.).loc[index]
    ledger["turnover"] = (position - previous).abs()
    ledger["cost"] = ledger["turnover"] * cost_bps / 10_000
    ledger["net_return"] = ledger["gross_return"] - ledger["cost"]
    if (ledger["net_return"] <= -1).any():
        raise ValueError("Strategy equity is exhausted; this unlevered return ledger cannot continue.")
    ledger["equity"] = (1 + ledger["net_return"]).cumprod()
    if not np.isfinite(ledger.to_numpy()).all():
        raise ValueError("Execution produced nonfinite values.")
    return ledger


def summarize_ledger(ledger: pd.DataFrame, periods_per_year: float = 252) -> dict:
    """Net metrics including cash periods, entry/reversal count, and initial capital.

    n_periods includes the initial close (gross return zero). CAGR uses the
    elapsed calendar time (365.2425 days/year). Sharpe uses a
    zero risk-free rate. Statistical metrics require at least two periods;
    zero variance makes Sharpe unavailable. Drawdown is defined from one row.
    """
    periods_per_year = _number(periods_per_year, "periods_per_year", positive=True)
    keys = ["total_return", "cagr", "volatility", "sharpe", "max_drawdown", "exposure", "turnover"]
    result = {key: None for key in keys}
    result.update(n_trades=0, n_periods=len(ledger), unavailable={})
    if ledger.empty:
        result["unavailable"] = {key: "no_evaluation_periods" for key in keys}
        return result
    required = ["position", "net_return", "equity", "turnover"]
    if not np.isfinite(ledger[required].to_numpy()).all() or (ledger.equity <= 0).any():
        raise ValueError("Ledger must contain finite values and positive equity.")
    returns = ledger.net_return.to_numpy(float)
    equity = np.r_[1., ledger.equity.to_numpy(float)]
    previous = ledger.position.shift(1, fill_value=0.)
    entries = (ledger.position != 0) & ((previous == 0) | (np.sign(previous) != np.sign(ledger.position)))
    result.update(total_return=float(equity[-1] - 1),
                  max_drawdown=float((equity / np.maximum.accumulate(equity) - 1).min()),
                  exposure=float(ledger.position.abs().mean()),
                  turnover=float(ledger.turnover.sum()), n_trades=int(entries.sum()))
    if not isinstance(ledger.index, pd.DatetimeIndex) or not ledger.index.is_monotonic_increasing or not ledger.index.is_unique:
        raise ValueError("Ledger requires unique sorted datetime observations.")
    elapsed_days = (ledger.index[-1] - ledger.index[0]).total_seconds() / 86_400
    if elapsed_days <= 0:
        result["unavailable"]["cagr"] = "zero_elapsed_time"
    else:
        with np.errstate(over="ignore", invalid="ignore"):
            cagr = np.expm1(np.log(equity[-1]) * 365.2425 / elapsed_days)
        if np.isfinite(cagr):
            result["cagr"] = float(cagr)
        else:
            result["unavailable"]["cagr"] = "annualization_overflow"
    if len(returns) < 2:
        result["unavailable"].update(volatility="fewer_than_two_periods", sharpe="fewer_than_two_periods")
    else:
        std = float(returns.std(ddof=1))
        result["volatility"] = float(std * np.sqrt(periods_per_year))
        if std == 0:
            result["unavailable"]["sharpe"] = "zero_return_variance"
        else:
            result["sharpe"] = float(returns.mean() / std * np.sqrt(periods_per_year))
    return result


def walk_forward_backtest(close: pd.Series, labels: pd.Series,
                          min_train: int = DEFAULT_MIN_TRAIN, *,
                          periods_per_year: float = 252, cost_bps: float = 0) -> dict:
    """Sign-based strategy using causal next-close execution and explicit costs."""
    signals = walk_forward_signals(close, labels, min_train)
    eligible = signals.loc[signals.eligible]
    targets = np.sign(signals.signal)
    # Begin at the close after the first eligible decision.
    if len(eligible) > 1:
        ledger = execution_ledger(close, targets, cost_bps=cost_bps, start=eligible.index[1])
    else:
        _number(cost_bps, "cost_bps")
        ledger = pd.DataFrame()
    result = summarize_ledger(ledger, periods_per_year)
    result["unavailable_forecast_bars"] = int(eligible.signal.isna().sum())
    result["position_rule"] = "sign_signal"
    result["execution"] = "decision_t_fill_t_plus_1_return_t_plus_2"
    result["cost_bps"] = float(cost_bps)
    result["periods_per_year"] = float(periods_per_year)
    return result


def fit_hmm(returns: pd.Series, n_components: int = 3, random_state: int = 42):
    """Fit a Gaussian HMM on daily returns. Returns (model, hidden_states).

    Lazy import so the observable model still works if hmmlearn failed to
    compile (common on Windows without MSVC build tools). Returns (None, None)
    if hmmlearn is unavailable.

    Baum-Welch finds local maxima — for production work, fit several
    random_state values and keep the best by log-likelihood.
    """
    try:
        from hmmlearn import hmm  # noqa: PLC0415  (intentional lazy import)
    except Exception:  # noqa: BLE001  (ImportError or compiled-ext failure)
        return None, None

    X = returns.dropna().to_numpy(dtype=float).reshape(-1, 1)
    model = hmm.GaussianHMM(
        n_components=n_components,
        covariance_type="diag",
        n_iter=200,
        random_state=random_state,
    )
    model.fit(X)
    hidden_states = model.predict(X)
    return model, hidden_states


def _hmm_summary(close: pd.Series, enabled: bool) -> dict:
    """Build the HMM section of the analyze() dict, degrading gracefully."""
    if not enabled:
        return {"available": False, "reason": "disabled via --no-hmm"}
    try:
        model, _ = fit_hmm(close.pct_change().dropna(), n_components=3)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"hmm runtime error: {exc}"}
    if model is None:
        return {
            "available": False,
            "reason": "hmmlearn not installed or failed to compile",
        }

    means = np.array([model.means_[k][0] for k in range(model.n_components)])
    if not np.isfinite(means).all():
        return {"available": False, "reason": "HMM produced nonfinite estimated means"}
    order = np.argsort(means)  # ascending mean return
    rank_names = ["Bear", "Sideways", "Bull"]
    regimes = []
    for rank, k in enumerate(order):
        regimes.append(
            {
                "label": rank_names[rank],
                "latent_state": int(k),
                "mean_daily_return": float(means[k]),
            }
        )
    return {
        "available": True,
        "regimes": regimes,
        "caveat": (
            "HMM states are labelled by ascending mean return, so a positive "
            "'Bear' mean just means the worst latent state was still net-"
            "positive over this window. Baum-Welch finds local maxima; for "
            "production fit several random_state values."
        ),
    }


# --------------------------------------------------------------------------- #
# Top-level analyze() — the single structured dict agents consume.
# --------------------------------------------------------------------------- #
def analyze(
    close: pd.Series,
    *,
    source: str,
    window: int = DEFAULT_WINDOW,
    threshold: float = DEFAULT_THRESHOLD,
    min_train: int = DEFAULT_MIN_TRAIN,
    hmm: bool = True,
    horizon: int = 1,
    periods_per_year: float = 252,
    cost_bps: float = 0,
) -> dict:
    """Run the whole framework and return one structured dict.

    See SKILL.md for the full field-by-field JSON contract.
    """
    close = _prices(close, dates=True)
    min_train = _integer(min_train, "min_train", 2)
    horizon = _integer(horizon, "horizon", 0)
    periods_per_year = _number(periods_per_year, "periods_per_year", positive=True)
    cost_bps = _number(cost_bps, "cost_bps")
    labels = label_regimes(close, window=window, threshold=threshold)
    if len(labels) < 1:
        raise RuntimeError(
            "Not enough data to label regimes — need more rows than the "
            f"rolling window ({window}). Got {len(close)} price rows."
        )

    P = build_transition_matrix(labels)
    unavailable = {}
    try:
        pi = stationary_distribution(P)
    except UnavailableEstimate as exc:
        pi = np.full(3, np.nan)
        unavailable["stationary_distribution"] = str(exc)

    current_state = int(labels.iloc[-1])
    next_probs = P[current_state]  # P(next | current) over [Bear, Side, Bull]
    bull_p = float(next_probs[2])
    bear_p = float(next_probs[0])
    side_p = float(next_probs[1])
    forecast = nstep_forecast(P, horizon)[current_state]
    if np.isnan(next_probs).all():
        unavailable["next_state_probabilities"] = "unobserved_current_state_transitions"
        unavailable["signal"] = "unobserved_current_state_transitions"
    if np.isnan(forecast).all():
        unavailable["forecast"] = "forecast_reaches_unobserved_transition_rows"

    bt = walk_forward_backtest(close, labels, min_train=min_train,
                               periods_per_year=periods_per_year, cost_bps=cost_bps)

    return _json_safe({
        "schema_version": 2,
        "source": source,
        "rows": int(len(close)),
        "date_start": str(close.index.min().date()),
        "date_end": str(close.index.max().date()),
        "params": {
            "window": window,
            "threshold": threshold,
            "min_train": min_train,
            "horizon": horizon,
            "periods_per_year": periods_per_year,
            "cost_bps": cost_bps,
        },
        "states": STATES,
        "current_regime": STATES[current_state],
        "next_state_probabilities": {
            "bear": bear_p,
            "sideways": side_p,
            "bull": bull_p,
        },
        "signal": bull_p - bear_p,
        "forecast": {"horizon": horizon, "probabilities": dict(zip(["bear", "sideways", "bull"], forecast))},
        "transition_matrix": [[float(x) for x in row] for row in P],
        "transition_counts": _transition_counts(labels).tolist(),
        "persistence_diagonal": {
            "bear": float(P[0, 0]),
            "sideways": float(P[1, 1]),
            "bull": float(P[2, 2]),
        },
        "stationary_distribution": {
            "bear": float(pi[0]),
            "sideways": float(pi[1]),
            "bull": float(pi[2]),
        },
        "walk_forward": bt,
        "unavailable": unavailable,
        "hmm": _hmm_summary(close, hmm),
        "framework": "Roan (@RohOnChain)",
        "disclaimer": "Backtests are historical, not forward-looking.",
    })


def _json_safe(value):
    """Convert numerical missing estimates to strict JSON null values."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


# --------------------------------------------------------------------------- #
# Pretty terminal output — the on-camera demo. Keep it.
# --------------------------------------------------------------------------- #
def _print_pretty(a: dict) -> None:
    def fmt(value, *, percent=False):
        if value is None:
            return "unavailable"
        return f"{value * 100:.2f}%" if percent else f"{value:.4f}"

    P = np.array(a["transition_matrix"])
    print(
        f"\nmarkov-regime — source={a['source']} "
        f"window={a['params']['window']} threshold={a['params']['threshold']}"
    )
    print(f"  {a['rows']} rows | {a['date_start']} -> {a['date_end']}")

    print("\nTransition matrix (rows = from, cols = to):")
    print(f"            {'Bear':>9s} {'Sideways':>9s} {'Bull':>9s}")
    for i, from_state in enumerate(STATES):
        row = "  ".join(fmt(P[i, j], percent=True) for j in range(3))
        print(f"  {from_state:>9s}  {row}")

    pd_diag = a["persistence_diagonal"]
    print("\nPersistence diagonal (how sticky each regime is):")
    for state in STATES:
        print(f"  {state} -> {state}: {fmt(pd_diag[state.lower()], percent=True)}")

    sd = a["stationary_distribution"]
    print("\nStationary distribution (long-run regime mix):")
    for state in STATES:
        print(f"  {state}: {fmt(sd[state.lower()], percent=True)}")

    np_ = a["next_state_probabilities"]
    print(f"\nCurrent regime: {a['current_regime']}")
    print("Next-bar probabilities from here:")
    for state in STATES:
        print(f"  {state}: {fmt(np_[state.lower()], percent=True)}")
    print(f"Signal (bull_prob - bear_prob): {fmt(a['signal'])}")
    print(f"{a['forecast']['horizon']}-bar forecast: " + ", ".join(
        f"{key}={fmt(value, percent=True)}" for key, value in a["forecast"]["probabilities"].items()))

    wf = a["walk_forward"]
    print("\nWalk-forward backtest (matrix re-estimated every step, no lookahead):")
    print(f"  Sharpe (annualised): {fmt(wf['sharpe'])}")
    print(f"  Max drawdown: {fmt(wf['max_drawdown'], percent=True)}")
    print(f"  Entries including reversals: {wf['n_trades']}; evaluation periods: {wf['n_periods']}")
    print(f"  Unavailable forecast bars: {wf['unavailable_forecast_bars']}")
    print(f"  Costs: {wf['cost_bps']:g} bps per unit turnover; decision t -> fill t+1 -> return t+2")
    for key, reason in a["unavailable"].items():
        print(f"  {key} unavailable: {reason}")

    hmm = a["hmm"]
    if hmm.get("available"):
        print("\nHidden Markov Model (Baum-Welch + Viterbi):")
        for r in hmm["regimes"]:
            print(
                f"  {r['label']:<9s} (latent state {r['latent_state']}): "
                f"{r['mean_daily_return'] * 100:+.3f}% mean daily return"
            )
        print(f"  Note: {hmm['caveat']}")
    else:
        print(
            f"\nHMM skipped: {hmm.get('reason', 'unavailable')} "
            "(observable model above is unaffected)."
        )

    print("\n----------------------------------------------------------------")
    print(" Framework: Roan (@RohOnChain). Refactored into a Claude Code")
    print(" plugin by Lewis Jackson. Backtests are historical, not forward-")
    print(" looking. Point the matrix at whatever you trade.")
    print("----------------------------------------------------------------\n")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in argv
    parser = _ArgumentParser(
        prog="markov_regime",
        description="Markov regime detection for any asset (Roan / @RohOnChain).",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--ticker", help="Symbol to fetch via yfinance, e.g. BTC-USD")
    src.add_argument("--csv", help="Path to your own CSV (date column + close column)")
    parser.add_argument(
        "--years",
        type=int,
        default=DEFAULT_YEARS,
        help=f"Years of history when using --ticker (default {DEFAULT_YEARS})",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW,
        help=f"Rolling-return window in bars (default {DEFAULT_WINDOW})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Regime label threshold on rolling return (default {DEFAULT_THRESHOLD} = ±5%%)",
    )
    parser.add_argument(
        "--min-train",
        type=int,
        default=DEFAULT_MIN_TRAIN,
        help=f"Min training rows before the walk-forward starts (default {DEFAULT_MIN_TRAIN})",
    )
    parser.add_argument(
        "--no-hmm",
        action="store_true",
        help="Skip the HMM fit even if hmmlearn is available",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the analyze() dict as JSON to stdout and nothing else",
    )
    parser.add_argument("--horizon", type=int, default=1, help="Forecast horizon in bars (default 1)")
    parser.add_argument("--periods-per-year", type=float, default=252,
                        help="Annualization assumption; use 365 for daily crypto (default 252)")
    parser.add_argument("--cost-bps", type=float, default=0,
                        help="One-way cost per unit turnover in basis points (default 0)")

    try:
        args = parser.parse_args(argv)
        _integer(args.years, "years", 1)
        _integer(args.window, "window", 1)
        _integer(args.min_train, "min_train", 2)
        _integer(args.horizon, "horizon", 0)
        _number(args.threshold, "threshold")
        _number(args.periods_per_year, "periods_per_year", positive=True)
        _number(args.cost_bps, "cost_bps")
        if args.ticker:
            if not args.json:
                print(
                    f"  fetching {args.ticker} from Yahoo Finance...", file=sys.stderr
                )
            close = fetch_ticker(args.ticker, years=args.years)
            source = args.ticker
        else:
            close = load_csv(args.csv)
            source = args.csv

        result = analyze(
            close,
            source=source,
            window=args.window,
            threshold=args.threshold,
            min_train=args.min_train,
            hmm=not args.no_hmm,
            horizon=args.horizon,
            periods_per_year=args.periods_per_year,
            cost_bps=args.cost_bps,
        )
    except Exception as exc:  # noqa: BLE001
        if json_mode:
            print(json.dumps({"error": str(exc)}, allow_nan=False))
        else:
            print(f"\nERROR: {exc}\n", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, allow_nan=False))
    else:
        _print_pretty(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
