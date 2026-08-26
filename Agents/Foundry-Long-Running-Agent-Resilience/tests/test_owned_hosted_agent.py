from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "hosted-agent" / "src" / "lra-evidence-agent" / "contract.py"
)
sys.path.insert(0, str(CONTRACT_PATH.parent))
CLIENT_PATH = ROOT / "hosted-agent" / "client.py"
SPEC = importlib.util.spec_from_file_location("lra_owned_contract", CONTRACT_PATH)
assert SPEC and SPEC.loader
CONTRACT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTRACT
SPEC.loader.exec_module(CONTRACT)
CLIENT_SPEC = importlib.util.spec_from_file_location("lra_owned_client", CLIENT_PATH)
assert CLIENT_SPEC and CLIENT_SPEC.loader
CLIENT = importlib.util.module_from_spec(CLIENT_SPEC)
sys.modules[CLIENT_SPEC.name] = CLIENT
CLIENT_SPEC.loader.exec_module(CLIENT)
sys.modules["client"] = CLIENT
sys.modules["contract"] = CONTRACT
RUNNER_PATH = ROOT / "hosted-agent" / "run_local_recovery.py"
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "lra_owned_runner",
    RUNNER_PATH,
)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = RUNNER
RUNNER_SPEC.loader.exec_module(RUNNER)


def response_with(records: list[dict], status: str = "completed") -> dict:
    return {
        "status": status,
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(record, sort_keys=True),
                    }
                ],
            }
            for record in records
        ],
    }


