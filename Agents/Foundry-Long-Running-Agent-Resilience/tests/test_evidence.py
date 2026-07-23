from __future__ import annotations

import copy
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from lra_resilience.evidence import build_evidence_schema, canonical_sha256, validate_matrix


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
            "source_kind": "author-attested-sanitized-run",
            "assertions": {**common, "recovery_observed": True, "terminal_state": "run_completion"},
        },
        {
            "id": "research-responses-python",
            "runtime": "python",
            "protocol": "responses",
            "pattern": "research",
            "status": "passed",
            "source_kind": "author-attested-sanitized-run",
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
            "source_kind": "author-attested-sanitized-run",
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
            "source_kind": "author-attested-sanitized-run",
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
            "source_kind": "author-attested-sanitized-run",
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
            "source_kind": "author-attested-sanitized-run",
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
            "source_kind": "author-attested-sanitized-run",
            "assertions": {**common, "recovery_observed": True, "terminal_state": "run_completion"},
        },
        {
            "id": "research-responses-dotnet",
            "runtime": "dotnet",
            "protocol": "responses",
            "pattern": "research",
            "status": "passed",
            "source_kind": "author-attested-sanitized-run",
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
        scenario["source_kind"] = "author-attested-sanitized-run"
        scenario["provenance"] = {
            "attestation_type": "author-attested-sanitized-result",
            "campaign_verified_date": "2026-07-23",
            "private_source_artifact_count": 1,
            "private_source_commitment_sha256": "a" * 64,
        }
    return {
        "schema_version": 2,
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

    def test_provenance_commitment_is_required(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["provenance"].pop("private_source_commitment_sha256")
        self.assertTrue(
            any("provenance missing fields" in error for error in validate_matrix(matrix))
        )

    def test_provenance_commitment_must_be_sha256(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["provenance"]["private_source_commitment_sha256"] = "not-a-digest"
        self.assertTrue(
            any("must be lowercase SHA-256" in error for error in validate_matrix(matrix))
        )

    def test_canonical_digest_is_order_independent(self) -> None:
        matrix = valid_matrix()
        reordered = copy.deepcopy(matrix)
        reordered["summary"] = {
            "total": 8,
            "all_main_scenarios_passed": True,
            "passed": 8,
        }
        self.assertEqual(canonical_sha256(matrix), canonical_sha256(reordered))

    def test_json_schema_rejects_fake_scenario_ids(self) -> None:
        matrix = valid_matrix()
        matrix["scenarios"][0]["id"] = "fake-scenario"
        self.assertTrue(list(Draft202012Validator(build_evidence_schema()).iter_errors(matrix)))

    def test_json_schema_enforces_dates(self) -> None:
        matrix = valid_matrix()
        matrix["validation_date"] = "not-a-date"
        matrix["scenarios"][0]["provenance"]["campaign_verified_date"] = "2026-99-99"
        errors = list(
            Draft202012Validator(
                build_evidence_schema(),
                format_checker=FormatChecker(),
            ).iter_errors(matrix)
        )
        self.assertGreaterEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()