"""Frozen SPY/BTC research protocol. Only the explicit `fetch` command uses the network."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

if __package__:
    from . import markov_regime as core
else:
    import markov_regime as core


START = "2015-01-01"
END = "2025-12-31"
HOLDOUT_START = "2020-01-01"
ASSETS = {"SPY": 252, "BTC-USD": 365}
COSTS_BPS = (0, 5, 10, 25)
ROOT = Path(__file__).resolve().parents[1]


def _versions() -> dict:
    result = {"python": platform.python_version()}
    for package in ("numpy", "pandas", "yfinance"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = None
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_prices(close: pd.Series, asset: str) -> pd.Series:
    if not isinstance(close.index, pd.DatetimeIndex) or close.empty:
        raise ValueError(f"{asset}: nonempty daily DatetimeIndex required")
    if close.index.tz is not None or close.index.hasnans:
        raise ValueError(f"{asset}: valid timezone-naive dates required")
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError(f"{asset}: dates must be unique and sorted")
    if not close.index.equals(close.index.normalize()):
        raise ValueError(f"{asset}: daily dates must have midnight timestamps")
    values = np.asarray(close, dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(f"{asset}: prices must be finite and positive")
    if close.index.min() < pd.Timestamp(START) or close.index.max() > pd.Timestamp(END):
        raise ValueError(f"{asset}: prices outside the fixed {START}..{END} protocol")
    if close.index.min() > pd.Timestamp(START) + pd.Timedelta(days=7):
        raise ValueError(f"{asset}: snapshot does not cover the start of the protocol")
    if close.index.max() < pd.Timestamp(END) - pd.Timedelta(days=7):
        raise ValueError(f"{asset}: snapshot does not cover the end of the protocol")
    return pd.Series(values, index=close.index, name="close")


def _empty_destination(directory: Path) -> None:
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise FileExistsError(f"Refusing to overwrite snapshot at {directory}; choose a new directory")


def freeze_snapshot(
    directory: Path | str,
    prices: dict[str, pd.Series],
    *,
    acquired_at: str,
    versions: dict | None = None,
) -> dict:
    """Persist an immutable normalized acquisition, after validating all assets."""
    directory = Path(directory)
    _empty_destination(directory)
    if set(prices) != set(ASSETS):
        raise ValueError("The fixed protocol requires exactly SPY and BTC-USD")
    validated = {asset: _validate_prices(prices[asset], asset) for asset in ASSETS}
    manifest = {
        "snapshot_schema_version": "1.0",
        "source": "Yahoo Finance daily history via yfinance",
        "acquired_at_utc": acquired_at,
        "requested_start": START,
        "requested_end_inclusive": END,
        "download_end_exclusive": "2026-01-01",
        "dependency_versions": versions if versions is not None else _versions(),
        "calendar_policy": "Preserve observed dates; no resampling or forward fill",
        "assets": {},
    }
    directory.mkdir(parents=True, exist_ok=True)
    for asset, close in validated.items():
        path = directory / f"{asset}.csv"
        close.rename_axis("date").to_csv(path, date_format="%Y-%m-%d", float_format="%.17g", lineterminator="\n")
        gaps = close.index.to_series().diff().dt.days
        unusual = gaps[gaps > (4 if asset == "SPY" else 1)]
        manifest["assets"][asset] = {
            "ticker": asset,
            "source_url": f"https://finance.yahoo.com/quote/{asset}/history/",
            "file": path.name,
            "sha256": _sha256(path),
            "rows": len(close),
            "date_start": str(close.index.min().date()),
            "date_end": str(close.index.max().date()),
            "adjustment": "dividend_and_split_adjusted" if asset == "SPY" else "unadjusted_close",
            "yfinance_auto_adjust": asset == "SPY",
            "periods_per_year": ASSETS[asset],
            "unusually_long_gaps": [
                {"ending_date": str(date.date()), "calendar_days": int(days)}
                for date, days in unusual.items()
            ],
        }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def fetch_snapshot(directory: Path | str) -> dict:
    """Explicit acquisition only; never silently refresh an existing snapshot."""
    directory = Path(directory)
    _empty_destination(directory)
    import yfinance as yf

    prices = {}
    for asset in ASSETS:
        frame = yf.download(
            asset, start=START, end="2026-01-01", interval="1d",
            auto_adjust=asset == "SPY", actions=False, progress=False, threads=False,
        )
        if frame.empty:
            raise RuntimeError(f"Yahoo returned no {asset} data; no snapshot was frozen")
        close = frame["Close"]
        if isinstance(close, pd.DataFrame):
            close = close[asset]
        # Yahoo daily indexes may carry the exchange timezone; preserve its date.
        if close.index.tz is not None:
            close.index = close.index.tz_localize(None)
        prices[asset] = close
    return freeze_snapshot(directory, prices, acquired_at=datetime.now(timezone.utc).isoformat())


def load_snapshot(directory: Path | str) -> tuple[dict[str, pd.Series], dict]:
    """Read and verify all frozen inputs. This function never fetches missing data."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("snapshot_schema_version") != "1.0":
        raise ValueError("Unsupported snapshot schema")
    if manifest.get("requested_start") != START or manifest.get("requested_end_inclusive") != END:
        raise ValueError("Snapshot dates do not match the fixed research protocol")
    if set(manifest.get("assets", {})) != set(ASSETS):
        raise ValueError("Snapshot must contain exactly SPY and BTC-USD")
    prices = {}
    for asset in ASSETS:
        metadata = manifest["assets"][asset]
        if metadata["file"] != f"{asset}.csv":
            raise ValueError(f"Unexpected snapshot filename for {asset}")
        path = directory / metadata["file"]
        if _sha256(path) != metadata["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {asset}; frozen prices have changed")
        frame = pd.read_csv(path, float_precision="round_trip")
        if frame.columns.tolist() != ["date", "close"]:
            raise ValueError(f"{asset}: expected date,close CSV columns")
        close = pd.Series(frame["close"].to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(frame["date"])))
        close = _validate_prices(close, asset)
        if (len(close) != metadata["rows"] or str(close.index.min().date()) != metadata["date_start"]
                or str(close.index.max().date()) != metadata["date_end"]):
            raise ValueError(f"{asset}: manifest coverage does not match CSV")
        expected_adjustment = "dividend_and_split_adjusted" if asset == "SPY" else "unadjusted_close"
        if metadata.get("adjustment") != expected_adjustment or metadata.get("periods_per_year") != ASSETS[asset]:
            raise ValueError(f"{asset}: manifest price policy does not match the protocol")
        prices[asset] = close
    return prices, manifest


