import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class ValidationToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

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

    def make_generation(self, ids=("a", "b")) -> Path:
        run = self.root / "run"
        run.mkdir()
        predictions = {}
        for instance_id in ids:
            predictions[instance_id] = {
                "instance_id": instance_id,
                "model_name_or_path": "test-model",
                "model_patch": "diff --git a/a.py b/a.py\n" if instance_id == "a" else "",
            }
            instance = run / instance_id
            instance.mkdir()
            (instance / f"{instance_id}.traj.json").write_text(
                json.dumps(
                    {
                        "info": {
                            "exit_status": (
                                "Submitted" if instance_id == "a" else "RepeatedFormatError"
                            ),
                            "config": {
                                "environment": {"image": f"image-{instance_id}"},
                                "model": {"model_name": "test-model"},
                            },
                        }
                    }
                )
            )
        (run / "preds.json").write_text(json.dumps(predictions))
        return run

    def test_prediction_validation_and_config_audit(self) -> None:
        run = self.make_generation()
        manifest = self.root / "manifest.tsv"
        with manifest.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["instance_id"], delimiter="\t")
            writer.writeheader()
            writer.writerows([{"instance_id": "a"}, {"instance_id": "b"}])
        summary = self.root / "summary.json"
        self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--manifest",
            str(manifest),
            "--expected-count",
            "2",
            "--summary",
            str(summary),
        )
        payload = json.loads(summary.read_text())
        self.assertEqual(payload["nonempty_patches"], 1)
        self.assertEqual(payload["empty_patches"], 1)
        audit = self.run_script("audit_effective_configs.py", "--run-dir", str(run))
        self.assertIn('"normalized_config_count": 1', audit.stdout)

    def test_prediction_manifest_mismatch_fails(self) -> None:
        run = self.make_generation()
        manifest = self.root / "manifest.tsv"
        manifest.write_text("instance_id\na\n")
        result = self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--manifest",
            str(manifest),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differ from the frozen manifest", result.stderr)

    def test_prediction_embedded_id_mismatch_fails(self) -> None:
        run = self.make_generation(ids=("a",))
        predictions_path = run / "preds.json"
        predictions = json.loads(predictions_path.read_text())
        predictions["a"]["instance_id"] = "different"
        predictions_path.write_text(json.dumps(predictions))
        result = self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--expected-count",
            "1",
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("key and embedded instance_id differ", result.stderr)

    def test_report_merge_rejects_overlap(self) -> None:
        first = self.root / "first.json"
        second = self.root / "second.json"
        first.write_text(json.dumps({"resolved_ids": ["a"], "unresolved_ids": []}))
        second.write_text(json.dumps({"resolved_ids": ["a"], "unresolved_ids": []}))
        result = self.run_script(
            "merge_official_reports.py",
            "--report",
            str(first),
            "--report",
            str(second),
            "--expected-count",
            "2",
            "--output",
            str(self.root / "merged.json"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overlap", result.stderr.lower())

    def test_report_merge_rejects_incomplete_coverage(self) -> None:
        report = self.root / "report.json"
        report.write_text(json.dumps({"resolved_ids": ["a"], "unresolved_ids": []}))
        result = self.run_script(
            "merge_official_reports.py",
            "--report",
            str(report),
            "--expected-count",
            "2",
            "--output",
            str(self.root / "merged.json"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("coverage 1 != expected 2", result.stderr)

    def test_time_exceeded_is_a_valid_agent_limit(self) -> None:
        run = self.make_generation(ids=("a",))
        trajectory = run / "a" / "a.traj.json"
        payload = json.loads(trajectory.read_text())
        payload["info"]["exit_status"] = "TimeExceeded"
        trajectory.write_text(json.dumps(payload))
        result = self.run_script(
            "validate_predictions.py",
            "--run-dir",
            str(run),
            "--expected-count",
            "1",
        )
        self.assertIn('"TimeExceeded": 1', result.stdout)

    def test_hash_assets_rejects_empty_root(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        result = self.run_script(
            "hash_assets.py",
            str(empty),
            "--output",
            str(empty / "SHA256SUMS.txt"),
            expect_success=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No files found", result.stderr)


if __name__ == "__main__":
    unittest.main()
