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