class OwnedHostedAgentContractTests(unittest.TestCase):
    def test_plain_text_defaults_to_safe_rerun(self):
        spec = CONTRACT.parse_work_spec("hello")
        self.assertTrue(spec.work_id.startswith("text-"))
        self.assertIsNone(spec.crash_after_stage)

    def test_strict_json_input_rejects_unknown_fields(self):
        with self.assertRaisesRegex(CONTRACT.ContractError, "unknown input fields"):
            CONTRACT.parse_work_spec(
                json.dumps({"work_id": "w1", "payload": "x", "fake": True})
            )

    def test_crash_stage_is_bounded(self):
        with self.assertRaisesRegex(CONTRACT.ContractError, "crash_after_stage"):
            CONTRACT.parse_work_spec(
                json.dumps(
                    {
                        "work_id": "w1",
                        "payload": "x",
                        "crash_after_stage": len(CONTRACT.STAGES),
                    }
                )
            )

    def test_complete_recovered_response_passes(self):
        spec = CONTRACT.parse_work_spec(
            json.dumps(
                {
                    "work_id": "w1",
                    "payload": "x",
                    "crash_after_stage": 1,
                }
            )
        )
        records = [
            CONTRACT.build_stage_record(
                spec,
                index,
                "process-a" if index <= 1 else "process-b",
                index > 1,
            )
            for index in range(len(CONTRACT.STAGES))
        ]
        result = CONTRACT.validate_terminal_response(
            response_with(records),
            expected_work_id="w1",
            expect_recovery=True,
        )
        self.assertEqual(result["stage_indexes"], list(range(len(CONTRACT.STAGES))))
        self.assertEqual(result["process_instance_ids"], ["process-a", "process-b"])

    def test_tampered_translation_fails_hash_validation(self):
        spec = CONTRACT.parse_work_spec(
            json.dumps(
                {
                    "work_id": "translation-work",
                    "payload": "translate",
                    "crash_after_stage": 3,
                    "workload": "translator_batch",
                }
            )
        )
        records = [
            CONTRACT.build_stage_record(
                spec,
                index,
                "process-a" if index <= 3 else "process-b",
                index > 3,
                result_text=f"translation {index}",
            )
            for index in range(len(CONTRACT.SOURCE_SECTIONS))
        ]
        records[6]["translated_text"] = "tampered translation"
        with self.assertRaisesRegex(
            CONTRACT.ContractError,
            "translation result hashes",
        ):
            CONTRACT.validate_terminal_response(
                response_with(records),
                expected_work_id="translation-work",
                expect_recovery=True,
                expected_workload="translator_batch",
            )

    def test_gap_or_duplicate_fails(self):
        spec = CONTRACT.parse_work_spec(
            json.dumps({"work_id": "w1", "payload": "x"})
        )
        indexes = list(range(len(CONTRACT.STAGES)))
        indexes[2] = 1
        records = [
            CONTRACT.build_stage_record(spec, index, "process-a", False)
            for index in indexes
        ]
        with self.assertRaisesRegex(CONTRACT.ContractError, "stage indexes"):
            CONTRACT.validate_terminal_response(
                response_with(records),
                expected_work_id="w1",
                expect_recovery=False,
            )

    def test_one_process_cannot_claim_recovery(self):
        spec = CONTRACT.parse_work_spec(
            json.dumps({"work_id": "w1", "payload": "x"})
        )
        records = [
            CONTRACT.build_stage_record(spec, index, "process-a", False)
            for index in range(len(CONTRACT.STAGES))
        ]
        with self.assertRaisesRegex(CONTRACT.ContractError, "two process instances"):
            CONTRACT.validate_terminal_response(
                response_with(records),
                expected_work_id="w1",
                expect_recovery=True,
            )

    def test_owned_contract_checkpoints_are_distinct(self):
        self.assertGreater(len(CONTRACT.STAGES), 1)
        self.assertEqual(len(set(CONTRACT.STAGES)), len(CONTRACT.STAGES))

    def test_public_acceptance_hashes_process_identity(self):
        public = CLIENT.public_acceptance(
            {
                "status": "completed",
                "work_id": "w1",
                "payload_sha256": "a" * 64,
                "entry_modes": ["fresh", "recovered"],
                "recovery_proven": True,
                "workload": "checkpoint_contract",
                "stage_names": ["one", "two"],
                "stage_result_sha256": ["b" * 64, "c" * 64],
                "process_instance_ids": ["private-process-a", "private-process-b"],
            }
        )
        self.assertNotIn("process_instance_ids", public)
        self.assertEqual(public["process_instance_count"], 2)
        self.assertEqual(len(public["process_instance_sha256"]), 2)

    def test_observer_modes_are_mutually_exclusive(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                CLIENT.parse_args(["--resume", "--create-only"])

    def test_foundry_log_envelope_is_unwrapped_before_hashing(self):
        envelope = {
            "timestamp": "2026-08-26T09:09:54.039+00:00",
            "stream": "stderr",
            "message": (
                "2026-08-26 INFO LRA_ENTRY "
                "at_utc=2026-08-26T09:09:54.039+00:00 "
                "response_id=response-1 work_id=w1 mode=recovered "
                "start=4 instance=instance-1"
            ),
        }
        exit_envelope = {
            "timestamp": "2026-08-26T09:09:55.000+00:00",
            "stream": "stderr",
            "message": (
                "LRA_INJECTED_PROCESS_LOSS "
                "at_utc=2026-08-26T09:09:55.000+00:00 "
                "response_id=response-1 work_id=w1 "
                "after_stage=3 exit_code=86"
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "monitor.log"
            path.write_text(
                "data: " + json.dumps(envelope) + "\n"
                "data: " + json.dumps(exit_envelope) + "\n",
                encoding="utf-8",
            )
            events = RUNNER.sanitize_agent_log(path)
        self.assertEqual(events[0]["at_utc"], "2026-08-26T09:09:54.039+00:00")
        self.assertEqual(
            events[0]["process_instance_sha256"],
            CLIENT.sha256_text("instance-1"),
        )
        self.assertEqual(events[1]["exit_code"], 86)
        self.assertEqual(events[1]["after_checkpoint"], "plan_work")

    def test_translation_log_uses_translation_checkpoint_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "agent.log"
            path.write_text(
                "LRA_ENTRY at_utc=2026-08-26T10:23:11.069+00:00 "
                "mode=recovered start=4\n",
                encoding="utf-8",
            )
            events = RUNNER.sanitize_agent_log(path, "translator_batch")
        self.assertEqual(
            events[0]["resume_from_checkpoint"],
            "translation_section_05",
        )

    def test_hosted_endpoint_keeps_api_version_on_item_reads(self):
        endpoint = (
            "https://example.invalid/agents/a/endpoint/protocols/openai/"
            "responses?api-" "version=v1"
        )
        self.assertEqual(
            CLIENT.response_item_url(endpoint, "response id"),
            (
                "https://example.invalid/agents/a/endpoint/protocols/openai/"
                "responses/response%20id?api-" "version=v1"
            ),
        )

    def test_azure_token_is_sent_on_the_wire(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"status":"ok"}'

        captured = {}

        def fake_urlopen(request, timeout):
            captured["authorization"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            return FakeResponse()

        with patch.object(CLIENT.urllib.request, "urlopen", fake_urlopen):
            result = CLIENT.request_json(
                "GET",
                "https://example.invalid/responses/r1",
                None,
                "abc123",
            )
        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(captured["authorization"], "Bearer abc123")
        self.assertEqual(captured["timeout"], 30)

    def test_resume_uses_remaining_absolute_deadline(self):
        remaining = CLIENT.remaining_deadline_seconds(
            "2026-08-26T10:01:00+00:00",
            now=datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(remaining, 60)
        with self.assertRaisesRegex(TimeoutError, "deadline has expired"):
            CLIENT.remaining_deadline_seconds(
                "2026-08-26T09:59:59+00:00",
                now=datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