def strategy_targets(close: pd.Series, signals: pd.DataFrame) -> dict[str, pd.Series]:
    """Three predeclared long/cash policies; unavailable forecasts gate to cash."""
    momentum = (close / close.shift(20) - 1 > 0).astype(float)
    available = signals["eligible"].reindex(close.index, fill_value=False).fillna(False).astype(bool)
    agreed = signals["signal"].reindex(close.index).gt(0) & available
    return {
        "buy_and_hold": pd.Series(1.0, index=close.index),
        "momentum": momentum,
        "filtered_momentum": momentum * agreed.astype(float),
    }


def forecast_scores(labels: pd.Series, signals: pd.DataFrame, *, start: str, end: str) -> dict:
    """Summed multiclass Brier score, using identical forecast dates for all models."""
    labels = labels.astype(int)
    following = labels.shift(-1)
    next_dates = pd.Series(labels.index, index=labels.index).shift(-1)
    mask = (labels.index >= pd.Timestamp(start)) & next_dates.le(pd.Timestamp(end)) & following.notna()
    dates = labels.index[mask]
    evidence = signals.reindex(dates)
    probabilities = evidence[["bear", "sideways", "bull"]].to_numpy(dtype=float)
    eligible = evidence["eligible"].fillna(False).to_numpy(dtype=bool)
    available = eligible & np.isfinite(probabilities).all(axis=1)
    scores = {"markov": [], "persistence": [], "historical_frequency": []}
    # Historical frequencies end before t, matching the Markov training cutoff.
    historical_counts = np.eye(3)[labels.to_numpy()].cumsum(axis=0)
    for offset in np.flatnonzero(available):
        date = dates[offset]
        pos = labels.index.get_loc(date)
        truth = np.eye(3)[int(following.loc[date])]
        persistence = np.eye(3)[int(labels.loc[date])]
        frequency = historical_counts[pos - 1] / pos
        for name, prediction in (("markov", probabilities[offset]), ("persistence", persistence),
                                 ("historical_frequency", frequency)):
            scores[name].append(float(np.square(prediction - truth).sum()))
    by_state = {}
    current = labels.reindex(dates).to_numpy()
    for state, name in enumerate(core.STATES):
        selected = current == state
        count = int(selected.sum())
        covered = int((selected & available).sum())
        by_state[name] = {"opportunities": count, "available": covered,
                          "coverage": covered / count if count else None}
    count = len(dates)
    covered = int(available.sum())
    return {
        "opportunities": count,
        "eligible": int(eligible.sum()),
        "available": covered,
        "unavailable": count - covered,
        "coverage": covered / count if count else None,
        "by_current_state": by_state,
        "brier_definition": "Mean sum of squared class errors (range 0..2; lower is better)",
        "brier": {name: float(np.mean(values)) if values else None for name, values in scores.items()},
        "unavailable_reason": None if covered else "No matched eligible forecasts with observed next states",
        "first_scored_decision": str(dates[available][0].date()) if covered else None,
        "last_scored_decision": str(dates[available][-1].date()) if covered else None,
    }


