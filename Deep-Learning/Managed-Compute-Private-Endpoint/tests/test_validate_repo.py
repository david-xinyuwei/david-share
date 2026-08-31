import copy
import importlib.util
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "validate_repo.py"
SPEC = importlib.util.spec_from_file_location("validate_repo", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RepositoryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = VALIDATOR.build_rule_results()
        self.expected_applicability = {
            rule["id"]: rule["applicable"] for rule in self.document["rules"]
        }

    def assert_invalid(self, candidate, expected_error: str) -> None:
        errors = VALIDATOR.validate_rule_results_document(
            candidate,
            self.expected_applicability,
        )
        self.assertTrue(
            any(expected_error in error for error in errors),
            f"Expected {expected_error!r} in {errors!r}",
        )

    def test_generated_rule_document_is_structurally_valid(self) -> None:
        self.assertEqual(
            VALIDATOR.validate_rule_results_document(
                self.document,
                self.expected_applicability,
            ),
            [],
        )

    def test_missing_rule_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        missing_id = candidate["rules"].pop()["id"]
        self.assert_invalid(candidate, f"missing rule: {missing_id}")

    def test_duplicate_rule_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"].append(copy.deepcopy(candidate["rules"][0]))
        self.assert_invalid(candidate, "duplicate rule: RUN-001")

    def test_unknown_rule_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0]["id"] = "RUN-999"
        self.assert_invalid(candidate, "unknown rule: RUN-999")

    def test_false_applicability_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0].update(
            applicable=False,
            status="N/A",
            reason="mutated",
            checks=[],
            evidence=[],
        )
        self.assert_invalid(candidate, "false applicability: RUN-001")

    def test_failed_check_with_forged_pass_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0]["checks"][0]["passed"] = False
        self.assert_invalid(candidate, "forged status: RUN-001=PASS")

    def test_absolute_evidence_path_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0]["evidence"][0] = "C:\\outside.json"
        self.assert_invalid(candidate, "absolute evidence path")

    def test_parent_evidence_escape_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0]["evidence"][0] = "../outside.json"
        self.assert_invalid(candidate, "parent traversal in evidence path")

    def test_missing_evidence_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0]["evidence"][0] = "evidence/not-present.json"
        self.assert_invalid(candidate, "missing evidence path")

    def test_duplicate_check_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.document)
        candidate["rules"][0]["checks"].append(
            copy.deepcopy(candidate["rules"][0]["checks"][0])
        )
        self.assert_invalid(candidate, "duplicate check: RUN-001")

    def test_symlink_evidence_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            root = base / "repo"
            root.mkdir()
            outside = base / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            link = root / "link.json"
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"Current Windows policy cannot create symlinks: {error}")
            errors = VALIDATOR.validate_evidence_path("link.json", root)
            self.assertTrue(
                any("outside repository" in error for error in errors),
                errors,
            )

    def test_quick_start_stages_are_complete_and_ordered(self) -> None:
        readme = (MODULE_PATH.parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertTrue(all(VALIDATOR.quick_start_stage_results(readme).values()))

    def test_embedded_rule_mutations_all_fail_closed(self) -> None:
        results = VALIDATOR.run_rule_contract_mutation_checks(self.document)
        self.assertTrue(results and all(results.values()), results)


if __name__ == "__main__":
    unittest.main()