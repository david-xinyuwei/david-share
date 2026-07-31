#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path


OUTCOME_KEYS = {
    "resolved_ids": "R",
    "unresolved_ids": "U",
    "empty_patch_ids": "E",
    "error_ids": "X",
}

CANARY_COUNT_KEYS = {
    "resolved": "resolved_instances",
    "unresolved": "unresolved_instances",
    "empty": "empty_patch_instances",
    "errors": "error_instances",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_outcomes(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: report must be a JSON object")
    outcomes = {}
    for key, outcome in OUTCOME_KEYS.items():
        values = payload.get(key, [])
        if not isinstance(values, list):
            raise ValueError(f"{path}: {key} must be a list")
        for instance_id in values:
            if not isinstance(instance_id, str) or not instance_id:
                raise ValueError(f"{path}: {key} contains an invalid instance ID")
            if instance_id in outcomes:
                raise ValueError(f"{path}: duplicate outcome for {instance_id}")
            outcomes[instance_id] = outcome
    if not outcomes:
        raise ValueError(f"{path}: no SWE-bench outcome categories found")
    return outcomes


def require_expected_count(outcomes: dict[str, str], expected_count: int, path: Path) -> None:
    if expected_count <= 0:
        raise ValueError("expected count must be positive")
    if len(outcomes) != expected_count:
        raise ValueError(
            f"{path}: outcome coverage {len(outcomes)} != expected {expected_count}"
        )


def is_pass(outcome: str) -> bool:
    return outcome == "R"


def validate_scored_canary_counts(payload: dict) -> dict[str, int]:
    if not isinstance(payload, dict):
        raise ValueError("Canary aggregate report must be a JSON object")
    counts = {}
    for label, key in CANARY_COUNT_KEYS.items():
        if key not in payload:
            raise ValueError(f"Canary aggregate is missing required field {key}")
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Canary aggregate field {key} must be a non-negative integer")
        counts[label] = value
    total = sum(counts.values())
    if total != 1:
        raise ValueError(f"Expected one classified canary outcome, found {total}")
    if counts["errors"]:
        raise ValueError("Scored canary ended with an infrastructure error")
    return counts