def evaluate_snapshot(directory: Path | str) -> dict:
    """Evaluate the frozen protocol without acquiring data or tuning parameters."""
    prices, manifest = load_snapshot(directory)
    result = {
        "schema_version": 2,
        "protocol": {
            "development": {"start": START, "end": "2019-12-31"},
            "holdout": {"start": HOLDOUT_START, "end": END},
            "window": 20, "threshold": 0.05, "min_train": 252,
            "training_cutoff": "At t, transitions strictly inside labels[:t]; no future data",
            "execution": "Decide at close t, fill at close t+1, earn t+1 to t+2; start flat, end liquidated",
            "cash_return": 0, "cost_bps": list(COSTS_BPS), "main_cost_bps": 10,
            "cost_model": "cost_bps / 10000 * absolute exposure change, including entry and liquidation",
            "evaluation_kind": "Retrospective walk-forward; parameters fixed before evaluation",
        },
        "snapshot": manifest,
        "manifest_sha256": _sha256(Path(directory) / "manifest.json"),
        "evaluation_dependencies": _versions(),
        "assets": {},
    }
    for asset, close in prices.items():
        labels = core.label_regimes(close, window=20, threshold=0.05)
        signals = core.walk_forward_signals(close, labels, min_train=252)
        targets = strategy_targets(close, signals)
        strategies = {}
        for policy, target in targets.items():
            strategies[policy] = {}
            for cost in COSTS_BPS:
                ledger = core.execution_ledger(close, target, cost_bps=cost, start=HOLDOUT_START, end=END)
                strategies[policy][str(cost)] = core.summarize_ledger(ledger, periods_per_year=ASSETS[asset])
        differences = {}
        for cost in COSTS_BPS:
            baseline = strategies["momentum"][str(cost)]
            filtered = strategies["filtered_momentum"][str(cost)]
            differences[str(cost)] = {
                metric: (filtered[metric] - baseline[metric])
                if filtered.get(metric) is not None and baseline.get(metric) is not None else None
                for metric in ("total_return", "cagr", "max_drawdown", "sharpe")
            }
        evaluation_dates = close.loc[HOLDOUT_START:END].index
        result["assets"][asset] = {
            "periods_per_year": ASSETS[asset],
            "date_start": str(evaluation_dates.min().date()),
            "date_end": str(evaluation_dates.max().date()),
            "observations": len(evaluation_dates),
            "strategies": strategies,
            "filtered_minus_momentum": differences,
            "forecast": forecast_scores(labels, signals, start=HOLDOUT_START, end=END),
        }
    # Enforce the same strict JSON contract before any output is written.
    json.dumps(result, allow_nan=False)
    return result


def _number(value, *, percent: bool = False) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.2%}" if percent else f"{value:.4f}"


