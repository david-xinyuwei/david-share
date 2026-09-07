"""Reject drift in the public report, event lineage and evidence inventory."""

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import validate_report


ROOT = Path(__file__).resolve().parent


class ReportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "topic" / "experiments" / ROOT.name
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "regenerated"))
        for language in ("README.md", "README-CN.md"):
            shutil.copyfile(ROOT.parent.parent / language, self.root.parent.parent / language)
            old = self.root.parent / "20260905-quality"
            old.mkdir(exist_ok=True)
            shutil.copyfile(ROOT.parent / "20260905-quality" / language, old / language)

    def mutate_json(self, relative, mutate):
        path = self.root / relative
        content = json.loads(path.read_text(encoding="utf-8"))
        mutate(content)
        path.write_text(json.dumps(content), encoding="utf-8")

    def test_recorded_report_passes(self):
        validate_report.validate(self.root)

    def test_run_identity_change_is_rejected(self):
        self.mutate_json("evidence/run.json", lambda value: value.update(run_id="different-run"))
        with self.assertRaisesRegex(ValueError, "RUN_ID_MISMATCH"):
            validate_report.validate_data(self.root)

    def test_missing_evidence_is_rejected(self):
        (self.root / "evidence/request-examples.json").unlink()
        with self.assertRaises(FileNotFoundError):
            validate_report.validate_data(self.root)

    def test_duration_change_is_rejected(self):
        self.mutate_json("evidence/run.json", lambda value: value["timing"].update(last_invocation_elapsed_s=0))
        with self.assertRaisesRegex(ValueError, "INVOCATION_DURATION_MISMATCH"):
            validate_report.validate_data(self.root)

    def test_stale_source_is_rejected(self):
        source = self.root / "source/scoring.py"
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "EXECUTED_SOURCE_CHANGED"):
            validate_report.validate_data(self.root)

    def test_request_change_is_rejected(self):
        self.mutate_json("evidence/request-examples.json", lambda value: value[0]["request"].update(temperature=0))
        with self.assertRaisesRegex(ValueError, "REQUEST_HASH_MISMATCH"):
            validate_report.validate_data(self.root)

    def test_table_change_is_rejected(self):
        path = self.root / "README.md"
        path.write_text(path.read_text(encoding="utf-8").replace("150.51", "151.51"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:RESULT_TABLE"):
            validate_report.validate(self.root)

    def test_duplicate_block_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE_REPORT_BLOCK"):
            validate_report.generated_block("<!-- BEGIN RESULT_TABLE -->" * 2 + "<!-- END RESULT_TABLE -->", "RESULT_TABLE", "", refresh=False)

    def test_counterexample_ratio_drift_is_rejected(self):
        path = self.root / "README.md"
        path.write_text(path.read_text(encoding="utf-8").replace("0.8713", "1.1640"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:COUNTEREXAMPLE"):
            validate_report.validate(self.root)

    def test_latency_uses_median_of_group_percentiles(self):
        groups = [{"group_id": str(index), "client": {"all": {
            metric: {"p50": value, "valid_count": 32, "missing_count": 0}
            for metric in ("ttft_token_s", "tpot_s", "e2e_s")}}}
            for index, value in enumerate((0.001, 0.010, 0.003))]
        summary = {"matched_summary": [{"route": "test-fixture", "concurrency": 1,
                    "source_groups": ["0", "1", "2"]}]}
        table = validate_report.latency_table(groups, summary, False)
        self.assertIn("| test-fixture / 1 | 3.000 | 3.000 | 0.003 | 96 / 0 | 96 / 0 | 96 / 0 |", table)

    def test_parent_onboarding_removal_is_rejected(self):
        parent = self.root.parent.parent / "README.md"
        parent.write_text(parent.read_text(encoding="utf-8").replace("python experiments/20260906-qwen38/validate_report.py", "omitted"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "PARENT_REPLAY_ENTRY_MISSING"):
            validate_report.validate(self.root)

    def test_manifest_path_escape_is_rejected(self):
        self.mutate_json(validate_report.MANIFEST, lambda value: value["files"].update({"../outside.json": {"sha256": "0" * 64, "bytes": 0}}))
        with self.assertRaisesRegex(ValueError, "MANIFEST_PATH_ESCAPE"):
            validate_report.verify_manifest(self.root)

    def test_edited_binary_is_rejected(self):
        path = self.root / "images/throughput.png"
        path.write_bytes(path.read_bytes() + b"drift")
        with self.assertRaisesRegex(ValueError, "PUBLISHED_FILE_HASH_OR_SET_MISMATCH"):
            validate_report.verify_manifest(self.root)

    def test_forged_validation_record_is_rejected(self):
        self.mutate_json(validate_report.RULES, lambda value: value["checks"].append(copy.deepcopy(value["checks"][0])))
        with self.assertRaisesRegex(ValueError, "VALIDATION_RECORD_DRIFT"):
            validate_report.validate(self.root)


if __name__ == "__main__":
    unittest.main()