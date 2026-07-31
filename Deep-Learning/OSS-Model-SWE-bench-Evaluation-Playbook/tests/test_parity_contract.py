import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_run_contracts.py"
REFERENCE = ROOT / "examples" / "parity-reference.toml"
CANDIDATE = ROOT / "examples" / "parity-candidate.toml"


class ParityContractTests(unittest.TestCase):
    def run_gate(
        self,
        reference: Path,
        candidate: Path,
        *extra: str,
        scenario: str = "platform_migration",
    ):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reference",
                str(reference),
                "--candidate",
                str(candidate),
                "--scenario",
                scenario,
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def candidate_copy(self, replace_from: str, replace_to: str) -> Path:
        root = Path(self.tempdir.name)
        candidate = root / "candidate.toml"
        text = CANDIDATE.read_text()
        self.assertIn(replace_from, text)
        candidate.write_text(text.replace(replace_from, replace_to, 1))
        return candidate

    def contract_copy(self, source: Path, replacements: list[tuple[str, str]]) -> Path:
        root = Path(self.tempdir.name)
        candidate = root / "scenario-candidate.toml"
        text = source.read_text()
        for replace_from, replace_to in replacements:
            self.assertIn(replace_from, text)
            text = text.replace(replace_from, replace_to, 1)
        candidate.write_text(text)
        return candidate

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_platform_migration_allows_endpoint_and_runtime_differences(self) -> None:
        result = self.run_gate(REFERENCE, CANDIDATE)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("classification=MODEL_AND_METHOD_ALIGNED", result.stdout)

    def test_model_revision_mismatch_fails_closed(self) -> None:
        candidate = self.candidate_copy(
            'revision = "2026-07-01"', 'revision = "different-revision"'
        )
        result = self.run_gate(REFERENCE, candidate)
        self.assertEqual(result.returncode, 4)
        self.assertIn("VIOLATION model.revision", result.stderr)

    def test_unverified_identity_downgrades_claim(self) -> None:
        candidate = self.candidate_copy(
            "a" * 64,
            "UNVERIFIED",
        )
        result = self.run_gate(REFERENCE, candidate)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("classification=METHOD_ALIGNED", result.stdout)

    def test_custom_adaptation_requires_explicit_acceptance(self) -> None:
        candidate = self.candidate_copy('version = "2.4.6"', 'version = "2.5.0"')
        review = self.run_gate(
            REFERENCE, candidate, "--allow-difference", "agent.version"
        )
        self.assertEqual(review.returncode, 3)
        self.assertIn("classification=ADAPTED_RUN", review.stdout)
        accepted = self.run_gate(
            REFERENCE,
            candidate,
            "--allow-difference",
            "agent.version",
            "--accept-adapted",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr or accepted.stdout)

    def test_context_below_required_tokens_is_invalid(self) -> None:
        candidate = self.candidate_copy(
            "context_length = 262144", "context_length = 65536"
        )
        result = self.run_gate(REFERENCE, candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("PARITY_CONTRACT_INVALID", result.stderr)

    def test_finetuning_allows_only_the_controlled_model_change(self) -> None:
        candidate = self.contract_copy(
            REFERENCE,
            [
                ('label = "onprem-reference"', 'label = "finetuned-candidate"'),
                ('revision = "2026-07-01"', 'revision = "finetuned-v1"'),
                ("a" * 64, "7" * 64),
                (
                    'deployment_name = "contoso-code-7b"',
                    'deployment_name = "contoso-code-7b-finetuned"',
                ),
            ],
        )
        result = self.run_gate(
            REFERENCE, candidate, scenario="finetuning"
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("classification=FINETUNING_METHOD_ALIGNED", result.stdout)

    def test_model_selection_has_its_own_claim_class(self) -> None:
        candidate = self.contract_copy(
            CANDIDATE,
            [
                ('family = "contoso-code-7b"', 'family = "fabrikam-code-4b"'),
                ('revision = "2026-07-01"', 'revision = "2026-07-15"'),
                ("a" * 64, "8" * 64),
            ],
        )
        result = self.run_gate(
            REFERENCE, candidate, scenario="model_selection"
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("classification=MODEL_SELECTION_METHOD_ALIGNED", result.stdout)

    def test_finetuning_rejects_platform_drift(self) -> None:
        result = self.run_gate(REFERENCE, CANDIDATE, scenario="finetuning")
        self.assertEqual(result.returncode, 4)
        self.assertIn("VIOLATION endpoint.mode", result.stderr)

    def test_sampling_change_fails_platform_migration(self) -> None:
        candidate = self.candidate_copy("temperature = 0.0", "temperature = 0.2")
        result = self.run_gate(REFERENCE, candidate)
        self.assertEqual(result.returncode, 4)
        self.assertIn("VIOLATION generation.temperature", result.stderr)

    def test_partition_change_fails_platform_migration(self) -> None:
        candidate = self.candidate_copy("4" * 64, "9" * 64)
        result = self.run_gate(REFERENCE, candidate)
        self.assertEqual(result.returncode, 4)
        self.assertIn("VIOLATION orchestration.partition_manifest_sha256", result.stderr)


if __name__ == "__main__":
    unittest.main()