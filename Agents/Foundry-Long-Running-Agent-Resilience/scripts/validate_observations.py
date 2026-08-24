#!/usr/bin/env python3
"""Validate workload continuity, terminal state, and recovery classification.

This tool evaluates caller-supplied JSON. The built-in self-test cases are
explicit test fixtures; they are not service responses or product claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = 1
MAX_OBSERVATION_ITEMS = 1_000_000


class ObservationError(ValueError):
    """Raised when observation input has an invalid schema."""


def sequence_has_no_gap(sequence: Sequence[int]) -> bool:
    return all(
        current - previous == 1
        for previous, current in zip(sequence, sequence[1:])
    )


def output_coverage_complete(indexes: Sequence[int], expected_last: int) -> bool:
    return (
        expected_last >= 0
        and len(indexes) == expected_last + 1
        and len(set(indexes)) == len(indexes)
        and min(indexes, default=-1) == 0
        and max(indexes, default=-1) == expected_last
    )


def completion_is_proven(
    snapshot: dict[str, Any], *, expected_phases: int
) -> bool:
    phases_completed = snapshot.get("phases_completed")
    return (
        snapshot.get("status") == "completed"
        and snapshot.get("terminal_event") == "run_complete"
        and isinstance(phases_completed, int)
        and not isinstance(phases_completed, bool)
        and phases_completed == expected_phases
    )


@dataclass(frozen=True)
class RecoverySignals:
    status_code: int
    deadline_expired: bool = False
    host_replacement_confirmed: bool = False
    same_work_addressable: bool = False
    observer_auth_expired: bool = False


def recovery_action(signals: RecoverySignals) -> str:
    if signals.deadline_expired:
        return "timeout"
    if (
        signals.status_code == 424
        and signals.host_replacement_confirmed
        and signals.same_work_addressable
    ):
        return "poll_same_work_with_bounded_backoff"
    if (
        signals.status_code in {401, 403}
        and signals.observer_auth_expired
    ):
        return "refresh_observer_auth_then_read_again"
    return "fail_closed"


def _int_list(value: Any, field: str) -> list[int]:
    if not isinstance(value, list) or any(
        not isinstance(item, int) or isinstance(item, bool) for item in value
    ):
        raise ObservationError(f"{field} must be an array of integers")
    if len(value) > MAX_OBSERVATION_ITEMS:
        raise ObservationError(
            f"{field} exceeds the {MAX_OBSERVATION_ITEMS}-item limit"
        )
    return value


def _required_int(document: dict[str, Any], field: str) -> int:
    value = document.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ObservationError(f"{field} must be an integer")
    return value


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ObservationError("input must be a JSON object")
    sequence = _int_list(document.get("sequence"), "sequence")
    indexes = _int_list(document.get("output_indexes"), "output_indexes")
    expected_last = _required_int(document, "expected_last_index")
    expected_phases = _required_int(document, "expected_phases")
    if not sequence:
        raise ObservationError("sequence must not be empty")
    if not indexes:
        raise ObservationError("output_indexes must not be empty")
    if expected_last < 0:
        raise ObservationError("expected_last_index must not be negative")
    if expected_last >= MAX_OBSERVATION_ITEMS:
        raise ObservationError(
            f"expected_last_index must be below {MAX_OBSERVATION_ITEMS}"
        )
    if expected_phases < 1:
        raise ObservationError("expected_phases must be positive")
    if expected_phases > MAX_OBSERVATION_ITEMS:
        raise ObservationError(
            f"expected_phases must not exceed {MAX_OBSERVATION_ITEMS}"
        )
    snapshot = document.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ObservationError("snapshot must be a JSON object")
    if not isinstance(snapshot.get("status"), str):
        raise ObservationError("snapshot.status must be a string")
    if not isinstance(snapshot.get("terminal_event"), str):
        raise ObservationError("snapshot.terminal_event must be a string")
    phases_completed = snapshot.get("phases_completed")
    if not isinstance(phases_completed, int) or isinstance(
        phases_completed, bool
    ):
        raise ObservationError("snapshot.phases_completed must be an integer")

    checks = {
        "sequence_gap_free": sequence_has_no_gap(sequence),
        "output_coverage_complete": output_coverage_complete(
            indexes, expected_last
        ),
        "terminal_state_proven": completion_is_proven(
            snapshot, expected_phases=expected_phases
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_type": "dynamic-runtime",
        "input_sha256": _canonical_sha256(document),
        "observed": {
            "sequence_count": len(sequence),
            "output_index_count": len(indexes),
            "expected_last_index": expected_last,
            "expected_phases": expected_phases,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_self_test() -> dict[str, Any]:
    base_snapshot = {
        "status": "completed",
        "terminal_event": "run_complete",
        "phases_completed": 3,
    }
    cases = [
        {
            "name": "clean",
            "document": {
                "sequence": [10, 11, 12],
                "output_indexes": [0, 1, 2],
                "expected_last_index": 2,
                "snapshot": base_snapshot,
                "expected_phases": 3,
            },
            "expected": True,
        },
        {
            "name": "sequence_gap",
            "document": {
                "sequence": [10, 12],
                "output_indexes": [0, 1, 2],
                "expected_last_index": 2,
                "snapshot": base_snapshot,
                "expected_phases": 3,
            },
            "expected": False,
        },
        {
            "name": "duplicate_output",
            "document": {
                "sequence": [10, 11, 12],
                "output_indexes": [0, 1, 1, 2],
                "expected_last_index": 2,
                "snapshot": base_snapshot,
                "expected_phases": 3,
            },
            "expected": False,
        },
        {
            "name": "bare_done",
            "document": {
                "sequence": [10, 11, 12],
                "output_indexes": [0, 1, 2],
                "expected_last_index": 2,
                "snapshot": {
                    "status": "completed",
                    "terminal_event": "done",
                    "phases_completed": 3,
                },
                "expected_phases": 3,
            },
            "expected": False,
        },
    ]
    case_results = []
    for case in cases:
        result = evaluate(case["document"])
        case_results.append(
            {
                "name": case["name"],
                "expected": case["expected"],
                "actual": result["passed"],
                "matched": result["passed"] == case["expected"],
                "checks": result["checks"],
                "input_sha256": result["input_sha256"],
            }
        )

    action_cases = [
        (
            "confirmed_424",
            RecoverySignals(
                status_code=424,
                host_replacement_confirmed=True,
                same_work_addressable=True,
            ),
            "poll_same_work_with_bounded_backoff",
        ),
        (
            "unclassified_424",
            RecoverySignals(status_code=424),
            "fail_closed",
        ),
        (
            "expired_observer_403",
            RecoverySignals(status_code=403, observer_auth_expired=True),
            "refresh_observer_auth_then_read_again",
        ),
        (
            "unclassified_403",
            RecoverySignals(status_code=403),
            "fail_closed",
        ),
        (
            "deadline",
            RecoverySignals(
                status_code=424,
                deadline_expired=True,
                host_replacement_confirmed=True,
                same_work_addressable=True,
            ),
            "timeout",
        ),
    ]
    action_results = [
        {
            "name": name,
            "signals": asdict(signals),
            "expected": expected,
            "actual": recovery_action(signals),
            "matched": recovery_action(signals) == expected,
        }
        for name, signals, expected in action_cases
    ]
    checks = {
        "observation_cases_match": all(
            item["matched"] for item in case_results
        ),
        "recovery_actions_match": all(
            item["matched"] for item in action_results
        ),
        "materially_different_inputs_change_hash": len(
            {item["input_sha256"] for item in case_results}
        )
        == len(case_results),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_type": "test-fixture",
        "claim_scope": (
            "Executable validator self-test; fixtures are not service responses."
        ),
        "observation_cases": case_results,
        "recovery_action_cases": action_results,
        "checks": checks,
        "passed": all(checks.values()),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate workload continuity and terminal evidence from JSON. "
            "Unclassified recovery signals fail closed."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="evaluate a caller-supplied observation JSON file"
    )
    evaluate_parser.add_argument("input", type=Path)
    evaluate_parser.add_argument("--output", type=Path)

    self_test = subparsers.add_parser(
        "self-test", help="run explicit positive and negative fixtures"
    )
    self_test.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "evaluate":
        document = json.loads(args.input.read_text(encoding="utf-8"))
        result = evaluate(document)
    else:
        result = run_self_test()

    if args.output is not None:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
