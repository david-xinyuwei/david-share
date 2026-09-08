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
from urllib.parse import unquote, urlsplit

import validate_report


ROOT = Path(__file__).resolve().parent
TOPIC = ROOT.parent.parent


class ReportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "topic" / "experiments" / ROOT.name
        self.topic = self.root.parent.parent
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "regenerated"))
        shutil.copyfile(TOPIC / validate_report.README, self.topic / validate_report.README)
        self.readme = self.topic / validate_report.README
        self.mirror_link_targets()

    def mirror_link_targets(self):
        text = self.readme.read_text(encoding="utf-8")
        for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = urlsplit(link)
            if target.scheme or link.startswith("#"):
                continue
            relative = unquote(target.path)
            source, destination = TOPIC / relative, self.topic / relative
            if destination.exists() or not source.exists():
                continue
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

    def rewrite_readme(self, transform):
        original = self.readme.read_text(encoding="utf-8")
        changed = transform(original)
        self.assertNotEqual(changed, original)
        self.readme.write_text(changed, encoding="utf-8")
        return original

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
        self.rewrite_readme(lambda text: text.replace("150.51", "151.51"))
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:RESULT_TABLE"):
            validate_report.validate(self.root)

    def test_duplicate_block_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE_REPORT_BLOCK"):
            validate_report.generated_block("<!-- BEGIN RESULT_TABLE -->" * 2 + "<!-- END RESULT_TABLE -->", "RESULT_TABLE", "", refresh=False)

    def test_counterexample_ratio_drift_is_rejected(self):
        self.rewrite_readme(lambda text: text.replace("0.8713", "1.1640"))
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:COUNTEREXAMPLE"):
            validate_report.validate(self.root)

    def test_chinese_tables_are_validated_separately(self):
        original = self.readme.read_text(encoding="utf-8")
        start = original.index("<!-- BEGIN RESULT_TABLE_CN -->")
        self.assertIn("| 1 | 基线 | 53.40 | 3458.61 |", original[start:])
        self.readme.write_text(original[:start] + original[start:].replace("| 1 | 基线 | 53.40 |", "| 1 | 基线 | 54.40 |", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:RESULT_TABLE_CN"):
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
        text = self.readme.read_text(encoding="utf-8")
        for internal_content in ("run-timeline.png", "BEGIN RUN_LOG", "--timeline"):
            self.assertNotIn(internal_content, text)

    def test_replay_entry_removal_is_rejected(self):
        self.rewrite_readme(lambda text: text.replace("python experiments/20260906-qwen38/validate_report.py", "omitted", 1))
        with self.assertRaisesRegex(ValueError, "REPLAY_ENTRY_MISSING"):
            validate_report.validate(self.root)

    def test_nested_markdown_is_rejected(self):
        nested = self.root / "NOTES.md"
        nested.write_text("# nested\n", encoding="utf-8")
        with self.subTest(case="file"):
            with self.assertRaisesRegex(ValueError, "NESTED_MARKDOWN_FILE"):
                validate_report.verify_local_links(self.root)
        with self.subTest(case="link"):
            original = self.rewrite_readme(lambda text: text + "\n[notes](experiments/20260906-qwen38/NOTES.md)\n")
            with self.assertRaisesRegex(ValueError, "NESTED_MARKDOWN_LINK"):
                validate_report.verify_local_links(self.root)
            self.readme.write_text(original, encoding="utf-8")
        nested.unlink()
        validate_report.verify_local_links(self.root)

    def test_page_anchor_conflicts_are_rejected(self):
        with self.subTest(case="duplicate heading"):
            original = self.rewrite_readme(lambda text: text.replace("\n## 测试方法\n", "\n## Test Method\n", 1))
            with self.assertRaisesRegex(ValueError, "DUPLICATE_PAGE_ANCHOR:test-method"):
                validate_report.verify_local_links(self.root)
            self.readme.write_text(original, encoding="utf-8")
        with self.subTest(case="broken anchor"):
            original = self.rewrite_readme(lambda text: text.replace("(#how-to-run-cn)", "(#how-to-run-zh)", 1))
            with self.assertRaisesRegex(ValueError, "BROKEN_PAGE_ANCHOR:how-to-run-zh"):
                validate_report.verify_local_links(self.root)
            self.readme.write_text(original, encoding="utf-8")
        with self.subTest(case="chinese entry"):
            original = self.rewrite_readme(lambda text: text.replace("[中文](#chinese)", "中文", 1))
            with self.assertRaisesRegex(ValueError, "CHINESE_SECTION_ENTRY_MISSING"):
                validate_report.verify_local_links(self.root)
            self.readme.write_text(original, encoding="utf-8")

    def test_missing_reader_badges_are_rejected(self):
        for signature in ("/badge/vLLM-", "/badge/GPU-", "/speculative-decoding-ci.yml/badge.svg"):
            with self.subTest(badge=signature):
                original = self.rewrite_readme(lambda text: "".join(line for line in text.splitlines(keepends=True) if signature not in line))
                with self.assertRaisesRegex(ValueError, "READER_BADGE_MISSING"):
                    validate_report.verify_local_links(self.root)
                self.readme.write_text(original, encoding="utf-8")

    def test_internal_report_maintenance_is_rejected(self):
        original = self.rewrite_readme(lambda text: text + "\npython validate_report.py --refresh\n")
        with self.assertRaisesRegex(ValueError, "INTERNAL_MAINTENANCE_IN_READER_PAGE"):
            validate_report.verify_local_links(self.root)
        self.readme.write_text(original, encoding="utf-8")

    def test_stage_durations_cannot_be_hidden(self):
        for heading in ("### Measured Duration by Stage", "### 各阶段测试耗时"):
            with self.subTest(heading=heading):
                def hide(text):
                    section = heading + text.split(heading, 1)[1].split("\n<a id=", 1)[0]
                    return text.replace(section, "<details>\n<summary>Stage durations</summary>\n\n" + section + "\n</details>\n")
                original = self.rewrite_readme(hide)
                with self.assertRaisesRegex(ValueError, "STAGE_DURATIONS_COLLAPSED"):
                    validate_report.verify_local_links(self.root)
                self.readme.write_text(original, encoding="utf-8")

    def test_customer_value_section_cannot_be_removed(self):
        for heading in ("## What You Can Do With This Repository", "## 你能用它做什么"):
            with self.subTest(heading=heading):
                original = self.rewrite_readme(lambda text: text.replace(heading, "## " + heading[3:].upper() + " (removed)"))
                with self.assertRaisesRegex(ValueError, "CUSTOMER_VALUE_ENTRY_MISSING"):
                    validate_report.verify_local_links(self.root)
                self.readme.write_text(original, encoding="utf-8")

    def test_test_flow_cannot_be_removed(self):
        for language in ("en", "cn"):
            with self.subTest(language=language):
                original = self.rewrite_readme(lambda text: re.sub(r"!\[[^\]]*\]\([^)]*test-flow-" + language + r"\.png\)", "", text))
                with self.assertRaisesRegex(ValueError, "TEST_FLOW_MISSING"):
                    validate_report.verify_local_links(self.root)
                self.readme.write_text(original, encoding="utf-8")

    def how_to_run_blocks(self, chinese):
        text = self.readme.read_text(encoding="utf-8")
        heading = "启动与调用" if chinese else "How to Run"
        self.assertEqual(text.count(f"\n## {heading}\n"), 1)
        if chinese:
            self.assertIn('<a id="how-to-run-cn"></a>', text)
        section = text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
        blocks = re.findall(r"```bash\n(.*?)\n```", section, re.S)
        self.assertEqual(len(blocks), 6)
        self.assertIn(f"experiments/{self.root.name}/evidence/request-examples.json", blocks[-1])
        return blocks

    def test_how_to_run_matches_recorded_launch_contract(self):
        blocks = self.how_to_run_blocks(False)
        self.assertEqual(blocks, self.how_to_run_blocks(True))
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
        block = self.how_to_run_blocks(False)[-1]
        arguments = shlex.split(block.replace("\\\n", ""))
        code = arguments[arguments.index("-c") + 1]
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", code],
                                cwd=self.topic, check=True, capture_output=True, encoding="utf-8")
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