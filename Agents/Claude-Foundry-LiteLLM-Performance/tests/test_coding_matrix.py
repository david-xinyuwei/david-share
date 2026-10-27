import hashlib
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
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODING = ROOT / "coding-matrix"
EV = ROOT / "evidence/coding-matrix-20261026"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.append(str(CODING))
import coding_data  # noqa: E402
import judge  # noqa: E402
import render_coding  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coding_analyze = load("coding_analyze", CODING / "analyze.py")
prepare = load("coding_prepare", CODING / "prepare.py")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(*args):
    return subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", timeout=300)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = coding_data.load()

    def test_facts_recompute_from_the_records(self):
        for script, run_dir in (("analyze.py", "matrix"), ("cache_analyze.py", "cache")):
            result = run(CODING / script, "--run-dir", EV / run_dir, "--check")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_tampered_record_fails_the_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "matrix"
            shutil.copytree(EV / "matrix", copy)
            judged = copy / "judged.jsonl"
            rows = judged.read_text(encoding="utf-8").splitlines()
            first = json.loads(rows[0])
            first["passed"] = not first["passed"]
            judged.write_text("\n".join([json.dumps(first)] + rows[1:]) + "\n", encoding="utf-8")
            result = run(CODING / "analyze.py", "--run-dir", copy, "--check")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("differs", result.stderr)

    def test_export_manifest_and_redactions(self):
        manifest = json.loads((EV / "_export_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["files"]), 30)
        for item in manifest["files"]:
            data = (EV / item["file"]).read_bytes()
            self.assertEqual(sha(data), item["sha256"], item["file"])
            self.assertEqual(item["identical_to_source"], item["file"] not in manifest["replaced"], item["file"])
        self.assertEqual(set(manifest["replaced"]), {"smoke/run.json", "pilot-32k/run.json", "pilot-32k/environment.txt",
                                                     "matrix/run.json", "matrix/environment.txt"})

    def test_public_scripts_match_provenance(self):
        provenance = json.loads((EV / "provenance.json").read_text(encoding="utf-8"))
        files = {p.relative_to(CODING).as_posix() for p in CODING.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        self.assertEqual(files, set(provenance["publicFiles"]))
        for name, item in provenance["publicFiles"].items():
            self.assertEqual(sha((CODING / name).read_bytes()), item["sha256"], name)
        for name in ("bench.py", "probe.py", "cache_test.py", "judge/Dockerfile", "judge/npm-test.sh", "judge/cpp-test.sh"):
            self.assertTrue(provenance["publicFiles"][name]["identical_to_measured"], name)
        for name, item in provenance["publicFiles"].items():
            if item["identical_to_measured"] is False:
                self.assertTrue(item["change"], name)

    def test_readme_step4_record_matches_the_published_client(self):
        record = json.loads((EV / "readme-step4.json").read_text(encoding="utf-8"))
        self.assertEqual((record["exit_code"], record["stderr_result"]["status"], record["stderr_result"]["http_status"]),
                         (0, "completed", 200))
        self.assertEqual(set(record["public_file_sha256"]), {"claude_api.py", "pricing.py", "call_once.py"})
        for name, digest in record["public_file_sha256"].items():
            self.assertEqual(sha((CODING / name).read_bytes()), digest, f"{name} changed after README step 4 was run")

    def test_problem_list_matches_the_measured_prompts(self):
        listed = json.loads((ROOT / "data/coding-problems.json").read_text(encoding="utf-8"))
        problems = self.d["problems"]
        self.assertEqual(len(listed["problems"]), 18)
        self.assertEqual(listed["system_prompt_sha256"], sha(problems["system_prompt"].encode("utf-8")))
        self.assertEqual(listed["system_prompt_sha256"], sha(prepare.SYSTEM_PROMPT.encode("utf-8")))
        for entry, problem in zip(listed["problems"], problems["problems"]):
            self.assertEqual(entry["id"], problem["id"])
            self.assertEqual(entry["user_message_sha256"], sha(problem["user_message"].encode("utf-8")))
        self.assertEqual({p.split("/")[0] for p in (e["id"] for e in listed["problems"])},
                         {"cpp", "go", "java", "javascript", "python", "rust"})

    def test_counts(self):
        m = coding_data.matrix_numbers(self.d)
        self.assertEqual((m["requests"], m["measured"], m["warmups"], m["completed"]), (1155, 1134, 21, 1130))
        self.assertEqual(len(self.d["cells"]), 21)
        self.assertTrue(all(c["attempted"] == 54 for c in self.d["cells"].values()))
        self.assertEqual(self.d["runs"]["probe"]["requests"], 102)
        self.assertEqual(self.d["runs"]["cache"]["requests"], 264)
        self.assertEqual(m["http"], {200: 1155})

    def test_readme_grids_match_the_facts(self):
        for name in ("README.md", "README_CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for model, mode in coding_data.ROWS:
                rows = re.findall(rf"^\| {re.escape(coding_data.NAME[model])} · `{mode}` \| (.+) \|$", text, re.MULTILINE)
                self.assertEqual(len(rows), 3, (name, model, mode))
                passes, first_text, cost = [row.split(" | ") for row in rows]
                for index, effort in enumerate(coding_data.EFFORTS):
                    cell = coding_data.cell(self.d, model, mode, effort)
                    if cell is None:
                        self.assertNotRegex(passes[index], r"\d")
                        continue
                    self.assertEqual(passes[index], f"{cell['passed']}/{cell['attempted']}")
                    self.assertEqual(first_text[index], render_coding.secs(cell["first_text_p50_s"]))
                    self.assertEqual(cost[index], render_coding.usd(cell["cost_per_1k_requests_usd"]))

    def test_support_table_covers_all_modes_and_omitted_effort(self):
        rows = render_coding.support_matrix_rows(self.d)
        self.assertEqual(len(rows), 12)
        self.assertEqual(sum(status == 200 for row in rows for status in row["efforts"].values()), 26)
        self.assertEqual(sum(row["cache_observed"] for row in rows), 5)
        for row in rows:
            self.assertEqual(tuple(row["efforts"]), (*coding_data.EFFORTS, "omitted"))
            if row["mode"] == "enabled":
                self.assertEqual(set(row["efforts"].values()), {400})

    def test_cache_table_values_use_each_model_and_scenario(self):
        values = render_coding.cache_setting_values(self.d)
        turns = coding_data.cache_numbers(self.d)["turns"]
        for model in coding_data.MODELS:
            deployment = coding_data.DEPLOYMENT[model]
            for scenario in ("auto", "system_only", "system_plus_auto"):
                shares = [turns[(deployment, scenario, turn)]["read_share"] for turn in (2, 3, 4)]
                self.assertEqual(values[model][scenario]["min"], min(shares))
                self.assertEqual(values[model][scenario]["max"], max(shares))
                self.assertEqual(values[model][scenario]["new_conversation"],
                                 turns[(deployment, scenario + "_second", 1)]["read_share"])
            self.assertEqual(values[model]["idle_5m"], 0)
            self.assertGreater(values[model]["idle_1h"], 0)

    def test_complete_table_figures_preserve_cells_and_scope(self):
        for chinese in (False, True):
            first = ET.fromstring(render_coding.support_figure(self.d, chinese))
            second = ET.fromstring(render_coding.cache_settings_figure(self.d, chinese))
            self.assertEqual(len(first.findall('.//*[@data-unsupported="true"]')), 46)
            self.assertEqual(len({node.get("data-row") for node in first.findall('.//*[@data-row]')}), 12)
            cache_cells = first.findall('.//*[@data-column="8"]')
            self.assertEqual(len(cache_cells), 12)
            self.assertTrue(all(node.get("data-unsupported") == "false" for node in cache_cells))
            self.assertEqual({"".join(node.itertext()).strip() for node in cache_cells},
                             {"适用", "不适用"} if chinese else {"Applicable", "Not applicable"})
            self.assertFalse(first.findall('.//{http://www.w3.org/2000/svg}line'))
            for node in first.findall('.//*[@data-unsupported="true"]'):
                self.assertEqual(" ".join("".join(node.itertext()).split()),
                                 "不支持" if chinese else "Not supported")
            self.assertEqual(len({node.get("data-row") for node in second.findall('.//*[@data-row]')}), 7)
            self.assertEqual(len(second.findall('.//*[@data-row]')), 42)
            language = "zh" if chinese else "en"
            markup = render_coding.support_tables(self.d, chinese, language)
            self.assertIn(f"images/parameter-support-{language}.svg", markup)
            self.assertIn(f"images/cache-settings-{language}.svg", markup)
            self.assertIn("26", markup)
            self.assertIn("ACA", markup)
            self.assertIn("probe/probe_results.jsonl", markup)
            self.assertIn("cache/cache_results.jsonl", markup)

    def test_retired_direct_method_is_not_current_or_default(self):
        for chinese, language in ((False, "en"), (True, "zh")):
            markup = render_coding.purpose(self.d, chinese, language)
            self.assertNotIn("1. **Direct from a VM", markup)
            self.assertNotIn("1. **从 VM 直连", markup)
            self.assertNotIn("Results come from this method unless", markup)
            self.assertNotIn("除非某节另有说明，结果都来自这种方法", markup)
            self.assertNotIn("In method 1", markup)
            self.assertNotIn("方法 1 的所有请求", markup)
            self.assertIn("当前测试方法" if chinese else "Current test method", markup)
            self.assertNotIn("**已取缔的方案，仅保留历史证据。**" if chinese else "**Retired method, historical evidence only.**", markup)
            self.assertIn("通过请求顶层 `cache_control` 开启提示缓存" if chinese else "Prompt caching is enabled with top-level `cache_control`", markup)
            steps = render_coding.steps(self.d, chinese)
            self.assertIn("gateway-cache/aca_cache_matrix.py", steps)
            self.assertIn("仅供历史参考" if chinese else "reference only", steps)

    def test_topology_shows_current_gateway_path_not_old_results(self):
        for chinese in (False, True):
            root = ET.fromstring(render_coding.topology(self.d, chinese))
            text = " ".join(root.itertext())
            self.assertEqual(len(root.findall('.//{http://www.w3.org/2000/svg}image')), 3)
            for value in ("Linux VM", "ACA / LiteLLM", "Microsoft Foundry", "East US 2", "cache_control",
                          "1h", "26", "12", "624", "650"):
                self.assertIn(value, text)
            self.assertNotIn("1,134", text)
            self.assertNotIn("Docker", text)
            self.assertIn("历史" if chinese else "Historical", text)
            self.assertIn("计划" if chinese else "Plan:", text)
            for model in ("Opus 5.5", "Sonnet 5.5", "Haiku 5.5"):
                self.assertIn(f"{model} · Global PAYGO", text)
            self.assertEqual(len(root.findall('.//*[@data-model-bullet="true"]')), 3)

    def test_thinking_comparison_uses_matched_efforts(self):
        for model in ("sonnet", "haiku"):
            item = self.d["facts"]["intervals"]["thinking"][model]
            self.assertEqual([c.split("|")[2] for c in item["on_cells"]], ["low", "medium", "high"])
            self.assertEqual([c.split("|")[2] for c in item["off_cells"]], ["low", "medium", "high"])
            low, high = item["difference_ci95"]
            self.assertLessEqual(low, item["difference"])
            self.assertLessEqual(item["difference"], high)
            self.assertEqual(item["problems_better_on"] + item["problems_better_off"] + item["problems_equal"], 18)


class AnalysisTests(unittest.TestCase):
    def test_intervals_resample_problems_deterministically(self):
        rows = []
        for index in range(18):
            rows.append({"cell_id": "sonnet|adaptive|low", "problem_id": f"p{index}", "passed": 3 if index < 9 else 0, "n": 3})
            rows.append({"cell_id": "sonnet|between_tools|low", "problem_id": f"p{index}", "passed": 3, "n": 3})
            rows.append({"cell_id": "opus|adaptive|low", "problem_id": f"p{index}", "passed": 3, "n": 3})
        cells = ["opus|adaptive|low", "sonnet|adaptive|low", "sonnet|between_tools|low"]
        first = coding_analyze.intervals(rows, cells)
        self.assertEqual(first, coding_analyze.intervals(rows, cells))
        self.assertEqual(first["cells"]["opus|adaptive|low"]["ci95"], [1.0, 1.0])
        self.assertAlmostEqual(first["cells"]["sonnet|adaptive|low"]["share"], 0.5)
        low, high = first["cells"]["sonnet|adaptive|low"]["ci95"]
        self.assertTrue(0.2 < low < 0.5 < high < 0.8)
        self.assertAlmostEqual(first["thinking"]["sonnet"]["difference"], -0.5)
        self.assertEqual(first["thinking"]["sonnet"]["problems_better_off"], 9)
        self.assertNotIn("opus", first["thinking"])


class JudgeExtractionTests(unittest.TestCase):
    def test_named_file_listing(self):
        text = "Here is the change.\n\nsrc/lib.rs\n```rust\nfn main() {}\n```\n"
        found, info = judge.extract_files(text, ["src/lib.rs"])
        self.assertEqual(found, {"src/lib.rs": "fn main() {}\n"})
        self.assertEqual(info["missing"], [])

    def test_basename_and_markup_around_the_name(self):
        text = "**`trinary.go`**\n```go\npackage trinary\n```\n"
        found, _ = judge.extract_files(text, ["trinary.go"])
        self.assertEqual(found, {"trinary.go": "package trinary\n"})

    def test_single_unnamed_block_for_a_single_file(self):
        found, _ = judge.extract_files("```python\nx = 1\n```", ["proverb.py"])
        self.assertEqual(found, {"proverb.py": "x = 1\n"})

    def test_no_code(self):
        found, info = judge.extract_files("I cannot do that.", ["a.py", "b.py"])
        self.assertEqual(found, {})
        self.assertEqual(info["missing"], ["a.py", "b.py"])

    def test_unclosed_block_is_counted(self):
        _, info = judge.extract_files("a.py\n```python\nx = 1\n", ["a.py"])
        self.assertEqual(info["unclosed"], 1)


def stream_body(scenario):
    usage = {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 1,
             "output_tokens_details": {"thinking_tokens": 0}}
    events = [("message_start", {"type": "message_start", "message": {"id": "test-only", "model": "claude-haiku-5-5", "usage": usage}}),
              ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}}),
              ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "test-only"}}),
              ("content_block_stop", {"type": "content_block_stop", "index": 0}),
              ("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}),
              ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hello"}}),
              ("content_block_stop", {"type": "content_block_stop", "index": 1}),
              ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "max_tokens" if scenario == "max_tokens" else "end_turn"},
                                 "usage": {"output_tokens": 5, "output_tokens_details": {"thinking_tokens": 4}}})]
    if scenario != "truncated":
        events.append(("message_stop", {"type": "message_stop"}))
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode("utf-8")


class StreamParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import httpx  # noqa: F401
            import azure.identity  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("install coding-matrix/requirements.txt to test the stream parser")
        os.environ.setdefault("FOUNDRY_ANTHROPIC_BASE", "http://127.0.0.1:1/anthropic")
        import claude_api
        cls.api = claude_api

    def collect(self, scenario):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                if scenario == "http_429":
                    body, status, kind = json.dumps({"error": {"type": "rate_limit_error", "message": "test-only"}}).encode(), 429, "application/json"
                else:
                    body, status, kind = stream_body(scenario), 200, "text/event-stream"
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("retry-after", "1")
                self.end_headers()
                self.wfile.write(body)

        class Tokens:
            def get(self):
                return "test-only"

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        original = self.api.BASE
        self.api.BASE = f"http://127.0.0.1:{server.server_port}/anthropic"
        client = self.api.new_client()
        try:
            body = {"model": "claude-haiku-5-5", "max_tokens": 64, "stream": True, "messages": [{"role": "user", "content": "test"}]}
            record = self.api.stream_message(client, Tokens(), body, deadline_s=30)
        finally:
            client.close()
            self.api.BASE = original
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        self.assertEqual(len(received), 1)
        return record

    def test_complete_stream(self):
        record = self.collect("complete")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["text"], "Hello")
        self.assertEqual(record["usage"]["output_tokens"], 5)
        self.assertEqual(record["usage"]["output_tokens_details"]["thinking_tokens"], 4)
        timing = record["timing"]
        for key in ("headers", "first_event", "message_start", "thinking_block_start", "first_signature", "first_text", "message_stop", "end"):
            self.assertIn(key, timing)
        self.assertNotIn("first_thinking_text", timing)
        self.assertLessEqual(timing["first_event"], timing["first_text"])
        self.assertLessEqual(timing["first_text"], timing["end"])
        self.assertEqual([b["type"] for b in record["blocks"]], ["thinking", "text"])
        self.assertTrue(record["blocks"][0]["signature"])

    def test_truncated_stream(self):
        self.assertEqual(self.collect("truncated")["status"], "stream_incomplete")

    def test_max_tokens_stream(self):
        self.assertEqual(self.collect("max_tokens")["status"], "max_tokens")

    def test_http_429(self):
        record = self.collect("http_429")
        self.assertEqual((record["status"], record["http_status"]), ("http_error", 429))
        self.assertEqual(record["error_body"]["error"]["type"], "rate_limit_error")
        self.assertEqual(record["headers"]["retry-after"], "1")


if __name__ == "__main__":
    unittest.main()
