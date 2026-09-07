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
        self.assertIn("| Concurrency | test-fixture |", table)
        self.assertEqual(table.count("| 1 | 3.000 |"), 2)
        self.assertIn("| 1 | 0.003 |", table)
        self.assertIn("96 valid response observations and 0 missing", table)

    def test_chinese_latency_tables_are_narrow_and_keep_values(self):
        groups = validate_report.read_json(self.root / "data/groups.json")["groups"]
        summary = validate_report.read_json(self.root / "data/summary.json")
        table = validate_report.latency_table(groups, summary, True)
        table_rows = [line for line in table.splitlines() if line.startswith("|")]
        self.assertTrue(all(line.count("|") == 5 for line in table_rows))
        self.assertIn("| 1 | 82.727 | 75.127 | 80.286 |", table)
        self.assertIn("| 1 | 18.567 | 8.011 | 5.875 |", table)
        self.assertIn("| 1 | 16.359 | 6.236 | 6.185 |", table)

    def test_chinese_result_tables_are_narrow_and_keep_values(self):
        summary = validate_report.read_json(self.root / "data/summary.json")
        table = validate_report.result_table(summary, True)
        table_rows = [line for line in table.splitlines() if line.startswith("|")]
        self.assertTrue(all(line.count("|") == 5 for line in table_rows))
        self.assertIn("| 1 | DFlash 2-7 | 150.51 | 1149.41 |", table)
        self.assertIn("| 4 | DFlash 2-7 | 31、31、29 | 31、31、30 |", table)
        self.assertIn("| 4 | DFlash 2-7 | 1、1、3 | 1、1、1 |", table)
        self.assertNotIn("代码 raw", table)
        self.assertNotIn("代码 normal", table)

    def test_distinct_normal_correct_counts_are_not_hidden(self):
        summary = validate_report.read_json(self.root / "data/summary.json")
        summary["matched_summary"][0]["datasets"]["humaneval_plus"]["normal_correct"][0] = 28
        table = validate_report.result_table(summary, True)
        self.assertIn("正常结束且答对的数量另列如下", table)
        self.assertIn("| 1 | 基线 | 28、31、30 | 30、30、30 |", table)

    def test_latency_retains_metric_specific_missing_counts(self):
        groups = [{"group_id": "observed", "client": {"all": {
            metric: {"p50": 0.01, "valid_count": 32, "missing_count": 0}
            for metric in ("ttft_token_s", "tpot_s", "e2e_s")}}}]
        groups[0]["client"]["all"]["tpot_s"].update(valid_count=31, missing_count=1)
        summary = {"matched_summary": [{"route": "mtp7", "concurrency": 1,
                    "source_groups": ["observed"]}]}
        table = validate_report.latency_table(groups, summary, True)
        self.assertIn("| MTP7 / 1 | ttft_token_s | 32 | 0 |", table)
        self.assertIn("| MTP7 / 1 | tpot_s | 31 | 1 |", table)

    def test_readable_timeline_uses_recorded_timestamps(self):
        run = validate_report.read_json(self.root / "evidence/run.json")
        table = validate_report.run_log(run, True)
        self.assertIn("| 最后一次执行开始 | 2026-09-06 06:28:46 |", table)
        self.assertIn("| 本地证据校验通过 | 2026-09-06 15:22:13 |", table)
        self.assertIn("| GPU 已释放 | 2026-09-06 15:22:53 |", table)
        self.assertIn("1,920/5,904", table)

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