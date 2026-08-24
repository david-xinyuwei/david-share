from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_observations import (  # noqa: E402
    ObservationError,
    RecoverySignals,
    evaluate,
    recovery_action,
    run_self_test,
)


def valid_document() -> dict:
    return {
        "sequence": [1, 2, 3],
        "output_indexes": [0, 1, 2],
        "expected_last_index": 2,
        "snapshot": {
            "status": "completed",
            "terminal_event": "run_complete",
            "phases_completed": 3,
        },
        "expected_phases": 3,
    }


class ObservationValidatorTests(unittest.TestCase):
    def test_valid_document_passes(self) -> None:
        self.assertTrue(evaluate(valid_document())["passed"])

    def test_gap_duplicate_and_bare_done_fail(self) -> None:
        gap = valid_document()
        gap["sequence"] = [1, 3]
        duplicate = valid_document()
        duplicate["output_indexes"] = [0, 1, 1, 2]
        bare_done = valid_document()
        bare_done["snapshot"] = {
            "status": "completed",
            "terminal_event": "done",
            "phases_completed": 3,
        }

        self.assertFalse(evaluate(gap)["checks"]["sequence_gap_free"])
        self.assertFalse(
            evaluate(duplicate)["checks"]["output_coverage_complete"]
        )
        self.assertFalse(evaluate(bare_done)["checks"]["terminal_state_proven"])

    def test_invalid_schema_fails_explicitly(self) -> None:
        invalid = valid_document()
        invalid["sequence"] = "1,2,3"
        with self.assertRaises(ObservationError):
            evaluate(invalid)

        empty = valid_document()
        empty["sequence"] = []
        with self.assertRaises(ObservationError):
            evaluate(empty)

        boolean_phase_count = valid_document()
        boolean_phase_count["expected_phases"] = 1
        boolean_phase_count["snapshot"]["phases_completed"] = True
        with self.assertRaises(ObservationError):
            evaluate(boolean_phase_count)

        oversized = valid_document()
        oversized["expected_last_index"] = 1_000_000_000
        with self.assertRaises(ObservationError):
            evaluate(oversized)

    def test_unclassified_status_fails_closed(self) -> None:
        self.assertEqual(
            recovery_action(RecoverySignals(status_code=424)), "fail_closed"
        )
        self.assertEqual(
            recovery_action(RecoverySignals(status_code=403)), "fail_closed"
        )

    def test_materially_different_inputs_change_output_hash(self) -> None:
        first = evaluate(valid_document())
        second_document = valid_document()
        second_document["sequence"] = [20, 21, 22]
        second = evaluate(second_document)
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])

    def test_self_test_covers_positive_and_negative_paths(self) -> None:
        result = run_self_test()
        self.assertTrue(result["passed"])
        self.assertGreaterEqual(len(result["observation_cases"]), 4)
        self.assertGreaterEqual(len(result["recovery_action_cases"]), 5)


if __name__ == "__main__":
    unittest.main()
