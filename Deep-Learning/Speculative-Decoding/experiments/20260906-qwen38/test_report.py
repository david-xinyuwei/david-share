"""Reject drift in the public report, event lineage and evidence inventory."""

import copy
from collections import Counter
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
        for filename in validate_report.READMES:
            shutil.copyfile(TOPIC / filename, self.topic / filename)
        self.readme = self.topic / "README.md"
        self.mirror_link_targets()

    def mirror_link_targets(self):
        for filename in validate_report.READMES:
            text = (self.topic / filename).read_text(encoding="utf-8")
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

    def rewrite_readme(self, transform, filename="README.md"):
        path = self.topic / filename
        original = path.read_text(encoding="utf-8")
        changed = transform(original)
        self.assertNotEqual(changed, original)
        path.write_text(changed, encoding="utf-8")
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
        self.rewrite_readme(lambda text: text.replace("| 1 | 基线 | 53.40 | 3458.61 |", "| 1 | 基线 | 54.40 | 3458.61 |", 1), "README_CN.md")
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:RESULT_TABLE"):
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
        for filename in validate_report.READMES:
            text = (self.topic / filename).read_text(encoding="utf-8")
            for internal_content in ("run-timeline.png", "BEGIN RUN_LOG", "--timeline"):
                self.assertNotIn(internal_content, text)

    def test_replay_entry_removal_is_rejected(self):
        self.rewrite_readme(lambda text: text.replace("python experiments/20260906-qwen38/validate_report.py", "omitted", 1))
        with self.assertRaisesRegex(ValueError, "REPLAY_ENTRY_MISSING"):
            validate_report.validate(self.root)

    def test_collapsed_sections_are_rejected(self):
        for filename in validate_report.READMES:
            with self.subTest(filename=filename):
                original = self.rewrite_readme(lambda text: text + "\n<details>\n<summary>hidden</summary>\n\nbody\n\n</details>\n", filename)
                with self.assertRaisesRegex(ValueError, "COLLAPSED_SECTION_IN_READER_PAGE"):
                    validate_report.verify_local_links(self.root)
                (self.topic / filename).write_text(original, encoding="utf-8")

    def test_undocumented_repository_entry_is_rejected(self):
        orphan = self.topic / "legacy"
        orphan.mkdir()
        (orphan / "old.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "UNDOCUMENTED_REPOSITORY_ENTRY:legacy"):
            validate_report.verify_local_links(self.root)
        shutil.rmtree(orphan)
        validate_report.verify_local_links(self.root)

    def test_local_logs_and_bytecode_are_not_reader_deliverables(self):
        logs = self.topic / "logs"
        logs.mkdir()
        (logs / "server_startup.log").write_text("local runtime log\n", encoding="utf-8")
        cached = self.topic / "scripts" / "__pycache__"
        cached.mkdir(parents=True)
        (cached / "sample.pyc").write_bytes(b"bytecode fixture")
        validate_report.verify_local_links(self.root)
        (self.topic / "scripts" / "undocumented.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "UNDOCUMENTED_REPOSITORY_ENTRY:scripts"):
            validate_report.verify_local_links(self.root)

    def test_retired_adaptation_guarantees_are_rejected(self):
        for filename in validate_report.READMES:
            for claim in validate_report.RETIRED_ADAPTATION_CLAIMS:
                with self.subTest(filename=filename, claim=claim):
                    original = self.rewrite_readme(lambda text: text + "\n" + claim + "\n", filename)
                    with self.assertRaisesRegex(ValueError, "RETIRED_ADAPTATION_CLAIM"):
                        validate_report.verify_local_links(self.root)
                    (self.topic / filename).write_text(original, encoding="utf-8")

    def test_required_reader_sections_cannot_be_removed(self):
        for filename, headings in (("README.md", ("## What You Can Do With This Repository", "## Repository Layout", "## Tests and Offline Replay", "## Applicability and Fine-Tuned Models")),
                                   ("README_CN.md", ("## 你能用它做什么", "## 仓库目录", "## 测试与离线复算", "## 适用范围与微调模型"))):
            for heading in headings:
                with self.subTest(filename=filename, heading=heading):
                    original = self.rewrite_readme(lambda text: text.replace(heading + "\n", heading + " (removed)\n", 1), filename)
                    with self.assertRaises(ValueError):
                        validate_report.verify_local_links(self.root)
                    (self.topic / filename).write_text(original, encoding="utf-8")

    def test_language_switch_is_required(self):
        for filename in validate_report.READMES:
            with self.subTest(filename=filename):
                original = self.rewrite_readme(lambda text: text.replace(validate_report.LANGUAGE_SWITCH, "English", 1), filename)
                with self.assertRaisesRegex(ValueError, "LANGUAGE_SWITCH_MISSING"):
                    validate_report.verify_local_links(self.root)
                (self.topic / filename).write_text(original, encoding="utf-8")

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
            original = self.rewrite_readme(lambda text: text.replace("\n### Client Latency\n", "\n### Test Method\n", 1))
            with self.assertRaisesRegex(ValueError, "DUPLICATE_PAGE_ANCHOR:test-method"):
                validate_report.verify_local_links(self.root)
            self.readme.write_text(original, encoding="utf-8")
        with self.subTest(case="broken anchor"):
            original = self.rewrite_readme(lambda text: text.replace("(#how-to-run)", "(#how-to-run-zh)", 1))
            with self.assertRaisesRegex(ValueError, "BROKEN_PAGE_ANCHOR:how-to-run-zh"):
                validate_report.verify_local_links(self.root)
            self.readme.write_text(original, encoding="utf-8")

    def test_missing_reader_badges_are_rejected(self):
        for filename in validate_report.READMES:
            for signature in ("/badge/vLLM-", "/badge/GPU-", "/speculative-decoding-ci.yml/badge.svg"):
                with self.subTest(filename=filename, badge=signature):
                    original = self.rewrite_readme(lambda text: "".join(line for line in text.splitlines(keepends=True) if signature not in line), filename)
                    with self.assertRaisesRegex(ValueError, "READER_BADGE_MISSING"):
                        validate_report.verify_local_links(self.root)
                    (self.topic / filename).write_text(original, encoding="utf-8")

    def test_internal_report_maintenance_is_rejected(self):
        for filename in validate_report.READMES:
            with self.subTest(filename=filename):
                original = self.rewrite_readme(lambda text: text + "\npython validate_report.py --refresh\n", filename)
                with self.assertRaisesRegex(ValueError, "INTERNAL_MAINTENANCE_IN_READER_PAGE"):
                    validate_report.verify_local_links(self.root)
                (self.topic / filename).write_text(original, encoding="utf-8")

    def test_test_flow_cannot_be_removed(self):
        for filename, language in (("README.md", "en"), ("README_CN.md", "cn")):
            with self.subTest(filename=filename):
                original = self.rewrite_readme(lambda text: re.sub(r"!\[[^\]]*\]\([^)]*test-flow-" + language + r"\.png\)", "", text), filename)
                with self.assertRaisesRegex(ValueError, "TEST_FLOW_MISSING"):
                    validate_report.verify_local_links(self.root)
                (self.topic / filename).write_text(original, encoding="utf-8")

    def how_to_run_blocks(self, filename):
        text = (self.topic / filename).read_text(encoding="utf-8")
        heading = "启动与调用" if filename == "README_CN.md" else "How to Run"
        self.assertEqual(text.count(f"\n## {heading}\n"), 1)
        section = text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
        adaptation = "复现再适配" if filename == "README_CN.md" else "Reproducing the Adaptation"
        section = section.split(f"\n### {adaptation}\n", 1)[0]
        blocks = re.findall(r"```bash\n(.*?)\n```", section, re.S)
        self.assertEqual(len(blocks), 6)
        self.assertIn(f"experiments/{self.root.name}/evidence/request-examples.json", blocks[-1])
        return blocks

    def test_how_to_run_matches_recorded_launch_contract(self):
        blocks = self.how_to_run_blocks("README.md")
        self.assertEqual(blocks, self.how_to_run_blocks("README_CN.md"))
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


class ReaderLayoutTests(unittest.TestCase):
    def test_training_diagram_cannot_disappear_or_revert_to_inline(self):
        text = (TOPIC / "README.md").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "TRAINING_FLOW_IMAGE_MISSING"):
            validate_report.verify_reader_workflows(text.replace("training-flow-en.png", "omitted.png"), False)
        with self.assertRaisesRegex(ValueError, "RETIRED_INLINE_TRAINING_DIAGRAM"):
            validate_report.verify_reader_workflows(text + '\n```mermaid\ntraining_data["old"]\n```\n', False)

    def test_actual_input_is_visible_before_results(self):
        validate_report.verify_local_links(ROOT)
        samples = validate_report.read_json(ROOT / "evidence/request-examples.json")
        sample = next(record for record in samples if record["dataset"] == "humaneval_plus")
        example = next(line.strip() for line in sample["request"]["messages"][0]["content"].splitlines()
                       if line.strip().startswith("search("))
        for filename, chinese in validate_report.READMES.items():
            text = (TOPIC / filename).read_text(encoding="utf-8")
            section = text.split("## " + validate_report.reader_titles(chinese)[3] + "\n", 1)[1]
            self.assertIn(example, section.split("\n|", 1)[0])

    def test_reorganization_is_idempotent_and_preserves_code_and_images(self):
        for filename, chinese in validate_report.READMES.items():
            original = (TOPIC / filename).read_text(encoding="utf-8")
            arranged = validate_report.arrange_report(original, chinese)
            self.assertEqual(arranged, validate_report.arrange_report(arranged, chinese))
            for pattern in (r"^```[^\n]*\n.*?^```", r"!\[[^\]]*\]\([^)]+\)"):
                self.assertEqual(Counter(re.findall(pattern, original, re.M | re.S)),
                                 Counter(re.findall(pattern, arranged, re.M | re.S)))
            validate_report.verify_reader_workflows(arranged, chinese)

    def test_client_cannot_be_appended_to_blocking_server(self):
        text = validate_report.arrange_report((TOPIC / "README.md").read_text(encoding="utf-8"), False)
        text = text.replace("export ROUTE=baseline", "export ROUTE=baseline\npython -m vllm.entrypoints.openai.api_server")
        with self.assertRaisesRegex(ValueError, "SERVER_CLIENT_IN_SAME_BLOCK"):
            validate_report.verify_reader_workflows(text, False)

    def test_selector_training_command_cannot_disappear(self):
        text = validate_report.arrange_report((TOPIC / "README.md").read_text(encoding="utf-8"), False)
        with self.assertRaisesRegex(ValueError, "ADAPTATION_COMMAND_MISSING:--train-selector"):
            validate_report.verify_reader_workflows(text.replace("--train-selector", ""), False)

    def test_reader_order_cannot_regress(self):
        text = validate_report.arrange_report((TOPIC / "README.md").read_text(encoding="utf-8"), False)
        text = text.replace("## How to Run", "## Undocumented Workflow", 1)
        with self.assertRaisesRegex(ValueError, "READER_SECTION_ORDER"):
            validate_report.verify_reader_workflows(text, False)


if __name__ == "__main__":
    unittest.main()