"""Source/fixture synchronization checks, NOT Pine runtime or compiler tests.

The actual indicator executes these literal vectors only when its diagnostic
mode is enabled in TradingView. These checks prevent that test bundle drifting
from the fixtures used by Python; TradingView acceptance is tracked separately.
"""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "tests/fixtures/model_contract.json").read_text())
PINE = (ROOT / "pine-script/markov-hedge-fund-method.pine").read_text(encoding="utf-8")


def pine_array(name):
    match = re.search(rf"\b{re.escape(name)}\s*=\s*array\.from\(([^\n]+)\)", PINE)
    if match is None:
        raise AssertionError(f"Pine diagnostic vector {name!r} is missing")
    values = match.group(1).split(",")
    return [None if "na" in value else float(value.strip()) for value in values]


def flat(matrix):
    return [value for row in matrix for value in row]


class PineFixtureSynchronizationTests(unittest.TestCase):
    def test_canonical_state_constants(self):
        for expected, name in enumerate(CONTRACT["state_order"]):
            match = re.search(rf"\bSTATE_{name.upper()}\s*=\s*(\d+)", PINE)
            self.assertIsNotNone(match, f"Missing named state {name}")
            self.assertEqual(int(match.group(1)), expected)

    def test_threshold_vectors_match_shared_contract(self):
        cases = CONTRACT["threshold_cases"]
        self.assertEqual(pine_array("diag_returns"), [case["return"] for case in cases])
        self.assertEqual(pine_array("diag_states"), [case["expected"] for case in cases])

    def test_transition_vectors_match_shared_contract(self):
        for case in CONTRACT["transition_cases"]:
            with self.subTest(case=case["id"]):
                prefix = "diag_" + case["id"]
                self.assertEqual(pine_array(prefix + "_labels"), case["labels"])
                self.assertEqual(pine_array(prefix + "_counts"), flat(case["expected_counts"]))
                self.assertEqual(pine_array(prefix + "_matrix"), flat(case["expected_matrix"]))

    def test_stationary_vectors_match_shared_contract(self):
        for case in CONTRACT["stationary_cases"]:
            with self.subTest(case=case["id"]):
                prefix = "diag_" + case["id"]
                self.assertEqual(pine_array(prefix + "_matrix"), flat(case["matrix"]))
                expected = case["expected_distribution"] or [None, None, None]
                self.assertEqual(pine_array(prefix + "_pi"), expected)

    def test_label_and_display_vectors_match_shared_contract(self):
        self.assertEqual(pine_array("diag_stable_labels"), CONTRACT["stable_label_case"]["labels"])
        self.assertEqual(pine_array("diag_display_pi"), CONTRACT["table_case"]["distribution"])
        self.assertEqual(pine_array("diag_display_expected"), CONTRACT["table_case"]["expected_display"])
        self.assertEqual(pine_array("diag_display_matrix"), flat(CONTRACT["table_case"]["matrix"]))
        self.assertEqual(pine_array("diag_display_matrix_expected"), flat(CONTRACT["table_case"]["expected_display_matrix"]))


if __name__ == "__main__":
    unittest.main()
