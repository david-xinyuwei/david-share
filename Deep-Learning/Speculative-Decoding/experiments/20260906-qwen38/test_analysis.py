"""Exercise the published replay and reject damaged copies of recorded evidence."""

import copy
import json
from pathlib import Path
import unittest

import analyze_results


ROOT = Path(__file__).resolve().parent


class EvidenceReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((ROOT / "data/groups.json").read_text(encoding="utf-8"))
        cls.expected = json.loads((ROOT / "data/summary.json").read_text(encoding="utf-8"))

    def setUp(self):
        self.groups = copy.deepcopy(self.original["groups"])
        self.coverage = copy.deepcopy(self.original["coverage"])

    def test_saved_summary_is_reproduced(self):
        self.assertEqual(analyze_results.summarize(self.groups, self.coverage), self.expected)

    def test_missing_engine_is_rejected(self):
        self.groups[0].pop("engine")
        with self.assertRaisesRegex(ValueError, "ENGINE_NOT_RECONCILED"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_wrong_engine_tokens_are_rejected(self):
        self.groups[0]["engine"]["generation_tokens"] += 1
        with self.assertRaisesRegex(ValueError, "ENGINE_TOKEN_MISMATCH"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_changed_grade_count_is_rejected(self):
        self.groups[0]["scores"]["datasets"]["humaneval_plus"]["raw_correct"] += 1
        with self.assertRaisesRegex(ValueError, "RAW_SCORE_MISMATCH"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_missing_group_is_rejected(self):
        self.groups.pop()
        with self.assertRaisesRegex(ValueError, "COMPLETED_COUNT_MISMATCH"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_duplicate_group_is_rejected(self):
        self.groups.append(copy.deepcopy(self.groups[0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_GROUP"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_duplicate_task_is_rejected(self):
        self.groups[0]["ordered_task_ids"][1] = self.groups[0]["ordered_task_ids"][0]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TASK"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_unfinished_group_is_rejected(self):
        self.groups[0]["status"] = "RUNNING"
        with self.assertRaisesRegex(ValueError, "GROUP_NOT_COMPLETE"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_resumed_throughput_is_rejected(self):
        self.groups[0]["throughput_status"] = "INVALID_RESUMED"
        with self.assertRaisesRegex(ValueError, "RESUMED_OR_INVALID_THROUGHPUT"):
            analyze_results.summarize(self.groups, self.coverage)

    def test_pair_order_change_is_rejected(self):
        group = next(group for group in self.groups if group["stage"] == "S")
        group["ordered_task_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "PAIRED_INPUT_ORDER_MISMATCH"):
            analyze_results.summarize(self.groups, self.coverage)


if __name__ == "__main__":
    unittest.main()