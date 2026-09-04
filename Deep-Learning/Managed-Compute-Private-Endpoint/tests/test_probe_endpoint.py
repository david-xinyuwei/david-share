import base64
import importlib.util
import argparse
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "probe_endpoint.py"
SPEC = importlib.util.spec_from_file_location("probe_endpoint", MODULE_PATH)
assert SPEC and SPEC.loader
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class ProbeEndpointTests(unittest.TestCase):
    def test_private_addresses(self) -> None:
        self.assertEqual(PROBE.classify_addresses(["10.0.0.8"]), "private")

    def test_public_addresses(self) -> None:
        self.assertEqual(PROBE.classify_addresses(["8.8.8.8"]), "public")

    def test_mixed_addresses(self) -> None:
        self.assertEqual(
            PROBE.classify_addresses(["10.0.0.8", "8.8.8.8"]),
            "mixed",
        )

    def test_error_summary_keeps_only_contract_fields(self) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "403",
                    "message": "Public access is disabled.",
                    "internal": "must-not-leak",
                }
            }
        ).encode()
        summary = PROBE.summarize_body(body)
        self.assertEqual(summary["errorCode"], "403")
        self.assertEqual(summary["errorCategory"], "public-access-disabled")
        self.assertTrue(summary["networkPolicyBlocked"])
        self.assertNotIn("internal", summary)
        self.assertNotIn("Public access is disabled.", json.dumps(summary))

    def test_success_summary_excludes_generated_content(self) -> None:
        body = json.dumps(
            {
                "object": "chat.completion",
                "model": "example-model",
                "choices": [{"message": {"content": "sensitive output"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
        ).encode()
        summary = PROBE.summarize_body(body)
        self.assertEqual(summary["choiceCount"], 1)
        self.assertNotIn("sensitive output", json.dumps(summary))

    def test_rejects_non_azure_host_before_authentication(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowed Azure AI"):
            PROBE.validate_endpoint("https://example.com/openai/v1/chat/completions")

    def test_rejects_userinfo_query_and_nonstandard_port(self) -> None:
        invalid_endpoints = [
            "https://user" + chr(64) + "example.services.ai.azure.com/openai/v1/chat/completions",
            "https://example.services.ai.azure.com:444/openai/v1/chat/completions",
            "https://example.services.ai.azure.com/openai/v1/chat/completions?redirect=1",
        ]
        for endpoint in invalid_endpoints:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                PROBE.validate_endpoint(endpoint)

    def test_unrelated_403_does_not_pass(self) -> None:
        result = {
            "dnsClass": "public",
            "httpStatus": 403,
            "networkPolicyBlocked": False,
        }
        self.assertFalse(PROBE.result_satisfies_expectation(result, "public", 403))

    def test_token_identity_fingerprint_is_stable_and_secret_free(self) -> None:
        claims = base64.urlsafe_b64encode(
            json.dumps({"tid": "tenant", "oid": "subject"}).encode()
        ).decode().rstrip("=")
        first = PROBE.token_identity_sha256(f"header.{claims}.signature-one")
        second = PROBE.token_identity_sha256(f"header.{claims}.signature-two")
        self.assertEqual(first, second)
        self.assertNotIn("tenant", first)
        self.assertNotIn("subject", first)

    def test_probe_source_digest_is_validated(self) -> None:
        self.assertEqual(PROBE.probe_source_sha256("A" * 64), "a" * 64)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            PROBE.probe_source_sha256("not-a-digest")

    def test_api_key_is_preferred_and_never_reaches_az(self) -> None:
        args = argparse.Namespace(
            api_key_environment_variable="TEST_AI_KEY",
            token_environment_variable="TEST_TOKEN",
            az_executable="az-must-not-run",
        )
        with mock.patch.dict(os.environ, {"TEST_AI_KEY": "k" * 32}, clear=False):
            headers, method, identity = PROBE.build_auth(args)
        self.assertEqual(headers, {"api-key": "k" * 32})
        self.assertEqual(method, "api-key")
        self.assertIsNone(identity)

    def test_entra_token_is_fallback_with_identity(self) -> None:
        claims = base64.urlsafe_b64encode(
            json.dumps({"tid": "tenant", "oid": "subject"}).encode()
        ).decode().rstrip("=")
        args = argparse.Namespace(
            api_key_environment_variable="TEST_AI_KEY_ABSENT",
            token_environment_variable="TEST_TOKEN",
            az_executable="az-must-not-run",
        )
        environment = {"TEST_TOKEN": f"h.{claims}.s"}
        with mock.patch.dict(os.environ, environment, clear=False):
            os.environ.pop("TEST_AI_KEY_ABSENT", None)
            headers, method, identity = PROBE.build_auth(args)
        self.assertEqual(headers, {"Authorization": f"Bearer h.{claims}.s"})
        self.assertEqual(method, "entra-bearer")
        self.assertEqual(len(identity), 64)

    def test_non_completion_200_does_not_pass(self) -> None:
        result = {
            "dnsClass": "private",
            "httpStatus": 200,
            "object": None,
            "choiceCount": None,
        }
        self.assertFalse(PROBE.result_satisfies_expectation(result, "private", 200))

    def test_main_writes_sanitized_output(self) -> None:
        result = {
            "dnsClass": "private",
            "httpStatus": 200,
            "object": "chat.completion",
            "choiceCount": 1,
            "passed": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "probe.json"
            argv = [
                "probe_endpoint.py",
                "--endpoint",
                "https://example.services.ai.azure.com/openai/v1/chat/completions",
                "--deployment",
                "example-deployment",
                "--expect-dns",
                "private",
                "--expect-http",
                "200",
                "--output",
                str(output),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                PROBE, "run_probe", return_value=result
            ):
                self.assertEqual(PROBE.main(), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)


if __name__ == "__main__":
    unittest.main()