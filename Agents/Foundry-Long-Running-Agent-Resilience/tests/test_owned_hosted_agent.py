from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "hosted-agent" / "src" / "lra-evidence-agent" / "contract.py"
)
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

    def test_owned_contract_has_eighteen_distinct_stages(self):
        self.assertEqual(len(CONTRACT.STAGES), 18)
        self.assertEqual(len(set(CONTRACT.STAGES)), 18)

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
