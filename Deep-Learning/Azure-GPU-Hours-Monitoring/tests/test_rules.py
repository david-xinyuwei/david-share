"""SOP-68 rule catalog: current results plus mutation checks for malformed or forged catalogs."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_rule_results as rules  # noqa: E402


class RuleResultTests(unittest.TestCase):
    def setUp(self):
        self.data = rules.build()

    def test_committed_results_are_current(self):
        self.assertEqual(rules.main(["--check"]), 0)

    def test_current_evaluation_passes(self):
        self.assertEqual(rules.validate(self.data), [])
        self.assertFalse(any(r["status"] == "FAIL" for r in self.data["rules"]))

    def rejected(self, edit, needle):
        data = copy.deepcopy(self.data)
        edit(data)
        self.assertTrue(any(needle in e for e in rules.validate(data)), rules.validate(data))

    def test_missing_rule_is_rejected(self):
        self.rejected(lambda d: d["rules"].pop(), "RULE_SET")

    def test_duplicate_rule_is_rejected(self):
        self.rejected(lambda d: d["rules"].append(copy.deepcopy(d["rules"][-1])), "RULE_SET")

    def test_unknown_rule_is_rejected(self):
        self.rejected(lambda d: d["rules"].__setitem__(0, {**d["rules"][0], "id": "RUN-999"}), "RULE_SET")

    def test_failed_check_with_forged_pass_is_rejected(self):
        def edit(d):
            d["rules"][0]["checks"][0]["passed"] = False
            d["rules"][0]["status"] = "PASS"
        self.rejected(edit, "FORGED_STATUS")

    def test_absolute_evidence_path_is_rejected(self):
        self.rejected(lambda d: d["rules"][0]["evidence"].append(str(ROOT / "README.md")), "EVIDENCE_ESCAPE")

    def test_parent_evidence_escape_is_rejected(self):
        self.rejected(lambda d: d["rules"][0]["evidence"].append("../README.md"), "EVIDENCE_ESCAPE")

    def test_missing_evidence_is_rejected(self):
        self.rejected(lambda d: d["rules"][0]["evidence"].append("evidence/does-not-exist.json"), "MISSING_EVIDENCE")

    def test_unjustified_na_is_rejected(self):
        self.rejected(lambda d: d["rules"][3].pop("reason"), "UNJUSTIFIED_NA")


if __name__ == "__main__":
    unittest.main()
