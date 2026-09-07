"""Reject drift in the public report, event lineage and evidence inventory."""

import copy
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
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
        self.mutate_json("evidence/run.json", lambda value: value["stages"]["S"].update(measured_group_wall_s=0))
        with self.assertRaisesRegex(ValueError, "STAGE_DURATION_MISMATCH"):
            validate_report.validate_data(self.root)

    def test_internal_operations_are_not_public_evidence(self):
        self.mutate_json("evidence/run.json", lambda value: value.update(closure={"power_decision": "STOPPED"}))
        with self.assertRaisesRegex(ValueError, "INTERNAL_OPERATIONS_IN_PUBLIC_EVIDENCE"):
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

    def test_public_reports_omit_internal_timeline(self):
        for filename in ("README.md", "README-CN.md"):
            text = (self.root / filename).read_text(encoding="utf-8")
            for internal_content in ("run-timeline.png", "BEGIN RUN_LOG", "--timeline"):
                self.assertNotIn(internal_content, text)

    def test_parent_onboarding_removal_is_rejected(self):
        parent = self.root.parent.parent / "README.md"
        parent.write_text(parent.read_text(encoding="utf-8").replace("python experiments/20260906-qwen38/validate_report.py", "omitted"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "PARENT_REPLAY_ENTRY_MISSING"):
            validate_report.validate(self.root)

    def how_to_run_blocks(self, filename):
        text = (self.root / filename).read_text(encoding="utf-8")
        self.assertEqual(text.count("\n## How to Run\n"), 1)
        section = text.split("\n## How to Run\n", 1)[1].split("\n## ", 1)[0]
        blocks = re.findall(r"```bash\n(.*?)\n```", section, re.S)
        self.assertEqual(len(blocks), 6)
        parent = (self.root.parent.parent / filename).read_text(encoding="utf-8")
        self.assertIn(f"experiments/{self.root.name}/{filename}#how-to-run", parent)
        return blocks

    def test_how_to_run_matches_recorded_launch_contract(self):
        blocks = self.how_to_run_blocks("README.md")
        self.assertEqual(blocks, self.how_to_run_blocks("README-CN.md"))
        config = validate_report.read_json(self.root / "evidence/configuration.json")
        serving = config["serving"]
        for role in ("target", "draft"):
            self.assertIn("hf download " + config[role]["model_id"], blocks[0])
            self.assertIn("--revision " + config[role]["revision"], blocks[0])
        self.assertIn("VLLM_USE_V2_MODEL_RUNNER=1", blocks[1])
        common = re.search(r"COMMON=\(\n(.*?)\n\)", blocks[1], re.S)
        self.assertIsNotNone(common)
        tokens = shlex.split(common.group(1))
        self.assertEqual(tokens.count("--no-enable-prefix-caching"), 1)
        self.assertIs(serving["prefix_caching"], False)
        tokens.remove("--no-enable-prefix-caching")
        options = dict(zip(tokens[::2], tokens[1::2]))
        self.assertEqual(len(options) * 2, len(tokens))
        expected = {
            "--model": "$MODEL_ROOT/target", "--served-model-name": config["target"]["model_id"],
            "--dtype": config["target"]["dtype"], "--kv-cache-dtype": "auto",
            "--attention-backend": "FLASH_ATTN", "--mamba-ssm-cache-dtype": "float32",
            "--generation-config": "vllm", "--seed": str(config["sampling"]["seed"]),
            "--limit-mm-per-prompt": '{"image":0,"video":0,"audio":0}',
            "--host": "127.0.0.1", "--port": "18080",
        }
        for field in ("tensor_parallel_size", "max_model_len", "max_num_seqs",
                      "max_num_batched_tokens", "gpu_memory_utilization", "reasoning_parser", "stream_interval"):
            expected["--" + field.replace("_", "-")] = str(serving[field])
        self.assertEqual(options, expected)
        for route, block in zip(config["routes"], blocks[2:5]):
            arguments = shlex.split(block.replace("\\\n", ""))
            self.assertEqual(arguments[:6], ["python", "-I", "-B", "-m",
                             "vllm.entrypoints.openai.api_server", "${COMMON[@]}"])
            if route["method"] is None:
                self.assertNotIn("--speculative-config", arguments)
                continue
            actual = json.loads(arguments[arguments.index("--speculative-config") + 1])
            expected_spec = {"method": route["method"], "num_speculative_tokens": route["num_speculative_tokens"],
                             "rejection_sample_method": serving["rejection_sample_method"]}
            if route["method"] == "dflash":
                expected_spec["model"] = "$MODEL_ROOT/draft"
            self.assertEqual(actual, expected_spec)

    def test_documented_client_extracts_actual_request(self):
        block = self.how_to_run_blocks("README.md")[-1]
        arguments = shlex.split(block.replace("\\\n", ""))
        code = arguments[arguments.index("-c") + 1]
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", code],
                                cwd=self.root, check=True, capture_output=True, encoding="utf-8")
        examples = validate_report.read_json(self.root / "evidence/request-examples.json")
        self.assertEqual(json.loads(result.stdout), examples[0]["request"])
        self.assertIn("http://127.0.0.1:18080/v1/chat/completions", arguments)
        self.assertIn("--data-binary", arguments)

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