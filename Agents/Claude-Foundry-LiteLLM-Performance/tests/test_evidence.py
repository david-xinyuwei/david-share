import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import analyze
import render_docs


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = analyze.read_json(ROOT / "evidence/requests.json")
        cls.matrix = analyze.read_json(ROOT / "data/matrix.json")

    def test_full_evidence_and_hashes(self):
        result = analyze.validate()
        self.assertEqual(result["requests"], 50)
        self.assertEqual(result["configurations"], 10)
        self.assertAlmostEqual(result["costUsd"], 0.78989513, places=10)

    def test_missing_turn_rejected(self):
        with self.assertRaisesRegex(ValueError, "fifty"):
            analyze.validate_records(self.records[:-1], self.matrix)

    def test_changed_token_denominator_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["measurement"]["totalInputTokens"] += 1
        with self.assertRaisesRegex(ValueError, "denominator"):
            analyze.validate_records(altered, self.matrix)

    def test_changed_question_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["request"]["messages"][-1]["content"] += " altered"
        with self.assertRaisesRegex(ValueError, "History or questions"):
            analyze.validate_records(altered, self.matrix)

    def test_mode_mismatch_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["providerRequest"]["thinking"]["type"] = "disabled"
        with self.assertRaisesRegex(ValueError, "Thinking mode"):
            analyze.validate_records(altered, self.matrix)

    def test_invalid_timing_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["measurement"]["firstSseSeconds"] = 999
        with self.assertRaisesRegex(ValueError, "Timing order"):
            analyze.validate_records(altered, self.matrix)

    def test_disabled_has_no_thinking(self):
        disabled = [record for record in self.records if record["measurement"]["thinking"] != "adaptive"]
        self.assertEqual(len(disabled), 20)
        self.assertTrue(all(record["response"]["usage"]["output_tokens_details"]["thinking_tokens"] == 0 for record in disabled))

    def test_rendered_pages_match_generator(self):
        for name, content in render_docs.pages(analyze.validate()).items():
            self.assertEqual((ROOT / name).read_text(encoding="utf-8"), content.rstrip() + "\n", name)

    def test_readme_sections_and_opening(self):
        for filename, expected, author in (
                ("README.md", ["Purpose", "Results", "Steps"], "Author: Xinyu Wei · [中文](README_CN.md)"),
                ("README_CN.md", ["目的", "实现效果", "操作步骤"], "作者：魏新宇 · [English](README.md)")):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"^## (.+)$", text, re.MULTILINE), expected)
            self.assertNotIn("<details", text)
            badges = re.findall(r"^\[!\[(\w+)\]", text, re.MULTILINE)
            self.assertEqual(badges, ["Models", "Measured", "CI"])
            self.assertIn("actions/workflows/claude-foundry-performance-ci.yml/badge.svg", text)
            self.assertIn("\n" + author + "\n", text)
            self.assertIn("call_once.py", text)
            steps = text.split("\n## " + expected[2] + "\n", 1)[1]
            self.assertTrue(steps.lstrip().startswith("**"))
            self.assertLess(steps.index("| 1 |"), steps.index("```bash"))
            for retired in ("Stars belong", "ENV_BUILD_STATUS", "This repair", "USD 3", "architecture-"):
                self.assertNotIn(retired, text)

    def test_bilingual_commands_and_complete_result_tables(self):
        for page, fences in (("README{}.md", ("bash",)), ("docs/testing{}.md", ("bash", "powershell"))):
            english = (ROOT / page.format("")).read_text(encoding="utf-8")
            chinese = (ROOT / page.format("_CN")).read_text(encoding="utf-8")
            for fence in fences:
                blocks = re.findall(rf"```{fence}\n(.*?)\n```", english, re.DOTALL)
                self.assertTrue(blocks, page)
                self.assertEqual(blocks, re.findall(rf"```{fence}\n(.*?)\n```", chinese, re.DOTALL), page)
        testing = (ROOT / "docs/testing.md").read_text(encoding="utf-8")
        for command in ("./scripts/run_matrix.ps1", "./scripts/check_gateway.ps1",
                        "--run-directory $run --trace-file $traceFile", "EXECUTED_PENDING_PROVIDER_TRACE_AUDIT"):
            self.assertIn(command, testing)
        result = analyze.validate()
        for suffix, heading in (("", "## Gateway test, 2026-10-24"), ("_CN", "## 网关测试")):
            text = (ROOT / f"docs/results{suffix}.md").read_text(encoding="utf-8")
            gateway = text.split("\n" + heading + "\n", 1)[1]
            self.assertEqual(len(re.findall(r"^#### ", gateway, re.MULTILINE)), 10)
            for case_id, group in result["groups"].items():
                self.assertIn(f"`{case_id}`", gateway)
                for row in group["rows"]:
                    self.assertIn(f'| {row["turn"]} | {row["ttftSeconds"]:.3f} | {row["e2eSeconds"]:.3f} |', gateway)
                    self.assertIn(f'| {row["turn"]} | {row["totalInputTokens"]} | {row["cacheReadTokens"]} | {row["cacheWriteTokens"]} |', gateway)
        for path in list(ROOT.glob("README*.md")) + list((ROOT / "docs").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(all(line.count("|") <= 7 for line in text.splitlines() if line.startswith("|")), path.name)

    def test_links_and_images_exist(self):
        for path in list(ROOT.glob("README*.md")) + list((ROOT / "docs").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            links = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'src="([^"]+)"', text)
            for link in links:
                if urlparse(link).scheme or link.startswith("#"):
                    continue
                target = path.parent / unquote(link.split("#", 1)[0])
                self.assertTrue(target.exists(), f"{path.name}: {link}")

    def test_inputs_precede_result_tables(self):
        for suffix, heading in (("", "## Gateway test, 2026-10-24"), ("_CN", "## 网关测试")):
            text = (ROOT / f"docs/results{suffix}.md").read_text(encoding="utf-8")
            before_gateway, gateway = text.split("\n" + heading + "\n", 1)
            coding_heading = "## 编码矩阵" if suffix else "## Coding matrix, 2026-10-26"
            aca, coding = before_gateway.split("\n" + coding_heading + "\n", 1)
            sections = ((aca, ['"cache_control"', '"max_tokens": 128000', '"ttl": "1h"']),
                        (coding, ["Act as an expert software developer."]), (gateway, self.matrix["questions"]))
            for section, inputs in sections:
                first_table = re.search(r"^\|.+\|$", section, re.MULTILINE)
                self.assertIsNotNone(first_table, suffix)
                for item in inputs:
                    self.assertIn(item, section)
                    self.assertLess(section.index(item), first_table.start())

    def test_public_identity_and_signature_boundary(self):
        private = "|".join(["ts" + "mc", "5303" + "9473", "16b3" + "c013", "926f" + "20f5", "ai-hub" + r"eastus\d+",
                            r"(?<!david-)xinyu" + "wei", r"20\.96\." + r"14\.\d+", r"161\.115\." + r"118\.\d+",
                            "/home/" + "azureuser"])
        forbidden = re.compile(r"[A-Z]:[\\/]+(?:Users|AI-Super-Agent)[\\/]|@microsoft\.com|https://(?!YOUR-FOUNDRY-RESOURCE\.|<foundry-resource>\.)[a-z0-9-]+\.(?:services\.ai\.azure\.com|azurecontainerapps\.io|openai\.azure\.com)|\b(?:ghp_[a-z0-9]{20,}|sk-[a-z0-9]{20,})|" + private, re.IGNORECASE)
        skipped = {"live-runs", "private", "tests", "__pycache__", "runs"}
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix not in {".png", ".pyc"} and not skipped & set(path.relative_to(ROOT).parts):
                text = path.read_text(encoding="utf-8", errors="replace")
                if path.relative_to(ROOT).as_posix() == "evidence/gateway-score-20261027/dataset.json":
                    import hashlib

                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "0035f4153351fe0e91fdd52447c5bcd12fbac867ee6b1977192cd6e2f35959de")
                    text = text.replace(r"C:\\Users\\E\\Desktop\\sympy-master", "PUBLIC_SYMPY_ISSUE_PATH")
                match = forbidden.search(text)
                self.assertIsNone(match, f"{path.relative_to(ROOT)}: {match.group(0) if match else ''}")
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "signature":
                        self.assertIn(child, ("", "[signature omitted]"))
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(self.records)


class RunAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "live-runs"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="audit-test-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name)
        matrix_path = self.run / "matrix.json"
        shutil.copyfile(ROOT / "data/matrix.json", matrix_path)
        matrix_hash = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
        frozen = self.run / "source/scripts/invoke_case.ps1"
        frozen.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/invoke_case.ps1", frozen)
        self.case_id = "opus-adaptive-system"
        self.records = [record for record in analyze.read_json(ROOT / "evidence/requests.json")
                        if record["measurement"]["caseId"] == self.case_id]
        state = {"status": "EXECUTED_PENDING_PROVIDER_TRACE_AUDIT", "selectedCases": [self.case_id],
                 "completedCases": [self.case_id], "failedCases": [], "matrixSha256": matrix_hash,
                 "runnerSha256": hashlib.sha256(frozen.read_bytes()).hexdigest()}
        self.save("run.json", state)
        traces = []
        for item in self.records:
            row = item["measurement"]
            response = item["response"]
            message = copy.deepcopy(response)
            message["content"] = []
            events = [{"type": "message_start", "message": message}]
            for index, block in enumerate(response["content"]):
                initial = copy.deepcopy(block)
                fields = [field for field in ("text", "thinking", "signature") if field in initial]
                for field in fields:
                    initial[field] = ""
                events.append({"type": "content_block_start", "index": index, "content_block": initial})
                for field in fields:
                    events.append({"type": "content_block_delta", "index": index,
                                   "delta": {"type": field + "_delta", field: block[field]}})
                events.append({"type": "content_block_stop", "index": index})
            events.extend([{"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                            "usage": copy.deepcopy(response["usage"])}, {"type": "message_stop"}])
            raw = {
                "status": "CAPTURED", "httpStatus": 200, "matrixCaseId": self.case_id,
                "label": f'{self.case_id}-turn-{row["turn"]}', "request": item["request"], "response": response,
                "headers": {"x-litellm-call-id": [row["callId"]]}, "sourceHashes": {"matrix": matrix_hash},
                "messageStopReceived": True, "messageStopSeconds": item["messageStopSeconds"],
                "sseEvents": events, "sseWireLines": ["data: " + json.dumps(event) for event in events],
                "responseHeadersSeconds": row["headersSeconds"],
                "firstBodyByteSeconds": row["firstBodyByteSeconds"], "firstSseEventSeconds": row["firstSseSeconds"],
                "firstVisibleTextSeconds": row["ttftSeconds"], "elapsedSeconds": row["e2eSeconds"],
                "pricingUsdPerMillionTokens": item["prices"], "estimatedModelCostUsd": row["estimatedCostUsd"],
            }
            self.set_event_timings(raw)
            self.save(f'ACA_HTTP_{raw["label"]}.json', raw)
            traces.append(dict(item["providerRequest"], stage="pre_api_call", capture="PROVIDER_REQUEST_FIELDS"))
        self.trace_path = self.run / "provider-traces.json"
        self.save(self.trace_path.name, traces)

    def save(self, name, value):
        (self.run / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def set_event_timings(record):
        events = record["sseEvents"]
        text_index = next(index for index, event in enumerate(events)
                          if event["type"] == "content_block_delta" and event["delta"].get("text"))
        timestamps = []
        for index, event in enumerate(events):
            if index == text_index:
                elapsed = record["firstVisibleTextSeconds"]
            elif index == len(events) - 1:
                elapsed = record["messageStopSeconds"]
            elif index < text_index:
                elapsed = record["firstSseEventSeconds"] + index / text_index * (record["firstVisibleTextSeconds"] - record["firstSseEventSeconds"])
            else:
                elapsed = record["firstVisibleTextSeconds"] + (index - text_index) / (len(events) - 1 - text_index) * (record["messageStopSeconds"] - record["firstVisibleTextSeconds"])
            timestamps.append({"event": index, "type": event["type"], "elapsedSeconds": elapsed})
            if event["type"] == "content_block_start" and event["content_block"]["type"] == "thinking":
                record["firstThinkingEventSeconds"] = elapsed
            if event["type"] == "content_block_delta" and event["delta"]["type"] == "signature_delta":
                record["firstSignatureSeconds"] = elapsed
        record["eventTimings"] = timestamps

    def test_selected_raw_run_and_output_files(self):
        result = analyze.analyze_run(self.run, [self.trace_path])
        self.assertEqual(result["requests"], 5)
        self.assertEqual(result["configurations"], 1)
        self.assertEqual(result["run"], self.run.name)
        expected_cost = sum(record["measurement"]["estimatedCostUsd"] for record in self.records)
        self.assertAlmostEqual(result["costUsd"], expected_cost, places=12)
        analyze.write_run_outputs(self.run, result)
        self.assertEqual(analyze.read_json(self.run / "analysis.json")["run"], self.run.name)
        self.assertIn(self.run.name, (self.run / "analysis.md").read_text(encoding="utf-8"))

    def test_new_run_inputs_change_the_result(self):
        before = analyze.analyze_run(self.run, [self.trace_path])
        for path in self.run.glob("ACA_HTTP_*.json"):
            record = analyze.read_json(path)
            record["firstVisibleTextSeconds"] = record["firstSseEventSeconds"] + 0.01
            self.set_event_timings(record)
            self.save(path.name, record)
        after = analyze.analyze_run(self.run, [self.trace_path])
        self.assertNotEqual(before["groups"][self.case_id]["ttftSeconds"]["p50"],
                            after["groups"][self.case_id]["ttftSeconds"]["p50"])

    def test_missing_trace_and_wrong_provider_rejected(self):
        traces = analyze.read_json(self.trace_path)
        self.save(self.trace_path.name, traces[:-1])
        with self.assertRaisesRegex(ValueError, "Missing provider trace"):
            analyze.analyze_run(self.run, [self.trace_path])
        traces[0]["model"] = "incorrect-model"
        self.save(self.trace_path.name, traces)
        with self.assertRaisesRegex(ValueError, "Provider model"):
            analyze.analyze_run(self.run, [self.trace_path])

    def test_conflicting_duplicate_trace_rejected(self):
        traces = analyze.read_json(self.trace_path)
        traces.append(dict(traces[0], model="incorrect-model"))
        self.save(self.trace_path.name, traces)
        with self.assertRaisesRegex(ValueError, "Conflicting provider"):
            analyze.analyze_run(self.run, [self.trace_path])

    def test_missing_turn_and_duplicate_request_rejected(self):
        path = next(self.run.glob("ACA_HTTP_*.json"))
        record = analyze.read_json(path)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete selected"):
            analyze.analyze_run(self.run, [self.trace_path])
        self.save(path.name, record)
        self.save("ACA_HTTP_duplicate.json", record)
        with self.assertRaisesRegex(ValueError, "Incomplete selected"):
            analyze.analyze_run(self.run, [self.trace_path])

    def test_failed_or_truncated_stream_rejected(self):
        path = next(self.run.glob("ACA_HTTP_*.json"))
        original = analyze.read_json(path)
        for change in ("http", "stop", "usage", "mode", "ttft", "stop_reason", "block_stop"):
            with self.subTest(change=change):
                record = copy.deepcopy(original)
                if change == "http":
                    record["httpStatus"] = 503
                elif change == "stop":
                    record["sseEvents"] = record["sseEvents"][:-1]
                    record["sseWireLines"] = record["sseWireLines"][:-1]
                    record["eventTimings"] = record["eventTimings"][:-1]
                elif change == "usage":
                    record["response"]["usage"]["output_tokens"] += 1
                elif change == "mode":
                    record["request"]["thinking"]["type"] = "disabled"
                elif change == "ttft":
                    record["firstVisibleTextSeconds"] = record["firstSseEventSeconds"] + 0.01
                else:
                    if change == "stop_reason":
                        record["sseEvents"][-2]["delta"]["stop_reason"] = "max_tokens"
                    else:
                        next(event for event in record["sseEvents"] if event["type"] == "content_block_stop")["index"] = 99
                    record["sseWireLines"] = ["data: " + json.dumps(event) for event in record["sseEvents"]]
                self.save(path.name, record)
                with self.assertRaises(ValueError):
                    analyze.analyze_run(self.run, [self.trace_path])

    def test_console_log_input(self):
        traces = analyze.read_json(self.trace_path)
        path = self.run / "console.jsonl"
        path.write_text("\n".join(json.dumps({"Log": "CLAUDE_PROVIDER_TRACE " + json.dumps(trace)})
                                  for trace in traces), encoding="utf-8")
        self.assertEqual(analyze.analyze_run(self.run, [path])["providerCalls"], 5)

    def test_cli_check_does_not_write_or_fallback(self):
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/analyze.py"),
                                    "--run-directory", str(self.run), "--trace-file", str(self.trace_path), "--check"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["requests"], 5)
        self.assertFalse((self.run / "analysis.json").exists())


class RunnerTests(unittest.TestCase):
    def test_public_collector_stream_and_failure_records(self):
        pwsh = shutil.which("pwsh")
        if not pwsh:
            self.skipTest("PowerShell 7 is required for collector tests")
        scratch = ROOT / "live-runs"
        scratch.mkdir(exist_ok=True)
        for scenario in ("complete", "http_error", "truncated", "missing_usage"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(prefix="collector-test-", dir=scratch) as temporary:
                received = []

                class TestHandler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                        received.append(payload)
                        if scenario == "http_error":
                            body = json.dumps({"error": {"type": "test_only", "message": "unavailable"}}).encode("utf-8")
                            status = 503
                        else:
                            usage = {"input_tokens": 10, "cache_creation_input_tokens": 0,
                                     "cache_read_input_tokens": 0, "output_tokens": 3,
                                     "output_tokens_details": {"thinking_tokens": 0}, "speed": "standard",
                                     "cache_creation": {"ephemeral_1h_input_tokens": 0}}
                            if scenario == "missing_usage":
                                del usage["cache_read_input_tokens"]
                            events = [
                                {"type": "message_start", "message": {"id": "test-only", "type": "message",
                                    "role": "assistant", "model": payload["model"], "content": [],
                                    "stop_reason": None, "usage": usage}},
                                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "test-only response"}},
                                {"type": "content_block_stop", "index": 0},
                                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": usage},
                            ]
                            if scenario != "truncated":
                                events.append({"type": "message_stop"})
                            body = "".join("data: " + json.dumps(event) + "\n\n" for event in events).encode("utf-8")
                            status = 200
                        self.send_response(status)
                        self.send_header("Content-Type", "text/event-stream" if status == 200 else "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("x-litellm-call-id", f"test-only-{len(received)}")
                        self.end_headers()
                        self.wfile.write(body)

                server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                environment = dict(os.environ, CLAUDE_GATEWAY_URL=f"http://127.0.0.1:{server.server_port}",
                                   CLAUDE_GATEWAY_KEY="test-only", COLLECTOR_SCRIPT=str(ROOT / "scripts/invoke_case.ps1"),
                                   COLLECTOR_MATRIX=str(ROOT / "data/matrix.json"), COLLECTOR_RUN=temporary)
                try:
                    result = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command",
                        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                        "$OutputEncoding=[Console]::OutputEncoding; "
                        "& $env:COLLECTOR_SCRIPT -Case matrix -CaseId haiku-disabled-system "
                        "-Label haiku-disabled-system -MatrixPath $env:COLLECTOR_MATRIX -RunDirectory $env:COLLECTOR_RUN"],
                        env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                paths = sorted(Path(temporary).glob("ACA_HTTP_*.json"))
                self.assertEqual(len(paths), 5 if scenario == "complete" else 1)
                self.assertEqual(len(received), len(paths))
                records = [analyze.read_json(path) for path in paths]
                if scenario == "complete":
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    for index, record in enumerate(records):
                        analyze.validate_stream(record)
                        self.assertEqual(record["response"]["content"], [{"type": "text", "text": "test-only response"}])
                        self.assertEqual(len(record["request"]["messages"]), index * 2 + 1)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(records[0]["status"], "CAPTURED")
                    if scenario == "http_error":
                        self.assertEqual(records[0]["httpStatus"], 503)
                    elif scenario == "truncated":
                        self.assertFalse(records[0]["messageStopReceived"])
                    else:
                        self.assertIsNone(records[0]["estimatedModelCostUsd"])

    def test_gateway_check_rejects_missing_models_and_insecure_url(self):
        pwsh = shutil.which("pwsh")
        if not pwsh:
            self.skipTest("PowerShell 7 is required for gateway checks")
        environment = dict(os.environ, GATEWAY_CHECK_SCRIPT=str(ROOT / "scripts/check_gateway.ps1"),
                           CLAUDE_GATEWAY_KEY="test-only")
        for scenario, expected_code in (("ready", 0), ("missing", 1), ("http", 1)):
            with self.subTest(scenario=scenario):
                environment["GATEWAY_TEST_SCENARIO"] = scenario
                command = (
                    "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                    "$OutputEncoding=[Console]::OutputEncoding; "
                    "function Invoke-RestMethod { "
                    "if ($env:GATEWAY_TEST_SCENARIO -eq 'missing') { return @{data=@(@{id='opus55-standard'})} }; "
                    "return @{data=@(@{id='opus55-standard'},@{id='sonnet55-standard'},@{id='haiku55-standard'})} }; "
                    "$url=if($env:GATEWAY_TEST_SCENARIO -eq 'http'){'http://unused.invalid'}else{'https://unused.invalid'}; "
                    "& $env:GATEWAY_CHECK_SCRIPT -GatewayUrl $url"
                )
                result = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
                                        env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
                if not expected_code:
                    self.assertEqual(json.loads(result.stdout)["modelInvocation"], "NOT_RUN")

    def test_initialization_uses_powershell_location(self):
        pwsh = shutil.which("pwsh")
        if not pwsh:
            self.skipTest("PowerShell 7 is required for public runner tests")
        scratch = ROOT / "live-runs"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="path-test-", dir=scratch) as temporary:
            parent = Path(temporary)
            project = parent / "project with spaces [test]"
            (project / "scripts").mkdir(parents=True)
            (project / "data").mkdir()
            shutil.copyfile(ROOT / "scripts/run_matrix.ps1", project / "scripts/run_matrix.ps1")
            (project / "data/matrix.json").write_text(
                json.dumps({"budgetUsd": 50, "cases": [{"id": "path-test"}]}), encoding="utf-8"
            )
            (project / "scripts/invoke_case.ps1").write_text(
                "param($Case,$CaseId,$Label,$MatrixPath,$RunDirectory,[switch]$ValidateOnly)\n"
                "$ErrorActionPreference='Stop'\n"
                "$value=@{matrix=$MatrixPath;output=$RunDirectory}|ConvertTo-Json\n"
                "[IO.File]::WriteAllText((Join-Path $RunDirectory 'paths.json'),$value,[Text.Encoding]::UTF8)\n",
                encoding="utf-8",
            )
            environment = dict(os.environ, TEST_SCENARIO_ROOT=str(project),
                               CLAUDE_GATEWAY_URL="https://unused.invalid", CLAUDE_GATEWAY_KEY="test-only")
            completed = subprocess.run(
                [pwsh, "-NoProfile", "-NonInteractive", "-Command",
                 "Set-Location -LiteralPath $env:TEST_SCENARIO_ROOT; "
                 "& ./scripts/run_matrix.ps1 -MatrixPath data/matrix.json -RunDirectory 'live-runs/[path probe]'"],
                cwd=parent, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            output = project / "live-runs/[path probe]"
            paths = json.loads((output / "paths.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(Path(paths["output"]), output)
            self.assertEqual(Path(paths["matrix"]), output / "matrix.json")
            self.assertFalse((parent / "live-runs").exists())
            state = json.loads((output / "run.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(state["completedCases"], ["path-test"])


if __name__ == "__main__":
    unittest.main()