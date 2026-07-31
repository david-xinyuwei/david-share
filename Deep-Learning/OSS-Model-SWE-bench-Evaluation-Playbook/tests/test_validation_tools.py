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

from scripts.preflight_provider import count_valid_ping_calls, request_candidates
from scripts.provider_compat import remove_provider_specific_fields
from scripts.swebench_outcomes import validate_scored_canary_counts


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
            "model.model_class=scripts.provider_model.FoundryOpenAIModel", args
        )
        self.assertNotIn("azure-secret-probe", args)
        self.assertIn("HOSTED_VLLM_API_KEY=azure-secret-probe", env)
        self.assertNotIn("HOSTED_VLLM_API_KEY=stale-token-probe", env)
        self.assertEqual(contract["evaluation_scenario"], "onprem_to_managed")
        self.assertEqual(contract["auth_env_name"], "HOSTED_VLLM_API_KEY")

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

    def test_fireworks_mode_routes_glm_without_secret_in_argv(self) -> None:
        output, capture = self.run_generation_mode(
            "fireworks",
            "accounts/example/models/glm-5-2",
            MODEL_API_KEY="fireworks-secret-probe",
        )
        args = (capture / "args.txt").read_text()
        env = (capture / "env.txt").read_text()
        contract = json.loads((output / "provider-contract.json").read_text())
        self.assertIn(
            "model.model_name=fireworks_ai/accounts/example/models/glm-5-2", args
        )
        self.assertIn("https://api.fireworks.ai/inference/v1", args)
        self.assertNotIn("fireworks-secret-probe", args)
        self.assertIn("FIREWORKS_AI_API_KEY=fireworks-secret-probe", env)
        self.assertEqual(contract["run_label"], "fireworks-candidate")

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

    def run_preflight(
        self,
        mode: str,
        model: str,
        expected_path: str,
        key_env: str,
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
                payload = {
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
                data = json.dumps(payload).encode()
                self.send_response(200)
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
            env.update(extra_environment)
            env[key_env] = "probe-secret"
            suffix = {
                "openai_compatible": "/v1",
                "azure_foundry": "",
                "fireworks": "/inference/v1",
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
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertNotIn("probe-secret", result.stdout)
        self.assertEqual(captured["path"], expected_path)
        self.assertEqual(captured["body"]["model"], model.split("/", 1)[-1] if mode != "fireworks" else model.removeprefix("fireworks_ai/"))
        return captured, json.loads(result.stdout)

    def test_preflight_openai_compatible_contract(self) -> None:
        captured, result = self.run_preflight(
            "openai_compatible", "hosted_vllm/local-model", "/v1/chat/completions", "MODEL_API_KEY"
        )
        self.assertEqual(captured["authorization"], "Bearer probe-secret")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["valid_ping_calls"], 1)

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

    def test_preflight_fireworks_contract(self) -> None:
        captured, result = self.run_preflight(
            "fireworks", "fireworks_ai/accounts/example/models/glm", "/inference/v1/chat/completions", "FIREWORKS_AI_API_KEY"
        )
        self.assertEqual(captured["authorization"], "Bearer probe-secret")
        self.assertEqual(result["state"], "PASS")


if __name__ == "__main__":
    unittest.main()
