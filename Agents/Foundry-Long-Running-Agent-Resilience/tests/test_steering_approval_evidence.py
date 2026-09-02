"""Fail-closed tests for the steering and approval acceptance rules and trace renderers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


STEERING = load("hosted-agent-steering/run_steering_recovery.py", "lra_steering_runner")
APPROVAL = load("hosted-agent-approval/run_approval_recovery.py", "lra_approval_runner")
RENDER_STEERING = load("scripts/render_steering_trace.py", "lra_render_steering")
RENDER_APPROVAL = load("scripts/render_approval_trace.py", "lra_render_approval")

P1 = hashlib.sha256(b"process-1").hexdigest()
P2 = hashlib.sha256(b"process-2").hexdigest()
TASK = hashlib.sha256(b"task").hexdigest()


def steering_inputs(**overrides):
    base = dict(
        fresh=list(range(10)),
        recovered=[10, 11, 12, 13],
        crash_after_stage=9,
        fresh_process=P1,
        recovered_process=P2,
        original_status="completed",
        steered_entry={"entry_mode": "steered", "process_sha256": P2},
        replacement_indexes=list(range(30)),
        replacement_targets=["zh-Hant"] * 30,
        replacement_target="zh-Hant",
        replacement_terminal="response.completed",
        texts=["译文"] * 44,
    )
    base.update(overrides)
    return base


def approval_inputs(**overrides):
    sample_hashes = [hashlib.sha256(f"s{i}".encode()).hexdigest() for i in range(10)]
    results = [
        {
            "stage_index": i,
            "stage_result_sha256": sample_hashes[i] if i < 10 else hashlib.sha256(f"r{i}".encode()).hexdigest(),
            "process_sha256": P1 if i < 10 else P2,
            "translated_text": "译文",
        }
        for i in range(30)
    ]
    base = dict(
        process_a=P1,
        process_b=P2,
        task_sha=TASK,
        output={"status": "resolved", "outcome": "completed", "task_id_sha256": TASK},
        results=results,
        sample_hashes=sample_hashes,
    )
    base.update(overrides)
    return base


class SteeringAcceptanceTests(unittest.TestCase):
    def test_reference_run_passes(self):
        self.assertTrue(all(STEERING.steering_checks(**steering_inputs()).values()))

    def test_recovery_on_the_same_process_fails(self):
        checks = STEERING.steering_checks(**steering_inputs(recovered_process=P1))
        self.assertFalse(checks["recovered_on_a_different_process"])
        self.assertFalse(checks["steered_entry_on_replacement_process"])

    def test_resume_gap_fails(self):
        checks = STEERING.steering_checks(**steering_inputs(recovered=[11, 12]))
        self.assertFalse(checks["resume_after_last_checkpoint"])

    def test_replacement_that_does_not_restart_at_section_1_fails(self):
        checks = STEERING.steering_checks(**steering_inputs(replacement_indexes=list(range(10, 30))))
        self.assertFalse(checks["replacement_starts_at_section_1"])
        self.assertFalse(checks["replacement_completed_all_sections"])

    def test_steered_turn_on_the_dead_process_fails(self):
        checks = STEERING.steering_checks(
            **steering_inputs(steered_entry={"entry_mode": "steered", "process_sha256": P1})
        )
        self.assertFalse(checks["steered_entry_on_replacement_process"])

    def test_wrong_language_or_unfinished_original_fails(self):
        checks = STEERING.steering_checks(**steering_inputs(replacement_targets=["zh-Hans"] * 30))
        self.assertFalse(checks["replacement_target_everywhere"])
        checks = STEERING.steering_checks(**steering_inputs(original_status="in_progress"))
        self.assertFalse(checks["original_response_completed"])


class ApprovalAcceptanceTests(unittest.TestCase):
    def test_reference_run_passes(self):
        self.assertTrue(all(APPROVAL.approval_checks(**approval_inputs()).values()))

    def test_sample_rewritten_after_recovery_fails(self):
        inputs = approval_inputs()
        inputs["results"][0]["stage_result_sha256"] = "0" * 64
        self.assertFalse(APPROVAL.approval_checks(**inputs)["sample_result_hashes_unchanged"])

    def test_remaining_sections_on_the_dead_process_fail(self):
        inputs = approval_inputs()
        for item in inputs["results"][10:]:
            item["process_sha256"] = P1
        self.assertFalse(APPROVAL.approval_checks(**inputs)["remaining_translated_on_process_b"])

    def test_missing_or_duplicate_section_fails(self):
        inputs = approval_inputs()
        inputs["results"].pop(15)
        self.assertFalse(APPROVAL.approval_checks(**inputs)["all_sections_present_once"])
        inputs = approval_inputs()
        inputs["results"].append(dict(inputs["results"][-1]))
        self.assertFalse(APPROVAL.approval_checks(**inputs)["all_sections_present_once"])

    def test_task_identity_or_outcome_change_fails(self):
        checks = APPROVAL.approval_checks(**approval_inputs(output={"status": "resolved", "outcome": "completed", "task_id_sha256": "1" * 64}))
        self.assertFalse(checks["task_identity_unchanged"])
        checks = APPROVAL.approval_checks(**approval_inputs(output={"status": "resolved", "outcome": "stopped", "task_id_sha256": TASK}))
        self.assertFalse(checks["resolved_as_completed"])
        self.assertFalse(APPROVAL.approval_checks(**approval_inputs(process_b=P1))["process_replaced"])


class CommittedEvidenceTests(unittest.TestCase):
    """The committed reports must satisfy the same rules the runners enforce, and the
    committed traces must be exactly what the renderers produce from them."""

    def read(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_committed_steering_report_passes_and_renders(self):
        report = self.read("evidence/owned-steering-live.json")
        self.assertTrue(report["passed"])
        self.assertTrue(all(value for key, value in report["acceptance"].items() if isinstance(value, bool)))
        self.assertEqual(report["responses"]["B"]["sections"], 30)
        self.assertEqual(report["acceptance"]["process_instance_count"], 2)
        rendered = RENDER_STEERING.render(report)
        committed = (ROOT / "evidence/owned-steering-live-trace.txt").read_text(encoding="utf-8")
        self.assertEqual(rendered.replace("\r\n", "\n"), committed.replace("\r\n", "\n"))

    def test_committed_approval_reports_pass_and_render(self):
        for stem in ("owned-approval-local", "owned-approval-live"):
            report = self.read(f"evidence/{stem}.json")
            self.assertTrue(report["passed"], stem)
            self.assertTrue(all(value for key, value in report["acceptance"].items() if isinstance(value, bool)), stem)
            self.assertEqual(report["acceptance"]["total_sections"], 30, stem)
            rendered = RENDER_APPROVAL.render(report)
            committed = (ROOT / f"evidence/{stem}-trace.txt").read_text(encoding="utf-8")
            self.assertEqual(rendered.replace("\r\n", "\n"), committed.replace("\r\n", "\n"), stem)

    def test_steer_then_crash_boundary_is_not_claimed(self):
        boundary = self.read("evidence/steering-order-boundary.json")
        self.assertEqual(boundary["status"], "NOT_VERIFIED")
        self.assertIn("failing closed", boundary["observed_message"])
        self.assertTrue(boundary["sdk_versions_observed"])


if __name__ == "__main__":
    unittest.main()
