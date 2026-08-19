from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "parse_demo_output", ROOT / "scripts" / "parse_demo_output.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ParseDemoOutputTests(unittest.TestCase):
    def fixture(self, name: str) -> str:
        return (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8")

    def test_full_warm_cache_run_is_recomputed(self) -> None:
        summary = MODULE.summarize(MODULE.parse_rows(self.fixture("demo-success.txt")))

        self.assertTrue(summary["firstCallColdObserved"])
        self.assertEqual(summary["warm"]["hits"], 5)
        self.assertEqual(summary["warm"]["cachedTokens"]["mean"], 2304)
        self.assertAlmostEqual(summary["warm"]["meanLatencyMs"], 3642.4)
        self.assertAlmostEqual(summary["firstToWarmSpeedup"], 1.597848)

    def test_three_of_five_warm_hits_meet_default_gate(self) -> None:
        summary = MODULE.summarize(
            MODULE.parse_rows(self.fixture("demo-partial-cache.txt"))
        )

        self.assertFalse(summary["firstCallColdObserved"])
        self.assertEqual(summary["warm"]["hits"], 3)
        self.assertEqual(summary["warm"]["hitRatio"], 0.6)
        self.assertIsNone(summary["firstToWarmSpeedup"])

    def test_zero_cache_hits_fail_closed(self) -> None:
        with self.assertRaisesRegex(MODULE.ValidationError, "below"):
            MODULE.summarize(MODULE.parse_rows(self.fixture("demo-no-cache.txt")))

    def test_zero_hit_threshold_is_rejected(self) -> None:
        with self.assertRaisesRegex(MODULE.ValidationError, "greater than 0"):
            MODULE.summarize(
                MODULE.parse_rows(self.fixture("demo-no-cache.txt")),
                min_warm_hit_ratio=0,
            )

    def test_zero_latency_is_rejected(self) -> None:
        rows = MODULE.parse_rows(self.fixture("demo-success.txt"))
        rows[1] = MODULE.CallResult(2, "bad.diff", 0, 3000, 2304, 10, 77)
        with self.assertRaisesRegex(MODULE.ValidationError, "measurable latency"):
            MODULE.summarize(rows)

    def test_http_error_fails_before_row_scoring(self) -> None:
        with self.assertRaisesRegex(MODULE.ValidationError, "HTTP or transport"):
            MODULE.parse_rows("1  a.diff  10  20  0  5  0%\nHTTP 401: denied")

    def test_quickstart_demo_failure_after_valid_rows_fails(self) -> None:
        text = self.fixture("demo-success.txt") + "\nDemo exited with code 1.\n"
        with self.assertRaisesRegex(MODULE.ValidationError, "HTTP or transport"):
            MODULE.parse_rows(text)

    def test_traceback_after_valid_rows_fails(self) -> None:
        text = self.fixture("demo-success.txt") + "\nTraceback (most recent call last):\n"
        with self.assertRaisesRegex(MODULE.ValidationError, "HTTP or transport"):
            MODULE.parse_rows(text)

    def test_impossible_cached_tokens_fail(self) -> None:
        rows = MODULE.parse_rows(self.fixture("demo-success.txt"))
        rows[1] = MODULE.CallResult(2, "bad.diff", 10, 100, 101, 10, 100)
        with self.assertRaisesRegex(MODULE.ValidationError, "impossible"):
            MODULE.summarize(rows)

    def test_inconsistent_hit_percent_fails(self) -> None:
        rows = MODULE.parse_rows(self.fixture("demo-success.txt"))
        rows[1] = MODULE.CallResult(2, "bad.diff", 10, 100, 50, 10, 90)
        with self.assertRaisesRegex(MODULE.ValidationError, "inconsistent"):
            MODULE.summarize(rows)

    def test_missing_call_row_fails_closed(self) -> None:
        rows = MODULE.parse_rows(self.fixture("demo-success.txt"))[:-1]
        with self.assertRaisesRegex(MODULE.ValidationError, "expected 6"):
            MODULE.summarize(rows)


if __name__ == "__main__":
    unittest.main()