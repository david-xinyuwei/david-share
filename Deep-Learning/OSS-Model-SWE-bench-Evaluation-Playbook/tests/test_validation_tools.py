import csv
import json
import subprocess
import sys
import tempfile
import unittest
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from scripts.preflight_provider import count_valid_ping_calls, request_candidates
from scripts.provider_compat import remove_provider_specific_fields
from scripts.swebench_outcomes import canary_outcome, validate_scored_canary_counts


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class ValidationToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_script(self, name: str, *args: str, expect_success: bool = True):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if expect_success and result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return result

    def make_generation(self, ids=("a", "b")) -> Path:
        run = self.root / "run"
        run.mkdir()
        predictions = {}
        for instance_id in ids:
            predictions[instance_id] = {
                "instance_id": instance_id,
                "model_name_or_path": "test-model",
                "model_patch": "diff --git a/a.py b/a.py\n" if instance_id == "a" else "",
            }
            instance = run / instance_id
            instance.mkdir()
            (instance / f"{instance_id}.traj.json").write_text(
                json.dumps(
                    {
                        "info": {
                            "exit_status": (
                                "Submitted" if instance_id == "a" else "RepeatedFormatError"
                            ),
                            "config": {
                                "environment": {"image": f"image-{instance_id}"},
                                "model": {"model_name": "test-model"},
                            },
                        }
                    }
                )
            )
        (run / "preds.json").write_text(json.dumps(predictions))
        return run

    def test_prediction_validation_and_config_audit(self) -> None:
        run = self.make_generation()
        manifest = self.root / "manifest.tsv"
        with manifest.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["instance_id"], delimiter="\t")
            writer.writeheader()
            writer.writerows([{"instance_id": "a"}, {"instance_id": "b"}])
        summary = self.root / "summary.json"
        self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--manifest",
            str(manifest),
            "--expected-count",
            "2",
            "--summary",
            str(summary),
        )
        payload = json.loads(summary.read_text())
        self.assertEqual(payload["nonempty_patches"], 1)
        self.assertEqual(payload["empty_patches"], 1)
        audit = self.run_script("audit_effective_configs.py", "--run-dir", str(run))
        self.assertIn('"normalized_config_count": 1', audit.stdout)

    def test_prediction_manifest_mismatch_fails(self) -> None:
        run = self.make_generation()
        manifest = self.root / "manifest.tsv"
        manifest.write_text("instance_id\na\n")
        result = self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--manifest",
            str(manifest),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differ from the frozen manifest", result.stderr)

    def test_prediction_embedded_id_mismatch_fails(self) -> None:
        run = self.make_generation(ids=("a",))
        predictions_path = run / "preds.json"
        predictions = json.loads(predictions_path.read_text())
        predictions["a"]["instance_id"] = "different"
        predictions_path.write_text(json.dumps(predictions))
        result = self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--expected-count",
            "1",
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("key and embedded instance_id differ", result.stderr)

    def test_report_merge_rejects_overlap(self) -> None:
        first = self.root / "first.json"
        second = self.root / "second.json"
        first.write_text(json.dumps({"resolved_ids": ["a"], "unresolved_ids": []}))
        second.write_text(json.dumps({"resolved_ids": ["a"], "unresolved_ids": []}))
        result = self.run_script(
            "merge_official_reports.py",
            "--report",
            str(first),
            "--report",
            str(second),
            "--expected-count",
            "2",
            "--output",
            str(self.root / "merged.json"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overlap", result.stderr.lower())

    def test_report_merge_rejects_incomplete_coverage(self) -> None:
        report = self.root / "report.json"
        report.write_text(json.dumps({"resolved_ids": ["a"], "unresolved_ids": []}))
        result = self.run_script(
            "merge_official_reports.py",
            "--report",
            str(report),
            "--expected-count",
            "2",
            "--output",
            str(self.root / "merged.json"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("coverage 1 != expected 2", result.stderr)

    def test_report_merge_refuses_existing_output(self) -> None:
        report = self.root / "report.json"
        report.write_text(
            json.dumps(
                {
                    "resolved_ids": ["a"],
                    "unresolved_ids": [],
                    "empty_patch_ids": [],
                    "error_ids": [],
                }
            )
        )
        output = self.root / "merged.json"
        output.write_text('{"existing": true}\n')
        result = self.run_script(
            "merge_official_reports.py",
            "--report",
            str(report),
            "--expected-count",
            "1",
            "--output",
            str(output),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite", result.stderr)
        self.assertEqual(json.loads(output.read_text()), {"existing": True})

    def test_scored_canary_rejects_infrastructure_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "infrastructure error"):
            validate_scored_canary_counts(
                {
                    "resolved_instances": 0,
                    "unresolved_instances": 0,
                    "empty_patch_instances": 0,
                    "error_instances": 1,
                }
            )

    def test_scored_canary_requires_all_outcome_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required field"):
            validate_scored_canary_counts({"resolved_instances": 1})

    def test_pipeline_canary_names_the_scoreable_outcome(self) -> None:
        self.assertEqual(
            canary_outcome({"resolved": 1, "unresolved": 0, "empty": 0, "errors": 0}),
            "Resolved",
        )
        self.assertEqual(
            canary_outcome({"resolved": 0, "unresolved": 1, "empty": 0, "errors": 0}),
            "Unresolved",
        )
        self.assertEqual(
            canary_outcome({"resolved": 0, "unresolved": 0, "empty": 1, "errors": 0}),
            "Empty",
        )

    def test_time_exceeded_is_a_valid_agent_limit(self) -> None:
        run = self.make_generation(ids=("a",))
        trajectory = run / "a" / "a.traj.json"
        payload = json.loads(trajectory.read_text())
        payload["info"]["exit_status"] = "TimeExceeded"
        trajectory.write_text(json.dumps(payload))
        result = self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--expected-count",
            "1",
        )
        self.assertIn('"TimeExceeded": 1', result.stdout)

    def test_hash_assets_rejects_empty_root(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        result = self.run_script(
            "hash_assets.py",
            str(empty),
            "--output",
            str(empty / "SHA256SUMS.txt"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No files found", result.stderr)

    def test_hash_assets_refuses_existing_manifest(self) -> None:
        assets = self.root / "assets"
        assets.mkdir()
        (assets / "evidence.json").write_text("{}\n")
        manifest = assets / "SHA256SUMS.txt"
        manifest.write_text("existing manifest\n")
        result = self.run_script(
            "hash_assets.py",
            str(assets),
            "--output",
            str(manifest),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite", result.stderr)
        self.assertEqual(manifest.read_text(), "existing manifest\n")

    def test_workflow_diagram_matches_generator(self) -> None:
        output = self.root / "workflow.png"
        self.run_script(
            "generate_workflow_diagram.py",
            "--output",
            str(output),
        )
        self.assertEqual(
            output.read_bytes(),
            (ROOT / "images" / "swebench_workflow.png").read_bytes(),
        )

    def test_roles_diagram_matches_generator(self) -> None:
        output = self.root / "roles.png"
        self.run_script(
            "generate_roles_diagram.py",
            "--output",
            str(output),
        )
        self.assertEqual(
            output.read_bytes(),
            (ROOT / "images" / "swebench_roles.png").read_bytes(),
        )

    def test_mimo_result_diagram_matches_generator(self) -> None:
        output = self.root / "mimo-result.png"
        self.run_script(
            "generate_mimo_result_diagram.py",
            "--output",
            str(output),
        )
        self.assertEqual(
            output.read_bytes(),
            (ROOT / "images" / "mimo_swebench_result.png").read_bytes(),
        )

    def test_mimo_full_result_uses_submitted_denominator(self) -> None:
        payload = yaml.safe_load(
            (ROOT / "examples" / "live-azure-gpu-vm-mimo-v25-pro-full500.yaml").read_text()
        )
        result = payload["result"]
        self.assertEqual(
            result["resolved_instances"] + result["unresolved_instances"],
            result["completed_instances"],
        )
        self.assertEqual(
            result["completed_instances"]
            + result["empty_patch_instances"]
            + result["error_instances"],
            result["total_instances"],
        )
        self.assertEqual(result["resolved_rate_percent"], 72.00)
        self.assertFalse(payload["scope"]["generation_rerun_for_this_result"])

    def test_readme_evidence_claims_match_sealed_yaml(self) -> None:
        readme = (ROOT / "README.md").read_text()
        readme_cn = (ROOT / "README-CN.md").read_text()
        mimo = yaml.safe_load(
            (ROOT / "examples" / "live-azure-gpu-vm-mimo-v25-pro-full500.yaml").read_text()
        )["result"]
        self.assertIn(
            f"{mimo['resolved_instances']} Resolved / {mimo['total_instances']} submitted "
            f"({mimo['resolved_rate_percent']:.2f}%), {mimo['empty_patch_instances']} Empty",
            readme,
        )
        self.assertIn(
            f"{mimo['resolved_instances']} Resolved / {mimo['total_instances']} submitted"
            f"（{mimo['resolved_rate_percent']:.2f}%），{mimo['empty_patch_instances']}个Empty",
            readme_cn,
        )
        managed = yaml.safe_load(
            (ROOT / "examples" / "live-foundry-managed-compute-scored-canary.yaml").read_text()
        )["official_evaluation"]
        marker = (
            f"{managed['resolved_instances']} Resolved / "
            f"{managed['unresolved_instances']} Unresolved / "
            f"{managed['empty_patch_instances']} Empty / "
            f"{managed['error_instances']} Error"
        )
        self.assertIn(marker, readme)
        self.assertIn(marker, readme_cn)
        self.assertNotIn("or an enabled account key", readme)
        self.assertNotIn("或已启用的account key", readme_cn)

        examples = ROOT / "examples"
        for name in (
            "live-foundry-direct-deepseek-v4-flash-scored-canary.yaml",
            "live-foundry-fw-glm51-scored-canary.yaml",
        ):
            reproduction = yaml.safe_load((examples / name).read_text())["reproduction"]["cli"]
            self.assertIn('export MODEL_API_KEY="<credential>"', reproduction)
            self.assertNotIn("AZURE_AD_TOKEN", reproduction)

        managed_evidence = yaml.safe_load(
            (examples / "live-foundry-managed-compute-scored-canary.yaml").read_text()
        )
        self.assertEqual(managed_evidence["provider"]["authentication"], "microsoft_entra_id")
        self.assertTrue(managed_evidence["provider"]["local_key_authentication"] == "disabled")

        for text in (readme, readme_cn):
            self.assertIn("| AI Foundry OSS Serverless | `azure_foundry` | `MODEL_API_KEY` |", text)
            self.assertIn("| AI Foundry / Fireworks | `azure_foundry` | `MODEL_API_KEY` |", text)
            self.assertIn('export MODEL_API_KEY="<deployment-key>"', text)
            self.assertIn('export MODEL_API_KEY="<resource-key>"', text)
            self.assertIn("disableLocalAuth=true", text)
            self.assertIn(
                "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/configure-entra-id",
                text,
            )

    def test_readme_uses_exact_sparse_checkout_and_four_azure_profiles(self) -> None:
        readme = (ROOT / "README.md").read_text()
        readme_cn = (ROOT / "README-CN.md").read_text()
        for text in (readme, readme_cn):
            self.assertIn("git clone --filter=blob:none --sparse --branch master", text)
            self.assertIn(
                "git sparse-checkout set --no-cone \\\n"
                "  '/Deep-Learning/OSS-Model-SWE-bench-Evaluation-Playbook/'",
                text,
            )
            self.assertIn("AI Foundry OSS<br/>Serverless", text)
            self.assertIn("Same Agent<br/>Same dataset<br/>Official harness" if text is readme else "相同Agent<br/>相同题目集<br/>官方harness", text)
            self.assertNotIn("AI Foundry Serverless", text)
        self.assertEqual(readme.count("### AI Foundry OSS Serverless"), 1)
        self.assertEqual(readme.count("### AI Foundry Managed Compute"), 1)
        self.assertEqual(readme.count("### AI Foundry / Fireworks"), 1)
        self.assertEqual(readme_cn.count("### AI Foundry OSS Serverless"), 1)
        self.assertEqual(readme_cn.count("### AI Foundry Managed Compute"), 1)
        self.assertEqual(readme_cn.count("### AI Foundry / Fireworks"), 1)

    def test_public_evidence_preserves_claim_boundaries(self) -> None:
        examples = ROOT / "examples"
        for name in (
            "live-foundry-direct-deepseek-v4-flash-scored-canary.yaml",
            "live-foundry-fw-glm51-scored-canary.yaml",
        ):
            payload = yaml.safe_load((examples / name).read_text())
            self.assertFalse(payload["scope"]["accuracy_estimate"])
            self.assertFalse(payload["scope"]["full_run_completed"])
            self.assertEqual(payload["scope"]["sample_size"], 1)

        managed = yaml.safe_load(
            (examples / "live-foundry-managed-compute-pending.yaml").read_text()
        )
        self.assertFalse(managed["scope"]["accuracy_estimate"])
        self.assertFalse(managed["scope"]["scored_canary_started"])
        self.assertFalse(managed["scope"]["full_run_completed"])
        self.assertEqual(managed["data_plane"]["models_list"]["state"], "PASS")
        self.assertEqual(managed["data_plane"]["chat_completion"]["http_status"], 500)
        self.assertEqual(managed["classification"]["verification"], "NOT_VERIFIED")
        self.assertEqual(
            managed["superseded_by"],
            "live-foundry-managed-compute-scored-canary.yaml",
        )

        managed_verified = yaml.safe_load(
            (examples / "live-foundry-managed-compute-scored-canary.yaml").read_text()
        )
        self.assertFalse(managed_verified["scope"]["accuracy_estimate"])
        self.assertFalse(managed_verified["scope"]["full_run_completed"])
        self.assertEqual(managed_verified["scope"]["instance_id"], "sympy__sympy-20590")
        self.assertEqual(managed_verified["generation"]["agent_step_limit"], 40)
        self.assertEqual(managed_verified["generation"]["nonempty_patches"], 1)
        self.assertGreater(managed_verified["generation"]["patch_bytes"], 0)
        self.assertEqual(managed_verified["official_evaluation"]["unresolved_instances"], 1)
        self.assertEqual(managed_verified["official_evaluation"]["empty_patch_instances"], 0)
        self.assertEqual(managed_verified["official_evaluation"]["error_instances"], 0)
        self.assertEqual(managed_verified["claim_boundary"]["provider_data_plane"], "VERIFIED")
        self.assertEqual(managed_verified["claim_boundary"]["nonempty_patch_generation"], "VERIFIED")
        self.assertEqual(managed_verified["claim_boundary"]["model_accuracy"], "NOT_CLAIMED")

    def test_generation_refuses_nonempty_output_dir(self) -> None:
        fake_bin = self.root / "generation-fake-bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        fake_docker.write_text("#!/bin/bash\nexit 0\n")
        fake_docker.chmod(0o755)
        output = self.root / "existing-generation"
        output.mkdir()
        (output / "existing.json").write_text("{}\n")
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "OUTPUT_DIR": str(output),
                "MODEL_NAME": "local-model",
                "MODEL_API_BASE": "http://127.0.0.1:8000/v1",
                "MODEL_API_KEY": "EMPTY",
                "PYTHON_EXECUTABLE": "/bin/false",
            }
        )
        result = subprocess.run(
            ["bash", str(SCRIPTS / "run_generation.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("OUTPUT_DIR must be empty", result.stderr)

    def test_official_harness_refuses_nonempty_report_dir(self) -> None:
        fake_bin = self.root / "harness-fake-bin"
        fake_bin.mkdir()
        fake_python = fake_bin / "python"
        fake_python.write_text("#!/bin/bash\nexit 0\n")
        fake_python.chmod(0o755)
        predictions = self.root / "preds.json"
        predictions.write_text("{}\n")
        report_dir = self.root / "existing-report"
        report_dir.mkdir()
        (report_dir / "existing.json").write_text("{}\n")
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "PREDICTIONS_PATH": str(predictions),
                "RUN_ID": "test-run",
                "REPORT_DIR": str(report_dir),
            }
        )
        result = subprocess.run(
            ["bash", str(SCRIPTS / "run_official_harness.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("REPORT_DIR must be empty unless RESUME=true", result.stderr)

    def test_official_harness_resume_reuses_nonempty_report_dir(self) -> None:
        fake_bin = self.root / "harness-resume-bin"
        fake_bin.mkdir()
        captured_args = self.root / "harness-resume-args.txt"
        fake_python = fake_bin / "python"
        fake_python.write_text("#!/bin/bash\nprintf '%s\\n' \"$@\" > \"$CAPTURE_FILE\"\n")
        fake_python.chmod(0o755)
        predictions = self.root / "resume-preds.json"
        predictions.write_text("{}\n")
        report_dir = self.root / "resume-report"
        report_dir.mkdir()
        (report_dir / "existing-report.json").write_text("{}\n")
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "CAPTURE_FILE": str(captured_args),
                "PREDICTIONS_PATH": str(predictions),
                "RUN_ID": "same-run",
                "REPORT_DIR": str(report_dir),
                "RESUME": "true",
            }
        )
        result = subprocess.run(
            ["bash", str(SCRIPTS / "run_official_harness.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = captured_args.read_text().splitlines()
        self.assertIn("same-run", args)
        self.assertEqual(args[args.index("--report_dir") + 1], str(report_dir.resolve()))

    def test_official_harness_uses_official_cli_defaults(self) -> None:
        fake_bin = self.root / "harness-capture-bin"
        fake_bin.mkdir()
        captured_args = self.root / "harness-args.txt"
        fake_python = fake_bin / "python"
        fake_python.write_text("#!/bin/bash\nprintf '%s\\n' \"$@\" > \"$CAPTURE_FILE\"\n")
        fake_python.chmod(0o755)
        predictions = self.root / "preds.json"
        predictions.write_text("{}\n")
        report_dir = self.root / "report"
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "CAPTURE_FILE": str(captured_args),
                "PREDICTIONS_PATH": str(predictions),
                "RUN_ID": "test-run",
                "REPORT_DIR": str(report_dir),
            }
        )
        result = subprocess.run(
            ["bash", str(SCRIPTS / "run_official_harness.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = captured_args.read_text().splitlines()
        self.assertEqual(args[:2], ["-m", "swebench.harness.run_evaluation"])
        self.assertEqual(args[args.index("--clean") + 1], "false")
        self.assertNotIn("--rewrite_reports", args)

    def run_generation_mode(self, mode: str, model_name: str, **environment: str):
        fake_bin = self.root / f"fake-{mode}"
        fake_bin.mkdir()
        capture = self.root / f"capture-{mode}"
        capture.mkdir()
        fake_python = fake_bin / "python"
        fake_python.write_text(
            "#!/bin/bash\n"
            "if [[ \"${1:-}\" == '-' ]]; then exec \"$REAL_PYTHON\" \"$@\"; fi\n"
            "printf '%s\\n' \"$@\" > \"$CAPTURE_DIR/args.txt\"\n"
            "env | sort > \"$CAPTURE_DIR/env.txt\"\n"
        )
        fake_python.chmod(0o755)
        fake_python3 = fake_bin / "python3"
        fake_python3.write_text(fake_python.read_text())
        fake_python3.chmod(0o755)
        fake_docker = fake_bin / "docker"
        fake_docker.write_text("#!/bin/bash\nexit 0\n")
        fake_docker.chmod(0o755)
        output = self.root / f"output-{mode}"
        env = os.environ.copy()
        for name in (
            "AGENT_STEP_LIMIT",
            "AZURE_AD_TOKEN",
            "AZURE_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "HOSTED_VLLM_API_KEY",
            "MODEL_API_BASE",
            "MODEL_API_KEY",
        ):
            env.pop(name, None)
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "REAL_PYTHON": sys.executable,
                "CAPTURE_DIR": str(capture),
                "OUTPUT_DIR": str(output),
                "ENDPOINT_MODE": mode,
                "EVALUATION_SCENARIO": "onprem_to_managed",
                "RUN_LABEL": f"{mode}-candidate",
                "MODEL_NAME": model_name,
            }
        )
        env.update(environment)
        result = subprocess.run(
            ["bash", str(SCRIPTS / "run_generation.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return output, capture

    def test_openai_compatible_mode_keeps_secret_out_of_argv(self) -> None:
        output, capture = self.run_generation_mode(
            "openai_compatible",
            "local-model",
            MODEL_API_BASE="http://127.0.0.1:8000/v1",
            MODEL_API_KEY="generic-secret-probe",
        )
        args = (capture / "args.txt").read_text()
        env = (capture / "env.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        self.assertIn("model.model_name=hosted_vllm/local-model", args)
        self.assertIn(
            "model.model_class=scripts.provider_model.SanitizingOpenAIModel", args
        )
        self.assertNotIn("generic-secret-probe", args)
        self.assertIn("HOSTED_VLLM_API_KEY=generic-secret-probe", env)
        self.assertEqual(contract["endpoint_mode"], "openai_compatible")

    def test_azure_foundry_mode_routes_v1_without_secret_in_argv(self) -> None:
        output, capture = self.run_generation_mode(
            "azure_foundry",
            "glm-deployment",
            MODEL_API_BASE="https://example.services.ai.azure.com",
            MODEL_API_KEY="azure-secret-probe",
            AZURE_AD_TOKEN="stale-token-probe",
        )
        args = (capture / "args.txt").read_text()
        env = (capture / "env.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        self.assertIn("model.model_name=hosted_vllm/glm-deployment", args)
        self.assertIn(
            "model.model_kwargs.api_base=https://example.services.ai.azure.com/openai/v1",
            args,
        )
        self.assertIn(
            "model.model_class=scripts.provider_model.SanitizingOpenAIModel", args
        )
        self.assertNotIn("azure-secret-probe", args)
        self.assertIn("HOSTED_VLLM_API_KEY=azure-secret-probe", env)
        self.assertNotIn("HOSTED_VLLM_API_KEY=stale-token-probe", env)
        self.assertEqual(contract["evaluation_scenario"], "onprem_to_managed")
        self.assertEqual(contract["auth_env_name"], "HOSTED_VLLM_API_KEY")

    def test_azure_foundry_accepts_entra_token_without_key(self) -> None:
        output, capture = self.run_generation_mode(
            "azure_foundry",
            "managed-deployment",
            MODEL_API_BASE=(
                "https://example.services.ai.azure.com/managed-deployments/"
                "managed-deployment/v1"
            ),
            MODEL_API_KEY="",
            AZURE_API_KEY="",
            AZURE_OPENAI_API_KEY="",
            AZURE_AD_TOKEN="entra-token-probe",
        )
        args = (capture / "args.txt").read_text()
        env = (capture / "env.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        self.assertNotIn("entra-token-probe", args)
        self.assertIn("HOSTED_VLLM_API_KEY=entra-token-probe", env)
        self.assertEqual(contract["auth_env_name"], "HOSTED_VLLM_API_KEY")

    def test_azure_foundry_managed_compute_preserves_published_v1_route(self) -> None:
        output, capture = self.run_generation_mode(
            "azure_foundry",
            "managed-deployment",
            MODEL_API_BASE=(
                "https://example.services.ai.azure.com/managed-deployments/"
                "managed-deployment/v1"
            ),
            MODEL_API_KEY="azure-secret-probe",
        )
        args = (capture / "args.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        expected = (
            "https://example.services.ai.azure.com/managed-deployments/"
            "managed-deployment/v1"
        )
        self.assertIn(f"model.model_kwargs.api_base={expected}", args)
        self.assertEqual(contract["api_base"], expected)

    def test_foundry_message_adapter_removes_only_transport_metadata(self) -> None:
        messages = [
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "call-1"}],
                "provider_specific_fields": {"reasoning": "transport-only"},
            },
        ]
        sanitized = remove_provider_specific_fields(messages)
        self.assertNotIn("provider_specific_fields", sanitized[1])
        self.assertEqual(sanitized[1]["tool_calls"], [{"id": "call-1"}])
        self.assertEqual(sanitized[0], messages[0])

    def test_instance_manifest_becomes_a_hashed_exact_filter(self) -> None:
        manifest = self.root / "instances.tsv"
        manifest.write_text("instance_id\nrepo__issue-2\nrepo__issue-1\n")
        output, capture = self.run_generation_mode(
            "openai_compatible",
            "local-model",
            MODEL_API_BASE="http://127.0.0.1:8000/v1",
            MODEL_API_KEY="EMPTY",
            INSTANCE_MANIFEST=str(manifest),
        )
        args = (capture / "args.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        self.assertIn("--filter", args)
        self.assertIn(r"^(?:repo__issue\-1|repo__issue\-2)$", args)
        self.assertEqual(contract["instance_selector"], "manifest")
        self.assertRegex(contract["instance_manifest_sha256"], r"^[0-9a-f]{64}$")

    def test_duplicate_instance_manifest_fails_closed(self) -> None:
        manifest = self.root / "duplicates.tsv"
        manifest.write_text("instance_id\nrepo__issue-1\nrepo__issue-1\n")
        fake_bin = self.root / "duplicate-fake-bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        fake_docker.write_text("#!/bin/bash\nexit 0\n")
        fake_docker.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "OUTPUT_DIR": str(self.root / "duplicate-output"),
                "MODEL_NAME": "local-model",
                "MODEL_API_BASE": "http://127.0.0.1:8000/v1",
                "INSTANCE_MANIFEST": str(manifest),
            }
        )
        result = subprocess.run(
            ["bash", str(SCRIPTS / "run_generation.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate instance IDs", result.stderr)

    def test_agent_step_limit_is_explicit_and_recorded(self) -> None:
        output, capture = self.run_generation_mode(
            "openai_compatible",
            "local-model",
            MODEL_API_BASE="http://127.0.0.1:8000/v1",
            MODEL_API_KEY="EMPTY",
            AGENT_STEP_LIMIT="12",
        )
        args = (capture / "args.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        self.assertIn("agent.step_limit=12", args)
        self.assertEqual(contract["agent_step_limit"], 12)

    def run_preflight(
        self,
        mode: str,
        model: str,
        expected_path: str,
        key_env: str,
        response_status: int = 200,
        **extra_environment: str,
    ):
        captured = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured["path"] = self.path
                captured["authorization"] = self.headers.get("Authorization")
                captured["api_key"] = self.headers.get("api-key")
                length = int(self.headers.get("Content-Length", "0"))
                captured["body"] = json.loads(self.rfile.read(length))
                payload = (
                    {
                        "choices": [
                            {
                                "finish_reason": "tool_calls",
                                "message": {
                                    "tool_calls": [
                                        {
                                            "id": "call-1",
                                            "type": "function",
                                            "function": {"name": "ping", "arguments": '{"value":"ok"}'},
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                    if response_status == 200
                    else {"error": {"message": "provider unavailable"}}
                )
                data = json.dumps(payload).encode()
                self.send_response(response_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("x-request-id", "request-1")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            for name in (
                "AZURE_AD_TOKEN",
                "AZURE_API_KEY",
                "AZURE_OPENAI_API_KEY",
                "HOSTED_VLLM_API_KEY",
                "MODEL_API_KEY",
            ):
                env.pop(name, None)
            env.update(extra_environment)
            env[key_env] = "probe-secret"
            suffix = {
                "openai_compatible": "/v1",
                "azure_foundry": "",
            }[mode]
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "preflight_provider.py"),
                    "--mode",
                    mode,
                    "--api-base",
                    f"http://127.0.0.1:{server.server_port}{suffix}",
                    "--model",
                    model,
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        expected_returncode = 0 if response_status == 200 else 3
        self.assertEqual(
            result.returncode,
            expected_returncode,
            result.stderr or result.stdout,
        )
        self.assertNotIn("probe-secret", result.stdout)
        self.assertEqual(captured["path"], expected_path)
        self.assertEqual(captured["body"]["model"], model.split("/", 1)[-1])
        return captured, json.loads(result.stdout)

    def test_preflight_openai_compatible_contract(self) -> None:
        captured, result = self.run_preflight(
            "openai_compatible", "hosted_vllm/local-model", "/v1/chat/completions", "MODEL_API_KEY"
        )
        self.assertEqual(captured["authorization"], "Bearer probe-secret")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["valid_ping_calls"], 1)
        self.assertEqual(result["request_id"], "request-1")

    def test_preflight_rejects_malformed_or_wrong_tool_calls(self) -> None:
        self.assertEqual(
            count_valid_ping_calls(
                [
                    {
                        "type": "function",
                        "function": {"name": "wrong", "arguments": '{"value":"ok"}'},
                    },
                    {
                        "type": "function",
                        "function": {"name": "ping", "arguments": "not-json"},
                    },
                ]
            ),
            0,
        )

    def test_preflight_error_preserves_request_id(self) -> None:
        _, result = self.run_preflight(
            "openai_compatible",
            "hosted_vllm/local-model",
            "/v1/chat/completions",
            "MODEL_API_KEY",
            response_status=500,
        )
        self.assertEqual(
            result["attempts"],
            [
                {
                    "route": "openai-compatible",
                    "http_status": 500,
                    "request_id": "request-1",
                }
            ],
        )

    def test_preflight_azure_foundry_contract(self) -> None:
        captured, result = self.run_preflight(
            "azure_foundry",
            "azure/glm-deployment",
            "/openai/v1/chat/completions",
            "MODEL_API_KEY",
            AZURE_AD_TOKEN="stale-token-probe",
        )
        self.assertEqual(captured["authorization"], "Bearer probe-secret")
        self.assertEqual(result["route"], "v1")

    def test_foundry_preflight_uses_only_the_generation_route(self) -> None:
        self.assertEqual(
            request_candidates(
                "azure_foundry", "https://example.services.ai.azure.com"
            ),
            [
                (
                    "https://example.services.ai.azure.com/openai/v1/chat/completions",
                    "v1",
                )
            ],
        )
        self.assertEqual(
            request_candidates(
                "azure_foundry",
                (
                    "https://example.services.ai.azure.com/managed-deployments/"
                    "managed-deployment/v1"
                ),
            ),
            [
                (
                    "https://example.services.ai.azure.com/managed-deployments/"
                    "managed-deployment/v1/chat/completions",
                    "v1",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
