import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def write_report(path: Path, resolved=(), unresolved=(), empty=(), errors=()) -> None:
    path.write_text(
        json.dumps(
            {
                "resolved_ids": list(resolved),
                "unresolved_ids": list(unresolved),
                "empty_patch_ids": list(empty),
                "error_ids": list(errors),
            }
        )
    )


class FrozenDisputeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.reference = self.root / "reference.json"
        self.baseline = self.root / "baseline.json"
        write_report(self.reference, resolved=("a", "b", "c"), unresolved=("d", "e"))
        write_report(self.baseline, resolved=("a", "d"), unresolved=("b", "c", "e"))
        self.manifest = self.root / "disputes.tsv"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_script(self, name: str, *args: str, expect_success: bool = True):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if expect_success and result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return result

    def build_manifest(self) -> None:
        self.run_script(
            "build_dispute_manifest.py",
            "--reference-report",
            str(self.reference),
            "--candidate-report",
            str(self.baseline),
            "--expected-count",
            "5",
            "--output",
            str(self.manifest),
        )

    def test_bidirectional_disputes_are_frozen(self) -> None:
        self.build_manifest()
        with self.manifest.open(newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual({row["instance_id"] for row in rows}, {"b", "c", "d"})
        directions = {row["instance_id"]: row["direction"] for row in rows}
        self.assertEqual(directions["b"], "REFERENCE_PASS_CANDIDATE_NOT")
        self.assertEqual(directions["d"], "CANDIDATE_PASS_REFERENCE_NOT")
        summary = json.loads(self.manifest.with_suffix(".summary.json").read_text())
        self.assertEqual(summary["accuracy_comparison"]["reference_resolved"], 3)
        self.assertEqual(summary["accuracy_comparison"]["candidate_resolved"], 2)
        self.assertEqual(summary["accuracy_comparison"]["delta_percentage_points"], -20.0)

    def test_full_frozen_set_is_replaced_once(self) -> None:
        self.build_manifest()
        retest = self.root / "retest.json"
        write_report(retest, resolved=("b", "d"), unresolved=("c",))
        output = self.root / "final"
        self.run_script(
            "finalize_frozen_disputes.py",
            "--reference-report",
            str(self.reference),
            "--baseline-report",
            str(self.baseline),
            "--expected-count",
            "5",
            "--dispute-manifest",
            str(self.manifest),
            "--retest-report",
            str(retest),
            "--output-dir",
            str(output),
        )
        summary = json.loads((output / "final-summary.json").read_text())
        self.assertEqual(summary["contract"]["frozen_disputes"], 3)
        self.assertEqual(summary["result"]["resolved"], 3)
        self.assertEqual(summary["result"]["accuracy_pct"], 60.0)

    def test_dynamic_subset_fails_closed(self) -> None:
        self.build_manifest()
        partial = self.root / "partial.json"
        write_report(partial, resolved=("b",), unresolved=("c",))
        result = self.run_script(
            "finalize_frozen_disputes.py",
            "--reference-report",
            str(self.reference),
            "--baseline-report",
            str(self.baseline),
            "--expected-count",
            "5",
            "--dispute-manifest",
            str(self.manifest),
            "--retest-report",
            str(partial),
            "--output-dir",
            str(self.root / "partial-output"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("every frozen dispute exactly once", result.stderr)

    def test_overlapping_shards_fail_closed(self) -> None:
        self.build_manifest()
        shard1 = self.root / "shard1.json"
        shard2 = self.root / "shard2.json"
        write_report(shard1, resolved=("b", "c"))
        write_report(shard2, resolved=("c", "d"))
        result = self.run_script(
            "finalize_frozen_disputes.py",
            "--reference-report",
            str(self.reference),
            "--baseline-report",
            str(self.baseline),
            "--expected-count",
            "5",
            "--dispute-manifest",
            str(self.manifest),
            "--retest-report",
            str(shard1),
            "--retest-report",
            str(shard2),
            "--output-dir",
            str(self.root / "overlap-output"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overlap", result.stderr.lower())

    def test_repository_offline_example(self) -> None:
        examples = REPO_ROOT / "examples"
        manifest = self.root / "example-disputes.tsv"
        self.run_script(
            "build_dispute_manifest.py",
            "--reference-report",
            str(examples / "reference-report.json"),
            "--candidate-report",
            str(examples / "candidate-report.json"),
            "--expected-count",
            "6",
            "--output",
            str(manifest),
        )
        output = self.root / "example-final"
        self.run_script(
            "finalize_frozen_disputes.py",
            "--reference-report",
            str(examples / "reference-report.json"),
            "--baseline-report",
            str(examples / "candidate-report.json"),
            "--expected-count",
            "6",
            "--dispute-manifest",
            str(manifest),
            "--retest-report",
            str(examples / "retest-shard-a.json"),
            "--retest-report",
            str(examples / "retest-shard-b.json"),
            "--output-dir",
            str(output),
        )
        summary = json.loads((output / "final-summary.json").read_text())
        self.assertEqual(summary["contract"]["frozen_disputes"], 4)
        self.assertEqual(summary["result"]["resolved"], 3)
        self.assertEqual(summary["result"]["accuracy_pct"], 50.0)

    def test_identically_incomplete_reports_fail_closed(self) -> None:
        result = self.run_script(
            "build_dispute_manifest.py",
            "--reference-report",
            str(self.reference),
            "--candidate-report",
            str(self.baseline),
            "--expected-count",
            "6",
            "--output",
            str(self.manifest),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("coverage 5 != expected 6", result.stderr)

    def test_stale_manifest_metadata_fails_closed(self) -> None:
        self.build_manifest()
        text = self.manifest.read_text().replace(
            "REFERENCE_PASS_CANDIDATE_NOT", "CANDIDATE_PASS_REFERENCE_NOT", 1
        )
        self.manifest.write_text(text)
        retest = self.root / "retest.json"
        write_report(retest, resolved=("b", "d"), unresolved=("c",))
        result = self.run_script(
            "finalize_frozen_disputes.py",
            "--reference-report",
            str(self.reference),
            "--baseline-report",
            str(self.baseline),
            "--expected-count",
            "5",
            "--dispute-manifest",
            str(self.manifest),
            "--retest-report",
            str(retest),
            "--output-dir",
            str(self.root / "stale-output"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("metadata differs", result.stderr)

    def test_zero_disputes_finalize_without_retest_report(self) -> None:
        identical = self.root / "identical.json"
        write_report(identical, resolved=("a", "b", "c"), unresolved=("d", "e"))
        self.run_script(
            "build_dispute_manifest.py",
            "--reference-report",
            str(self.reference),
            "--candidate-report",
            str(identical),
            "--expected-count",
            "5",
            "--output",
            str(self.manifest),
        )
        output = self.root / "zero-final"
        self.run_script(
            "finalize_frozen_disputes.py",
            "--reference-report",
            str(self.reference),
            "--baseline-report",
            str(identical),
            "--expected-count",
            "5",
            "--dispute-manifest",
            str(self.manifest),
            "--output-dir",
            str(output),
        )
        summary = json.loads((output / "final-summary.json").read_text())
        self.assertEqual(summary["contract"]["frozen_disputes"], 0)
        self.assertEqual(summary["result"]["resolved"], 3)


if __name__ == "__main__":
    unittest.main()