def render_report(result: dict) -> str:
    lines = [
        "# Frozen regime research evaluation", "",
        "Retrospective walk-forward evaluation: development 2015-2019; holdout 2020-2025. "
        "Fixed 20-observation simple returns, +/-5% regimes, 252-observation minimum training.", "",
        "Decide at close t, fill at close t+1, earn t+1 to t+2. Start flat; liquidate at the final close. "
        "Cash earns zero. Costs are assumptions per unit of exposure change, including initial and final trades. "
        "SPY uses adjusted closes and 252 observations/year; BTC-USD uses closes and 365 observations/year "
        "for volatility and Sharpe. CAGR uses actual elapsed calendar time with 365.2425 days/year.", "",
        "These policies are long/cash: buy-and-hold; positive 20-observation momentum; "
        "the same momentum gated by an available positive Markov signal. An unavailable signal means cash.", "",
        f"Snapshot acquired: {result['snapshot']['acquired_at_utc']}. "
        f"Manifest SHA-256: `{result['manifest_sha256']}`.", "",
        "Profitability is not a release gate. The requirements are reproducibility, correct chronology, "
        "explicit unavailable evidence, and an honest comparison. Regime probabilities are not probabilities "
        "of a profitable trade. Adjusted historical prices may reflect later source revisions; "
        "this is a frozen retrospective dataset, not point-in-time vendor data.", "",
    ]
    for asset, data in result["assets"].items():
        lines += [f"## {asset}", "", f"{data['date_start']} to {data['date_end']}; {data['observations']} observations.", "",
                  "| Policy | Cost bps | Return | CAGR | Volatility | Sharpe | Max drawdown | Exposure | Turnover | Entries |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for policy, cases in data["strategies"].items():
            for cost, metrics in cases.items():
                values = [_number(metrics.get(k), percent=True) for k in ("total_return", "cagr", "volatility")]
                values += [_number(metrics.get("sharpe")), _number(metrics.get("max_drawdown"), percent=True),
                           _number(metrics.get("exposure"), percent=True), _number(metrics.get("turnover")),
                           str(metrics.get("n_trades", "unavailable"))]
                lines.append(f"| {policy} | {cost} | " + " | ".join(values) + " |")
        delta = data["filtered_minus_momentum"]["10"]
        lines += ["", f"At the main **10 bps** assumption, filtered-minus-momentum return is "
                  f"{_number(delta['total_return'], percent=True)} and max-drawdown difference is "
                  f"{_number(delta['max_drawdown'], percent=True)} (positive means a shallower drawdown).", ""]
        if delta["total_return"] is not None and delta["total_return"] <= 0:
            lines.append("The regime filter did not improve total return over the momentum baseline in this evaluation.")
        else:
            lines.append("Any improvement here is retrospective evidence only; this comparison does not establish future performance.")
        forecast = data["forecast"]
        lines += ["", f"Forecast coverage: {forecast['available']}/{forecast['opportunities']} "
                  f"({_number(forecast['coverage'], percent=True)}); {forecast['unavailable']} unavailable. "
                  "All three Brier scores use the same available eligible dates; lower is better.", "",
                  "| Forecast | Multiclass Brier |", "|---|---:|"]
        for name, score in forecast["brier"].items():
            lines.append(f"| {name} | {_number(score)} |")
        lines += ["", "| Current state | Available / opportunities | Coverage |", "|---|---:|---:|"]
        for state, coverage in forecast["by_current_state"].items():
            lines.append(f"| {state} | {coverage['available']}/{coverage['opportunities']} | {_number(coverage['coverage'], percent=True)} |")
        gaps = result["snapshot"]["assets"][asset]["unusually_long_gaps"]
        lines += ["", f"Snapshot unusually long observed calendar gaps: {len(gaps)} (details in manifest).", ""]
    lines += ["## Limits", "", "No parameter search, live trades, leverage, short borrowing, taxes, or intraday fill simulation. "
              "The cost grid is a sensitivity analysis, not measured brokerage costs. Daily close-only prices cannot model "
              "intraday execution or market impact. This comparison does not validate continuous signal sizing or "
              "stationary-distribution risk sizing. Undefined metrics are null in JSON with an unavailable reason.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Explicitly acquire a NEW immutable Yahoo snapshot")
    fetch.add_argument("--data-dir", type=Path, required=True)
    evaluate = commands.add_parser("evaluate", help="Evaluate frozen inputs offline")
    evaluate.add_argument("--data-dir", type=Path, default=ROOT / "research" / "data" / "baseline-v1")
    evaluate.add_argument("--output-dir", type=Path, default=ROOT / "research" / "results" / "baseline-v1")
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            manifest = fetch_snapshot(args.data_dir)
            print(json.dumps({"snapshot": str(args.data_dir), "assets": list(manifest["assets"])}))
        else:
            result = evaluate_snapshot(args.data_dir)
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / "evaluation.json").write_text(
                json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
            )
            (args.output_dir / "report.md").write_text(render_report(result), encoding="utf-8", newline="\n")
            print(json.dumps({"evaluation": str(args.output_dir / "evaluation.json"),
                              "report": str(args.output_dir / "report.md")}))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
