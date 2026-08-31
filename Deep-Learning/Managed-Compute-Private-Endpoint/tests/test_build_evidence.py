import copy
import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "build_evidence.py"
SPEC = importlib.util.spec_from_file_location("build_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class EvidenceBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observations = {
            name: BUILDER.load_raw(BUILDER.RAW_DIR, name) for name in BUILDER.RAW_FILES
        }

    def test_checked_in_raw_observations_form_valid_differential(self) -> None:
        BUILDER.validate_observations(self.observations)

    def test_public_success_cannot_replace_blocked_observation(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-blocked.json"]["httpStatus"] = 200
        with self.assertRaisesRegex(ValueError, "authenticated 403"):
            BUILDER.validate_observations(tampered)

    def test_private_public_dns_cannot_claim_private_success(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["dnsClass"] = "public"
        with self.assertRaisesRegex(ValueError, "private DNS"):
            BUILDER.validate_observations(tampered)

    def test_duplicate_scenario_identity_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["id"] = "public-blocked"
        with self.assertRaisesRegex(ValueError, "scenario identity"):
            BUILDER.validate_observations(tampered)

    def test_wrong_response_identity_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["responseModel"] = "different-model"
        with self.assertRaisesRegex(ValueError, "Chat Completions"):
            BUILDER.validate_observations(tampered)

    def test_missing_completion_output_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["responseObject"] = None
        with self.assertRaisesRegex(ValueError, "Chat Completions"):
            BUILDER.validate_observations(tampered)

    def test_run_contract_identity_is_required(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["control-plane.json"]["runId"] = ""
        with self.assertRaisesRegex(ValueError, "run contract"):
            BUILDER.validate_observations(tampered)

    def test_scenario_run_identity_must_match(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["runId"] = "different-run"
        with self.assertRaisesRegex(ValueError, "run identity"):
            BUILDER.validate_observations(tampered)

    def test_scenario_sequence_must_be_exact(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["sequence"] = 1
        with self.assertRaisesRegex(ValueError, "scenario sequence"):
            BUILDER.validate_observations(tampered)

    def test_observation_times_must_be_monotonic(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-restored.json"]["observedAtUtc"] = tampered[
            "public-blocked.json"
        ]["observedAtUtc"]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            BUILDER.validate_observations(tampered)

    def test_cleanup_must_follow_scenarios(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["cleanup.json"]["observedAtUtc"] = tampered[
            "public-blocked.json"
        ]["observedAtUtc"]
        with self.assertRaisesRegex(ValueError, "safe final state"):
            BUILDER.validate_observations(tampered)

    def test_cleanup_with_remaining_resources_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["cleanup.json"]["temporaryResourceCount"] = 1
        with self.assertRaisesRegex(ValueError, "safe final state"):
            BUILDER.validate_observations(tampered)


if __name__ == "__main__":
    unittest.main()
