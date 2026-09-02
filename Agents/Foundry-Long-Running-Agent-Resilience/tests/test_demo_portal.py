"""Fail-closed orchestration and HTTP-surface tests for demo-portal/."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load_portal() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lra_demo_portal", ROOT / "demo-portal/app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PORTAL = load_portal()
PROCESS_A_ID = "host-a"
PROCESS_B_ID = "host-b"
PROCESS_A = hashlib.sha256(PROCESS_A_ID.encode()).hexdigest()
PROCESS_B = hashlib.sha256(PROCESS_B_ID.encode()).hexdigest()
TASK_SHA = "d" * 64


def json_item(payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}


def steering_entry(entry_mode: str, process_sha: str, target: str, resume_from: int = 0) -> dict[str, Any]:
    return json_item(
        {
            "kind": "lre_steering_entry",
            "entry_mode": entry_mode,
            "process_sha256": process_sha,
            "target": target,
            "resume_from": resume_from,
        }
    )


def stage_item(index: int, total: int, entry_mode: str, process_id: str, target: str) -> dict[str, Any]:
    return json_item(
        {
            "kind": "lra_stage",
            "workload": "translator_batch",
            "stage_index": index,
            "stage_name": f"translation_section_{index + 1:02d}",
            "stage_count": total,
            "entry_mode": entry_mode,
            "process_instance_id": process_id,
            "target": target,
            "source_text": f"source {index}",
            "translated_text": f"translated {index} {target}",
        }
    )


def item_done(index: int, item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "response.output_item.done", "output_index": index, "item": item}


async def collect(stream: Any) -> list[dict[str, Any]]:
    events = []
    async for chunk in stream:
        assert chunk.startswith("data: ") and chunk.endswith("\n\n")
        events.append(json.loads(chunk[6:]))
    return events


def section(index: int, total: int, process: str, batch: str) -> dict[str, Any]:
    text = f"translated {index}"
    return {
        "stage_index": index,
        "stage_name": f"translation_section_{index + 1:02d}",
        "source_text": f"source {index}",
        "translated_text": text,
        "stage_result_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "entry_mode": "fresh" if batch == "sample" else "resumed",
        "process_sha256": process,
        "batch": batch,
        "total_sections": total,
    }


class PortalSurfaceTests(unittest.TestCase):
    def test_loopback_mode_and_static_surface(self):
        with TestClient(PORTAL.app) as client:
            status = client.get("/api/auth/status")
            self.assertEqual(status.status_code, 200)
            self.assertFalse(status.json()["auth_required"])
            self.assertTrue(status.json()["authenticated"])
            self.assertEqual(client.get("/healthz").json()["status"], "ok")
            agents = client.get("/api/agents")
            self.assertEqual(agents.status_code, 200)
            self.assertFalse(agents.json()["configured"])
            self.assertIn("Four kinds of interruption", client.get("/").text)
            self.assertIn("function recoveryEvent", client.get("/static/app.js").text)
            self.assertEqual(client.get("/assets/official-lease-recovery-model.png").status_code, 200)

    def test_validator_rejects_damaged_evidence(self):
        with TestClient(PORTAL.app) as client:
            payload = client.post("/api/validator-check").json()
        self.assertTrue(payload["all_behaved"])
        self.assertEqual(len(payload["cases"]), 8)
        rejected = {item["id"] for item in payload["cases"] if item["rejected"]}
        self.assertIn("missing-checkpoint", rejected)
        self.assertIn("duplicate-checkpoint", rejected)
        self.assertIn("no-handoff", rejected)

    def test_url_builder_encodes_query_parameters(self):
        with patch.object(PORTAL.settings, "project_endpoint", "https://foundry.test/project"):
            url = PORTAL._approval_url("approval", "session-1", "invoke-1")
        self.assertTrue(url.startswith("https://foundry.test/project/agents/approval/"))
        self.assertIn("agent_session_id=session-1", url)
        self.assertIn("invocations/invoke-1?", url)


class CheckpointAcceptanceTests(unittest.TestCase):
    @staticmethod
    def lanes(first: list[int], second: list[int]) -> list[dict[str, Any]]:
        def items(indexes: list[int]) -> list[dict[str, Any]]:
            return [
                {"index": index, "name": f"translation_section_{index + 1:02d}", "source": "source", "text": "translated"}
                for index in indexes
            ]

        return [
            {"process_sha256": PROCESS_A, "entry_mode": "fresh", "stages": items(first)},
            {"process_sha256": PROCESS_B, "entry_mode": "recovered", "stages": items(second)},
        ]

    def test_twelve_section_repository_agent_contract_passes(self):
        result = PORTAL._lra_acceptance(self.lanes(list(range(4)), list(range(4, 12))), 12, "completed", "crash", True)
        self.assertTrue(result["passed"])
        self.assertTrue(result["handed_off_to_new_process"])

    def test_gap_duplicate_and_no_handoff_fail(self):
        gap = PORTAL._lra_acceptance(self.lanes(list(range(4)), list(range(5, 12))), 12, "completed", "crash", True)
        duplicate = PORTAL._lra_acceptance(self.lanes(list(range(5)), list(range(4, 12))), 12, "completed", "crash", True)
        single = PORTAL._lra_acceptance(self.lanes(list(range(12)), []), 12, "completed", "crash", True)
        self.assertFalse(gap["passed"])
        self.assertFalse(duplicate["passed"])
        self.assertFalse(single["passed"])


class SteeringOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, *, resume_at: int = 3, recovered_id: str = PROCESS_B_ID) -> tuple[list[dict[str, Any]], list[str]]:
        total = 6
        methods = []
        recovered_sha = hashlib.sha256(recovered_id.encode()).hexdigest()

        async def fake_stream(_request, method, _url, payload, *_args):
            methods.append(method)
            if method == "POST" and payload and "previous_response_id" not in payload:
                yield {"type": "response.created", "response": {"id": "response-a"}}
                yield item_done(0, steering_entry("fresh", PROCESS_A, "zh-Hans"))
                for index in range(3):
                    yield item_done(index + 1, stage_item(index, total, "fresh", PROCESS_A_ID, "zh-Hans"))
                return
            if method == "GET":
                yield item_done(0, steering_entry("fresh", PROCESS_A, "zh-Hans"))
                for index in range(3):
                    yield item_done(index + 1, stage_item(index, total, "fresh", PROCESS_A_ID, "zh-Hans"))
                yield item_done(4, steering_entry("recovered", recovered_sha, "zh-Hans", resume_from=resume_at))
                for offset, index in enumerate(range(resume_at, min(total, resume_at + 2))):
                    yield item_done(5 + offset, stage_item(index, total, "recovered", recovered_id, "zh-Hans"))
                return
            assert payload and payload["previous_response_id"] == "response-a"
            yield {"type": "response.created", "response": {"id": "response-b"}}
            yield item_done(0, steering_entry("steered", recovered_sha, "zh-Hant"))
            for index in range(total):
                yield item_done(index + 1, stage_item(index, total, "steered", recovered_id, "zh-Hant"))
            yield {"type": "response.completed", "response": {"status": "completed"}}

        body = PORTAL.SteeringDemoRequest(
            original_target="zh-Hans",
            replacement_target="zh-Hant",
            steer_after_sections=2,
            crash_after_stage=2,
        )
        with (
            patch.object(PORTAL.settings, "project_endpoint", "https://foundry.test/project"),
            patch.object(PORTAL, "_get_agent", AsyncMock(return_value={})),
            patch.object(PORTAL, "_runtime_contract", return_value={"version": "test"}),
            patch.object(PORTAL, "_lra_stream_events", fake_stream),
            patch.object(PORTAL, "_response_json", AsyncMock(return_value={"status": "completed"})),
        ):
            events = await collect(PORTAL._steering_stream(object(), body))
        return events, methods

    async def test_dynamic_stage_count_passes(self):
        events, methods = await self.run_case()
        result = [item["result"] for item in events if item["kind"] == "done"][0]
        self.assertEqual(methods, ["POST", "GET", "POST"])
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["stage_count"], 6)
        self.assertEqual(result["replacement_sections"], 6)
        self.assertTrue(result["process_replaced"])
        self.assertTrue(result["steered_on_replacement"])

    async def test_resume_gap_and_same_process_fail_closed(self):
        gap, _ = await self.run_case(resume_at=4)
        same, _ = await self.run_case(recovered_id=PROCESS_A_ID)
        self.assertEqual(gap[-1]["kind"], "error")
        self.assertEqual(same[-1]["kind"], "error")
        self.assertFalse(any(item["kind"] == "done" for item in gap))
        self.assertFalse(any(item["kind"] == "done" for item in same))


class ApprovalOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def phase_one(self) -> list[dict[str, Any]]:
        total = 8
        sample = [section(index, total, PROCESS_A, "sample") for index in range(3)]

        async def fake_turn(_request, _agent, _session, payload):
            self.assertEqual(payload["action"], "start")
            yield {
                "status": "completed",
                "output": {
                    "status": "awaiting_review",
                    "process_sha256": PROCESS_A,
                    "task_id_sha256": TASK_SHA,
                },
                "progress": {"total_sections": total, "results": sample},
            }

        async def fake_post(_request, _agent, _session, payload):
            if payload["action"] == "inject_process_loss":
                raise httpx.ReadError("process lost")
            return httpx.Response(200, json={"process_sha256": PROCESS_B}, request=httpx.Request("POST", "https://foundry.test"))

        body = PORTAL.ApprovalDemoRequest(target="zh-Hans", sample_size=3, auto_approve=False)
        with (
            patch.object(PORTAL.settings, "project_endpoint", "https://foundry.test/project"),
            patch.object(PORTAL, "_get_agent", AsyncMock(return_value={})),
            patch.object(PORTAL, "_runtime_contract", return_value={"version": "test"}),
            patch.object(PORTAL, "_approval_turn", fake_turn),
            patch.object(PORTAL, "_approval_post", fake_post),
        ):
            return await collect(PORTAL._approval_stream(object(), body))

    async def phase_two(self, handoff: dict[str, Any], *, tamper: bool = False) -> list[dict[str, Any]]:
        total = 8
        results = [section(index, total, PROCESS_A if index < 3 else PROCESS_B, "sample" if index < 3 else "remaining") for index in range(total)]
        if tamper:
            results[0]["stage_result_sha256"] = "0" * 64

        async def fake_turn(_request, _agent, _session, payload):
            self.assertEqual(payload["action"], "approve_review")
            yield {
                "status": "completed",
                "output": {
                    "status": "resolved",
                    "outcome": "completed",
                    "process_sha256": PROCESS_B,
                    "task_id_sha256": TASK_SHA,
                    "target": "zh-Hans",
                },
                "progress": {"total_sections": total, "results": results},
            }

        body = PORTAL.ApprovalDecisionRequest(
            session_id=handoff["session_id"],
            task_id_sha256=handoff["task_id_sha256"],
            process_a_sha256=handoff["process_a_sha256"],
            sample_hashes=handoff["sample_hashes"],
        )
        with (
            patch.object(PORTAL.settings, "project_endpoint", "https://foundry.test/project"),
            patch.object(PORTAL, "_get_agent", AsyncMock(return_value={})),
            patch.object(PORTAL, "_runtime_contract", return_value={"version": "test"}),
            patch.object(PORTAL, "_approval_turn", fake_turn),
        ):
            return await collect(PORTAL._approval_decision_stream(object(), body))

    async def test_dynamic_total_and_two_phase_approval_pass(self):
        first = await self.phase_one()
        handoff = [item["result"] for item in first if item["kind"] == "done"][0]
        self.assertEqual(handoff["status"], "awaiting_approval")
        self.assertEqual(len(handoff["sample_hashes"]), 3)
        self.assertLess([item["kind"] for item in first].index("process_lost"), [item["kind"] for item in first].index("recovered"))

        second = await self.phase_two(handoff)
        result = [item["result"] for item in second if item["kind"] == "done"][0]
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["total_sections"], 8)
        self.assertEqual(result["remaining_sections"], 5)
        self.assertTrue(result["sample_preserved"])

    async def test_changed_sample_fails_closed(self):
        first = await self.phase_one()
        handoff = [item["result"] for item in first if item["kind"] == "done"][0]
        second = await self.phase_two(handoff, tamper=True)
        self.assertEqual(second[-1]["kind"], "error")
        self.assertFalse(any(item["kind"] == "done" for item in second))


if __name__ == "__main__":
    unittest.main()
