from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts" / "generate_rule_results.py"
SPEC = importlib.util.spec_from_file_location("lra_rule_results", GENERATOR_PATH)
assert SPEC and SPEC.loader
RULES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RULES)


class RuleResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = RULES.evaluate_rules(ROOT)

    def errors_for(self, mutate):
        document = copy.deepcopy(self.document)
        mutate(document)
        return RULES.validate_document(ROOT, document)

    def test_computed_rules_all_pass(self):
        self.assertEqual(RULES.validate_document(ROOT, self.document), [])
        self.assertEqual(
            {rule["id"] for rule in self.document["rules"]},
            set(RULES.REQUIRED_RULE_IDS),
        )
        self.assertTrue(
            all(
                rule["applicable"] is True and rule["status"] == "PASS"
                for rule in self.document["rules"]
            )
        )

    def test_missing_rule_is_rejected(self):
        errors = self.errors_for(lambda document: document["rules"].pop())
        self.assertTrue(any("missing, duplicated" in error for error in errors))

    def test_duplicate_rule_is_rejected(self):
        def mutate(document):
            document["rules"][-1] = copy.deepcopy(document["rules"][0])

        errors = self.errors_for(mutate)
        self.assertTrue(any("missing, duplicated" in error for error in errors))

    def test_false_applicability_is_rejected(self):
        errors = self.errors_for(
            lambda document: document["rules"][0].update(applicable=False)
        )
        self.assertTrue(any("must be applicable" in error for error in errors))

    def test_pass_with_failed_check_is_rejected(self):
        def mutate(document):
            document["rules"][0]["checks"][0]["passed"] = False
            document["rules"][0]["status"] = "PASS"

        errors = self.errors_for(mutate)
        self.assertTrue(any("does not match computed" in error for error in errors))

    def test_escaping_evidence_path_is_rejected(self):
        errors = self.errors_for(
            lambda document: document["rules"][0]["evidence"].__setitem__(
                0,
                "../README.md",
            )
        )
        self.assertTrue(any("escapes repository root" in error for error in errors))

    def test_absolute_evidence_path_is_rejected(self):
        errors = self.errors_for(
            lambda document: document["rules"][0]["evidence"].__setitem__(
                0,
                str((ROOT / "README.md").resolve()),
            )
        )
        self.assertTrue(any("absolute path is forbidden" in error for error in errors))

    def test_stale_generated_artifact_is_rejected(self):
        contract = RULES.read_json(ROOT, "evidence/run-contract.json")
        outcomes = RULES.rule_mutation_outcomes(ROOT, contract)
        self.assertTrue(outcomes["stale_generated_artifact"])

    def test_manifest_drift_is_rejected(self):
        contract = RULES.read_json(ROOT, "evidence/run-contract.json")
        outcomes = RULES.rule_mutation_outcomes(ROOT, contract)
        self.assertTrue(outcomes["manifest_drift"])


if __name__ == "__main__":
    unittest.main()
