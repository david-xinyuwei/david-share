import copy
import hashlib
import importlib.util
import pathlib
import tempfile
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

    def test_cli_transcript_exposes_the_code_path_differential(self) -> None:
        transcript = BUILDER.build_cli_transcript()
        required = (
            "ORIGINAL_TERMINAL_CAPTURE=false",
            "CLIENT=Python HTTPS client with Microsoft Entra bearer token",
            "ACTUAL_PROBE_OUTPUT_RETAINED=true",
            "REPRODUCTION_ENTRYPOINT=scripts/probe_endpoint.py",
            "MODEL_DEPLOYMENT_CHANGED=false",
            "IDENTITY_SHA256=887146420b45005bf903fd183eda936b0e3fee00aa6be67a91a47f0546b54e6c",
            "DEPLOYMENT_SHA256=4d87fdbcba1fe6671069062752306ee4957a40c6ac281803b423c80ddd682776",
            "REQUEST_SHA256=c4c06fac9fe6ed09d3f3117ca538e1f1d9e8be12330d5ef9b36284b6e4120804",
            "PRIVATE_RUNNER=private-IP Azure Container Instances in a linked VNet workload subnet (not Bastion)",
            "[1/5] OUTSIDE_VNET_PNA_ENABLED_BASELINE",
            "[2/5] INSIDE_LINKED_VNET_PNA_ENABLED_PREFLIGHT",
            "[3/5] OUTSIDE_VNET_PNA_DISABLED",
            "HTTP_STATUS=403",
            "NETWORK_POLICY_BLOCKED=true",
            "ERROR_CATEGORY=public-access-disabled",
            "[4/5] INSIDE_LINKED_VNET_PNA_DISABLED",
            "HTTP_STATUS=200",
            "RESPONSE_OBJECT=chat.completion",
            "RUNNER_EXIT_CODE=0",
            "[5/5] OUTSIDE_VNET_PNA_RESTORED",
        )
        self.assertTrue(all(value in transcript for value in required))
        self.assertNotIn("sensitive output", transcript)

    def test_text_hash_is_stable_across_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "sample.json"
            path.write_bytes(b'{"value": 1}\r\n')
            windows_hash = BUILDER.sha256(path)
            path.write_bytes(b'{"value": 1}\n')
            linux_hash = BUILDER.sha256(path)
        self.assertEqual(windows_hash, linux_hash)
        self.assertEqual(
            linux_hash,
            hashlib.sha256(b'{"value": 1}\n').hexdigest(),
        )

    def test_public_success_cannot_replace_blocked_observation(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-blocked.json"]["httpStatus"] = 200
        with self.assertRaisesRegex(ValueError, "authenticated 403"):
            BUILDER.validate_observations(tampered)

    def test_different_identity_fingerprint_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-restored.json"]["identitySha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint chain"):
            BUILDER.validate_observations(tampered)

    def test_non_policy_403_category_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-blocked.json"]["errorCategory"] = "service-error"
        with self.assertRaisesRegex(ValueError, "authenticated 403"):
            BUILDER.validate_observations(tampered)

    def test_public_block_cannot_replace_baseline_observation(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-baseline.json"]["httpStatus"] = 403
        with self.assertRaisesRegex(ValueError, "public 200"):
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
        tampered["private-success.json"]["sequence"] = 3
        with self.assertRaisesRegex(ValueError, "scenario sequence"):
            BUILDER.validate_observations(tampered)

    def test_observation_times_must_be_monotonic(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["public-restored.json"]["observedAtUtc"] = tampered[
            "public-blocked.json"
        ]["observedAtUtc"]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            BUILDER.validate_observations(tampered)

    def test_post_test_state_must_follow_scenarios(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["post-test-state.json"]["observedAtUtc"] = tampered[
            "public-blocked.json"
        ]["observedAtUtc"]
        with self.assertRaisesRegex(ValueError, "retained safe state"):
            BUILDER.validate_observations(tampered)

    def test_false_cleanup_claim_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["post-test-state.json"]["temporaryResourcesRetained"] = False
        with self.assertRaisesRegex(ValueError, "retained safe state"):
            BUILDER.validate_observations(tampered)

    def test_private_probe_source_drift_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.observations)
        tampered["private-success.json"]["probeSourceSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint chain"):
            BUILDER.validate_observations(tampered)


if __name__ == "__main__":
    unittest.main()
