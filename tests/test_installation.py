"""Distribution contract; the observable CLI must not install the HMM stack."""
from pathlib import Path
import ast
import re


ROOT = Path(__file__).resolve().parents[1]


def test_core_script_does_not_require_optional_hmm():
    source = (ROOT / "scripts" / "markov_regime.py").read_text(encoding="utf-8")
    match = re.search(r"^# dependencies = (\[.*\])$", source, re.MULTILINE)
    assert match is not None
    requirements = ast.literal_eval(match.group(1))
    names = {re.split(r"[<>=!~\[]", requirement)[0] for requirement in requirements}
    assert "hmmlearn" not in names, "Core uv launch must not resolve optional HMM"
    assert "scipy" not in names, "No direct scipy dependency is used by the observable model"
    assert names == {"numpy", "pandas", "yfinance"}
