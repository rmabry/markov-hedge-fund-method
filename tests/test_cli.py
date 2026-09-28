import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import markov_regime as m


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "markov_regime.py"


def run_cli(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})


def strict_json(text):
    return json.loads(text, parse_constant=lambda value: pytest.fail(f"Non-JSON value: {value}"))


def test_cli_short_history_is_one_strict_json_object(tmp_path):
    csv = tmp_path / "close.csv"
    csv.write_text("date,close\n2020-01-01,100\n2020-01-02,100\n2020-01-03,100\n2020-01-04,110\n")
    result = run_cli("--csv", str(csv), "--window", "1", "--json", "--no-hmm")
    assert result.returncode == 0, result.stderr
    parsed = strict_json(result.stdout)
    assert parsed["schema_version"] == 2
    assert parsed["signal"] is None


@pytest.mark.parametrize("args", [[], ["--window", "nope"], ["--wat"],
    ["--csv", "missing.csv", "--ticker", "SPY"]])
def test_json_argument_errors_have_json_on_stdout(args):
    result = run_cli("--json", *args)
    assert result.returncode != 0
    assert "error" in strict_json(result.stdout)


def test_cli_exposes_horizon_annualization_and_costs(tmp_path):
    csv = tmp_path / "close.csv"
    csv.write_text("date,close\n2020-01-01,100\n2020-01-02,100\n2020-01-03,100\n2020-01-04,100\n")
    result = run_cli("--csv", str(csv), "--window", "1", "--horizon", "3",
                     "--periods-per-year", "365", "--cost-bps", "10", "--json", "--no-hmm")
    assert result.returncode == 0, result.stderr
    parsed = strict_json(result.stdout)
    assert parsed["params"]["horizon"] == 3
    assert parsed["params"]["periods_per_year"] == 365
    assert parsed["params"]["cost_bps"] == 10


def test_hmm_is_not_a_required_script_dependency():
    metadata = SCRIPT.read_text(encoding="utf-8").split("# ///")[1]
    assert '"hmmlearn"' not in metadata
    assert '"scipy"' not in metadata


def test_pretty_output_handles_unavailable_estimates(capsys):
    import pandas as pd
    close = pd.Series([100.] * 4, index=pd.date_range("2020-01-01", periods=4))
    result = m.analyze(close, source="fixture", window=1, hmm=False)
    m._print_pretty(result)
    assert "unavailable" in capsys.readouterr().out.lower()


def test_optional_hmm_runtime_failure_preserves_observable_model(monkeypatch):
    import pandas as pd
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic fit failure")
    monkeypatch.setattr(m, "fit_hmm", fail)
    close = pd.Series([100.] * 4, index=pd.date_range("2020-01-01", periods=4))
    result = m.analyze(close, source="fixture", window=1)
    assert result["hmm"]["available"] is False
    assert result["next_state_probabilities"]["sideways"] == 1


def test_missing_hmm_import_preserves_observable_model(monkeypatch):
    import pandas as pd
    monkeypatch.setitem(sys.modules, "hmmlearn", None)
    close = pd.Series([100.] * 4, index=pd.date_range("2020-01-01", periods=4))
    result = m.analyze(close, source="fixture", window=1)
    assert result["hmm"]["available"] is False
    assert result["next_state_probabilities"]["sideways"] == 1


def test_nonfinite_hmm_estimate_is_unavailable(monkeypatch):
    import numpy as np
    import pandas as pd
    from types import SimpleNamespace
    model = SimpleNamespace(n_components=3, means_=np.array([[np.nan], [0.], [1.]]))
    monkeypatch.setattr(m, "fit_hmm", lambda *a, **k: (model, None))
    close = pd.Series([100.] * 4, index=pd.date_range("2020-01-01", periods=4))
    result = m.analyze(close, source="fixture", window=1)
    assert result["hmm"]["available"] is False
    assert result["next_state_probabilities"]["sideways"] == 1
