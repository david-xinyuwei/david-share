from __future__ import annotations

import copy
import unittest

from lra_resilience.evidence import canonical_sha256, validate_matrix


def valid_matrix() -> dict:
    common = {
        "checkpoint_before_failure": True,
        "failure_injected": True,
        "connection_drop_observed": True,
        "completed": True,
        "phase_count": 18,
    }
    scenarios = [
        {
            "id": "research-invocations-python",
            "runtime": "python",
            "protocol": "invocations",
            "pattern": "research",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {**common, "recovery_observed": True, "terminal_state": "run_completion"},
        },
        {
            "id": "research-responses-python",
            "runtime": "python",
            "protocol": "responses",
            "pattern": "research",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {
                **common,
                "same_response_resume": True,
                "output_item_count": 18,
                "resume_evidence": "protocol-recovery-marker",
            },
        },
        {
            "id": "graph-hitl-invocations-python",
            "runtime": "python",
            "protocol": "invocations",
            "pattern": "graph-hitl",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {
                "approval_checkpoint": True,
                "failure_injected": True,
                "reconnect_observed": True,
                "approval_resumed": True,
                "completed": True,
                "confirmation_observed": True,
            },
        },
        {
            "id": "graph-hitl-responses-python",
            "runtime": "python",
            "protocol": "responses",
            "pattern": "graph-hitl",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {
                "approval_checkpoint": True,
                "failure_injected": True,
                "reconnect_observed": True,
                "approval_resumed": True,
                "completed": True,
                "confirmation_observed": True,
            },
        },
        {
            "id": "durable-workflow-python",
            "runtime": "python",
            "protocol": "responses",
            "pattern": "durable-workflow",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {
                "persisted_state": True,
                "completed": True,
                "round_trip_output": True,
                "output_stage_count": 3,
            },
        },
        {
            "id": "steering-python",
            "runtime": "python",
            "protocol": "responses",
            "pattern": "steering",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {
                "different_input": True,
                "follow_up_queued": True,
                "first_turn_terminated": True,
                "second_turn_completed": True,
                "relevant_answer": True,
            },
        },
        {
            "id": "research-invocations-dotnet",
            "runtime": "dotnet",
            "protocol": "invocations",
            "pattern": "research",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {**common, "recovery_observed": True, "terminal_state": "run_completion"},
        },
        {
            "id": "research-responses-dotnet",
            "runtime": "dotnet",
            "protocol": "responses",
            "pattern": "research",
            "status": "passed",
            "source_kind": "sanitized-authenticated-run",
            "assertions": {
                **common,
                "same_response_resume": True,
                "output_item_count": 18,
                "resume_evidence": "same-response-output-continuity",
            },
        },
    ]
    for scenario in scenarios:
        scenario["scope"] = "main-documented-scenario"
    return {
        "schema_version": 1,
        "disclosure": "public-sanitized-attestation",
        "scope": "eight-main-documented-scenarios",
        "validation_date": "2026-07-23",
        "raw_evidence_disclosed": False,
        "scenarios": scenarios,
        "summary": {"passed": 8, "total": 8, "all_main_scenarios_passed": True},
    }


class EvidenceTests(unittest.TestCase):
    def test_valid_matrix_passes(self) -> None:
        self.assertEqual(validate_matrix(valid_matrix()), [])

    def test_missing_recovery_fails_closed(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["assertions"]["recovery_observed"] = False
        self.assertIn(
            "research-invocations-python.assertions.recovery_observed must be true",
            validate_matrix(matrix),
        )

    def test_nested_sensitive_field_is_rejected(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["metadata"] = {"session_id": "not-public"}
        self.assertIn(
            "public evidence contains forbidden field: $.scenarios[0].metadata.session_id",
            validate_matrix(matrix),
        )

    def test_summary_must_be_recomputed(self) -> None:
        matrix = valid_matrix()
        matrix["summary"]["passed"] = 7
        self.assertTrue(any(error.startswith("matrix.summary must equal") for error in validate_matrix(matrix)))

    def test_scenario_shape_is_bound_to_id(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["runtime"] = "dotnet"
        self.assertTrue(any("shape must be" in error for error in validate_matrix(matrix)))

    def test_unexpected_scenario_field_is_rejected(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["notes"] = "not allowed"
        self.assertTrue(any("unexpected fields: notes" in error for error in validate_matrix(matrix)))

    def test_unexpected_assertion_field_is_rejected(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["assertions"]["raw_payload"] = "not allowed"
        self.assertTrue(any("unexpected fields: raw_payload" in error for error in validate_matrix(matrix)))

    def test_canonical_digest_is_order_independent(self) -> None:
        matrix = valid_matrix()
        reordered = copy.deepcopy(matrix)
        reordered["summary"] = {
            "total": 8,
            "all_main_scenarios_passed": True,
            "passed": 8,
        }
        self.assertEqual(canonical_sha256(matrix), canonical_sha256(reordered))


if __name__ == "__main__":
    unittest.main()