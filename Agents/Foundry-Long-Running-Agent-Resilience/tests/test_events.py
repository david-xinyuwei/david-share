from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lra_resilience.events import summarize_event_file, summarize_event_records


class EventSummaryTests(unittest.TestCase):
    def test_summary_discards_identity_fields(self) -> None:
        summary = summarize_event_records(
            [
                {"type": "phase", "phase": 1, "total": 2, "session_id": "private"},
                {"type": "recovered", "phase": 1, "invocation_id": "private"},
                {"type": "done", "status": "completed"},
            ]
        )
        serialized = json.dumps(summary)
        self.assertNotIn("session_id", serialized)
        self.assertNotIn("invocation_id", serialized)
        self.assertEqual(summary["phases"], [1])
        self.assertTrue(summary["recovery_observed"])
        self.assertTrue(summary["completion_observed"])

    def test_nested_event_records_are_supported(self) -> None:
        summary = summarize_event_records(
            [
                {"source": "stream", "event": {"type": "response.output_item.done", "output_index": 0}},
                {"source": "stream", "event": {"type": "response.completed", "status": "completed"}},
            ]
        )
        self.assertEqual(summary["output_indexes"], [0])
        self.assertTrue(summary["completion_observed"])

    def test_invalid_jsonl_reports_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "broken.jsonl"
            path.write_text("{}\nnot-json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"broken\.jsonl:2: invalid JSON"):
                summarize_event_file(path)

    def test_empty_input_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "no public protocol events"):
            summarize_event_records([])

    def test_identity_only_input_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "no public protocol events"):
            summarize_event_records([{"session_id": "discarded"}])


if __name__ == "__main__":
    unittest.main()
