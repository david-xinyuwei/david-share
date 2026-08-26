from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

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
        records = [
            CONTRACT.build_stage_record(spec, index, "process-a", False)
            for index in (0, 1, 1, 3, 4)
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


if __name__ == "__main__":
    unittest.main()
