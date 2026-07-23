"""Validate a public-safe long-running agent evidence matrix."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from typing import Any


EXPECTED_SCENARIO_SHAPES = {
    "research-invocations-python": ("python", "invocations", "research"),
    "research-responses-python": ("python", "responses", "research"),
    "graph-hitl-invocations-python": ("python", "invocations", "graph-hitl"),
    "graph-hitl-responses-python": ("python", "responses", "graph-hitl"),
    "durable-workflow-python": ("python", "responses", "durable-workflow"),
    "steering-python": ("python", "responses", "steering"),
    "research-invocations-dotnet": ("dotnet", "invocations", "research"),
    "research-responses-dotnet": ("dotnet", "responses", "research"),
}
EXPECTED_SCENARIOS = set(EXPECTED_SCENARIO_SHAPES)

FORBIDDEN_KEYS = {
    "access_token",
    "api_key",
    "client_secret",
    "email",
    "endpoint",
    "fqdn",
    "invocation_id",
    "password",
    "private_repo_url",
    "resource_id",
    "response_id",
    "session_id",
    "subscription_id",
    "tenant_id",
    "token",
    "vm",
}

REQUIRED_SCENARIO_FIELDS = {
    "id",
    "runtime",
    "protocol",
    "pattern",
    "status",
    "source_kind",
    "assertions",
    "scope",
}
MATRIX_FIELDS = {
    "schema_version",
    "disclosure",
    "scope",
    "validation_date",
    "raw_evidence_disclosed",
    "scenarios",
    "summary",
}
ASSERTION_FIELDS = {
    ("research", "invocations"): {
        "checkpoint_before_failure",
        "failure_injected",
        "connection_drop_observed",
        "completed",
        "phase_count",
        "recovery_observed",
        "terminal_state",
    },
    ("research", "responses"): {
        "checkpoint_before_failure",
        "failure_injected",
        "connection_drop_observed",
        "completed",
        "phase_count",
        "same_response_resume",
        "output_item_count",
        "resume_evidence",
    },
    ("graph-hitl", "invocations"): {
        "approval_checkpoint",
        "failure_injected",
        "reconnect_observed",
        "approval_resumed",
        "completed",
        "confirmation_observed",
    },
    ("graph-hitl", "responses"): {
        "approval_checkpoint",
        "failure_injected",
        "reconnect_observed",
        "approval_resumed",
        "completed",
        "confirmation_observed",
    },
    ("durable-workflow", "responses"): {
        "persisted_state",
        "completed",
        "round_trip_output",
        "output_stage_count",
    },
    ("steering", "responses"): {
        "different_input",
        "follow_up_queued",
        "first_turn_terminated",
        "second_turn_completed",
        "relevant_answer",
    },
}


def canonical_sha256(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).casefold()
            nested_path = f"{path}.{key}"
            if normalized in FORBIDDEN_KEYS:
                errors.append(f"public evidence contains forbidden field: {nested_path}")
            errors.extend(_forbidden_paths(nested, nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            errors.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return errors


def _require_true(assertions: Mapping[str, Any], names: tuple[str, ...], scenario_id: str) -> list[str]:
    return [
        f"{scenario_id}.assertions.{name} must be true"
        for name in names
        if assertions.get(name) is not True
    ]


def _validate_research(scenario: Mapping[str, Any]) -> list[str]:
    scenario_id = str(scenario["id"])
    assertions = scenario["assertions"]
    errors = _require_true(
        assertions,
        ("checkpoint_before_failure", "failure_injected", "connection_drop_observed", "completed"),
        scenario_id,
    )
    if assertions.get("phase_count") != 18:
        errors.append(f"{scenario_id}.assertions.phase_count must equal 18")

    protocol = scenario.get("protocol")
    if protocol == "invocations":
        errors.extend(_require_true(assertions, ("recovery_observed",), scenario_id))
        if assertions.get("terminal_state") != "run_completion":
            errors.append(f"{scenario_id}.assertions.terminal_state must be run_completion")
    elif protocol == "responses":
        errors.extend(_require_true(assertions, ("same_response_resume",), scenario_id))
        if assertions.get("output_item_count") != 18:
            errors.append(f"{scenario_id}.assertions.output_item_count must equal 18")
        if assertions.get("resume_evidence") not in {
            "protocol-recovery-marker",
            "same-response-output-continuity",
        }:
            errors.append(f"{scenario_id}.assertions.resume_evidence is not recognized")
    else:
        errors.append(f"{scenario_id}.protocol must be invocations or responses")
    return errors


def _validate_graph_hitl(scenario: Mapping[str, Any]) -> list[str]:
    scenario_id = str(scenario["id"])
    assertions = scenario["assertions"]
    return _require_true(
        assertions,
        (
            "approval_checkpoint",
            "failure_injected",
            "reconnect_observed",
            "approval_resumed",
            "completed",
            "confirmation_observed",
        ),
        scenario_id,
    )


def _validate_workflow(scenario: Mapping[str, Any]) -> list[str]:
    scenario_id = str(scenario["id"])
    assertions = scenario["assertions"]
    errors = _require_true(assertions, ("persisted_state", "completed", "round_trip_output"), scenario_id)
    if assertions.get("output_stage_count", 0) < 3:
        errors.append(f"{scenario_id}.assertions.output_stage_count must be at least 3")
    return errors


def _validate_steering(scenario: Mapping[str, Any]) -> list[str]:
    scenario_id = str(scenario["id"])
    assertions = scenario["assertions"]
    return _require_true(
        assertions,
        (
            "different_input",
            "follow_up_queued",
            "first_turn_terminated",
            "second_turn_completed",
            "relevant_answer",
        ),
        scenario_id,
    )


def _validate_scenario(scenario: Mapping[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_SCENARIO_FIELDS - set(scenario))
    if missing:
        return [f"scenario {index} missing fields: {', '.join(missing)}"]

    scenario_id = str(scenario["id"])
    unexpected = sorted(set(scenario) - REQUIRED_SCENARIO_FIELDS)
    if unexpected:
        errors.append(f"{scenario_id} has unexpected fields: {', '.join(unexpected)}")
    assertions = scenario.get("assertions")
    if not isinstance(assertions, Mapping):
        return [f"{scenario_id}.assertions must be an object"]
    if scenario.get("status") != "passed":
        errors.append(f"{scenario_id}.status must be passed")
    if scenario.get("source_kind") != "sanitized-authenticated-run":
        errors.append(f"{scenario_id}.source_kind must be sanitized-authenticated-run")
    if scenario.get("scope") != "main-documented-scenario":
        errors.append(f"{scenario_id}.scope must be main-documented-scenario")

    expected_shape = EXPECTED_SCENARIO_SHAPES.get(scenario_id)
    actual_shape = (scenario.get("runtime"), scenario.get("protocol"), scenario.get("pattern"))
    if expected_shape is not None and actual_shape != expected_shape:
        errors.append(f"{scenario_id} shape must be {expected_shape}, got {actual_shape}")

    expected_assertions = ASSERTION_FIELDS.get((str(scenario.get("pattern")), str(scenario.get("protocol"))))
    if expected_assertions is not None and set(assertions) != expected_assertions:
        missing_assertions = sorted(expected_assertions - set(assertions))
        extra_assertions = sorted(set(assertions) - expected_assertions)
        if missing_assertions:
            errors.append(f"{scenario_id}.assertions missing fields: {', '.join(missing_assertions)}")
        if extra_assertions:
            errors.append(f"{scenario_id}.assertions has unexpected fields: {', '.join(extra_assertions)}")

    pattern = scenario.get("pattern")
    if pattern == "research":
        errors.extend(_validate_research(scenario))
    elif pattern == "graph-hitl":
        errors.extend(_validate_graph_hitl(scenario))
    elif pattern == "durable-workflow":
        errors.extend(_validate_workflow(scenario))
    elif pattern == "steering":
        errors.extend(_validate_steering(scenario))
    else:
        errors.append(f"{scenario_id}.pattern is not recognized")
    return errors


def validate_matrix(matrix: Mapping[str, Any]) -> list[str]:
    """Return all deterministic validation errors for an evidence matrix."""

    errors = _forbidden_paths(matrix)
    unexpected_matrix_fields = sorted(set(matrix) - MATRIX_FIELDS)
    if unexpected_matrix_fields:
        errors.append(f"matrix has unexpected fields: {', '.join(unexpected_matrix_fields)}")
    if matrix.get("schema_version") != 1:
        errors.append("matrix.schema_version must equal 1")
    if matrix.get("disclosure") != "public-sanitized-attestation":
        errors.append("matrix.disclosure must be public-sanitized-attestation")
    if matrix.get("scope") != "eight-main-documented-scenarios":
        errors.append("matrix.scope must be eight-main-documented-scenarios")
    if matrix.get("raw_evidence_disclosed") is not False:
        errors.append("matrix.raw_evidence_disclosed must be false")
    try:
        date.fromisoformat(str(matrix.get("validation_date")))
    except ValueError:
        errors.append("matrix.validation_date must be an ISO date")

    scenarios = matrix.get("scenarios")
    if not isinstance(scenarios, list):
        errors.append("matrix.scenarios must be a list")
        return errors
    if len(scenarios) != len(EXPECTED_SCENARIOS):
        errors.append(f"matrix.scenarios must contain exactly {len(EXPECTED_SCENARIOS)} entries")

    ids: list[str] = []
    for index, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, Mapping):
            errors.append(f"scenario {index} must be an object")
            continue
        ids.append(str(scenario.get("id", "")))
        errors.extend(_validate_scenario(scenario, index))

    if len(ids) != len(set(ids)):
        errors.append("scenario IDs must be unique")
    missing_ids = sorted(EXPECTED_SCENARIOS - set(ids))
    unexpected_ids = sorted(set(ids) - EXPECTED_SCENARIOS)
    if missing_ids:
        errors.append(f"missing scenario IDs: {', '.join(missing_ids)}")
    if unexpected_ids:
        errors.append(f"unexpected scenario IDs: {', '.join(unexpected_ids)}")

    passed = sum(scenario.get("status") == "passed" for scenario in scenarios if isinstance(scenario, Mapping))
    summary = matrix.get("summary")
    expected_summary = {"passed": passed, "total": len(scenarios), "all_main_scenarios_passed": passed == len(scenarios)}
    if summary != expected_summary:
        errors.append(f"matrix.summary must equal {expected_summary}")
    return errors
