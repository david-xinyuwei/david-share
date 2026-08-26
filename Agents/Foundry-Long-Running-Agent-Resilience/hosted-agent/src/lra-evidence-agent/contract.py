"""Pure contract helpers shared by the LRA Evidence Agent and its client."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 2
STAGES = (
    "accept",
    "validate_input",
    "fingerprint_payload",
    "plan_work",
    "allocate_steps",
    "prepare_context",
    "execute_part_1",
    "execute_part_2",
    "execute_part_3",
    "aggregate_results",
    "verify_order",
    "verify_uniqueness",
    "verify_payload",
    "build_summary",
    "record_metrics",
    "finalize_output",
    "validate_terminal",
    "complete",
)
_WORK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ALLOWED_INPUT_FIELDS = {
    "work_id",
    "payload",
    "crash_after_stage",
    "stage_delay_ms",
}


class ContractError(ValueError):
    """Raised when a request or response violates the public test contract."""


@dataclass(frozen=True)
class WorkSpec:
    work_id: str
    payload: str
    crash_after_stage: int | None
    stage_delay_ms: int


def parse_work_spec(raw_input: str, default_delay_ms: int = 500) -> WorkSpec:
    """Parse a strict JSON request, or treat plain text as a safe no-crash job."""
    raw_input = raw_input.strip()
    if not raw_input:
        raise ContractError("input must not be empty")

    try:
        candidate = json.loads(raw_input)
    except json.JSONDecodeError:
        digest = hashlib.sha256(raw_input.encode("utf-8")).hexdigest()[:12]
        return WorkSpec(
            work_id=f"text-{digest}",
            payload=raw_input,
            crash_after_stage=None,
            stage_delay_ms=default_delay_ms,
        )

    if not isinstance(candidate, dict):
        raise ContractError("JSON input must be an object")
    unknown = sorted(set(candidate) - _ALLOWED_INPUT_FIELDS)
    if unknown:
        raise ContractError(f"unknown input fields: {', '.join(unknown)}")

    work_id = candidate.get("work_id")
    payload = candidate.get("payload")
    crash_after_stage = candidate.get("crash_after_stage")
    stage_delay_ms = candidate.get("stage_delay_ms", default_delay_ms)

    if not isinstance(work_id, str) or not _WORK_ID.fullmatch(work_id):
        raise ContractError(
            "work_id must be 1-64 characters: letters, digits, dot, dash, underscore"
        )
    if not isinstance(payload, str) or not payload.strip():
        raise ContractError("payload must be a non-empty string")
    if len(payload) > 16_384:
        raise ContractError("payload must be at most 16384 characters")
    if crash_after_stage is not None and (
        isinstance(crash_after_stage, bool)
        or not isinstance(crash_after_stage, int)
        or crash_after_stage not in range(len(STAGES))
    ):
        raise ContractError(f"crash_after_stage must be null or 0-{len(STAGES) - 1}")
    if (
        isinstance(stage_delay_ms, bool)
        or not isinstance(stage_delay_ms, int)
        or stage_delay_ms not in range(0, 10_001)
    ):
        raise ContractError("stage_delay_ms must be an integer from 0 through 10000")

    return WorkSpec(
        work_id=work_id,
        payload=payload,
        crash_after_stage=crash_after_stage,
        stage_delay_ms=stage_delay_ms,
    )


def build_stage_record(
    spec: WorkSpec,
    stage_index: int,
    process_instance_id: str,
    recovered_entry: bool,
) -> dict[str, Any]:
    """Build one stable, machine-checkable stage result."""
    if stage_index not in range(len(STAGES)):
        raise ContractError(f"invalid stage index: {stage_index}")
    stage_name = STAGES[stage_index]
    stage_result_sha256 = hashlib.sha256(
        f"{spec.payload}\n{stage_index}\n{stage_name}".encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "lra_stage",
        "work_id": spec.work_id,
        "payload_sha256": hashlib.sha256(spec.payload.encode("utf-8")).hexdigest(),
        "stage_index": stage_index,
        "stage_name": stage_name,
        "stage_count": len(STAGES),
        "stage_result_sha256": stage_result_sha256,
        "entry_mode": "recovered" if recovered_entry else "fresh",
        "process_instance_id": process_instance_id,
    }


def extract_stage_records(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract JSON stage records from a Responses API terminal object."""
    records: list[dict[str, Any]] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if not isinstance(text, str):
                continue
            try:
                candidate = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and candidate.get("kind") == "lra_stage":
                records.append(candidate)
    return records


def validate_terminal_response(
    response: dict[str, Any],
    expected_work_id: str,
    expect_recovery: bool,
) -> dict[str, Any]:
    """Fail closed unless the same response completed every stage exactly once."""
    errors: list[str] = []
    status = response.get("status")
    if status != "completed":
        errors.append(f"terminal status is {status!r}, expected 'completed'")

    records = extract_stage_records(response)
    indexes = [record.get("stage_index") for record in records]
    expected_indexes = list(range(len(STAGES)))
    if indexes != expected_indexes:
        errors.append(f"stage indexes are {indexes!r}, expected {expected_indexes!r}")

    work_ids = {record.get("work_id") for record in records}
    if work_ids != {expected_work_id}:
        errors.append(f"work IDs are {sorted(map(str, work_ids))!r}")

    payload_hashes = {record.get("payload_sha256") for record in records}
    if len(payload_hashes) != 1:
        errors.append("stage records do not share one payload hash")

    stage_names = [record.get("stage_name") for record in records]
    if stage_names != list(STAGES):
        errors.append("stage names do not match the owned 18-stage contract")
    stage_counts = {record.get("stage_count") for record in records}
    if stage_counts != {len(STAGES)}:
        errors.append(f"stage counts are {sorted(map(str, stage_counts))!r}")
    schema_versions = {record.get("schema_version") for record in records}
    if schema_versions != {SCHEMA_VERSION}:
        errors.append(f"schema versions are {sorted(map(str, schema_versions))!r}")
    stage_result_hashes = {
        record.get("stage_result_sha256") for record in records
    }
    if (
        len(stage_result_hashes) != len(STAGES)
        or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in stage_result_hashes
        )
    ):
        errors.append("stage result hashes are missing or duplicated")

    process_instances = {
        record.get("process_instance_id")
        for record in records
        if record.get("process_instance_id")
    }
    entry_modes = {record.get("entry_mode") for record in records}
    if expect_recovery:
        if len(process_instances) < 2:
            errors.append("recovery did not expose two process instances")
        if not {"fresh", "recovered"}.issubset(entry_modes):
            errors.append(f"entry modes do not prove recovery: {sorted(entry_modes)!r}")

    if errors:
        raise ContractError("; ".join(errors))
    return {
        "status": status,
        "work_id": expected_work_id,
        "stage_indexes": indexes,
        "stage_names": stage_names,
        "stage_result_sha256": sorted(stage_result_hashes),
        "payload_sha256": next(iter(payload_hashes)),
        "process_instance_ids": sorted(process_instances),
        "entry_modes": sorted(entry_modes),
        "recovery_proven": expect_recovery,
    }
