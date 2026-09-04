import importlib.util
import json
import pathlib
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOAD = load("load_test_endpoint")
ACI = load("submit_private_aci_load_test")


def sse(*events: dict) -> bytes:
    return b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events) + b"data: [DONE]\n\n"


class LoadTestEndpointTests(unittest.TestCase):
    def test_stream_summary_uses_first_content_delta_for_ttft_and_usage_for_tokens(self) -> None:
        role_only = {"choices": [{"delta": {"role": "assistant"}}]}
        content = {"choices": [{"delta": {"content": "x"}}]}
        usage = {"choices": [], "usage": {"prompt_tokens": 400, "completion_tokens": 256}}
        chunks = [(10.5, sse(role_only)), (11.0, sse(content)), (12.0, sse(content, usage))]
        summary = LOAD.summarize_stream(chunks, started=10.0, finished=13.0)
        self.assertEqual(summary["ttftSeconds"], 1.0)
        self.assertEqual(summary["e2eSeconds"], 3.0)
        self.assertEqual(summary["outputTokens"], 256)
        self.assertEqual(summary["promptTokens"], 400)
        self.assertEqual(summary["tokenSource"], "usage")
        self.assertEqual(summary["contentEvents"], 2)

    def test_stream_summary_falls_back_to_content_events_without_usage(self) -> None:
        content = {"choices": [{"delta": {"reasoning_content": "y"}}]}
        summary = LOAD.summarize_stream([(1.2, sse(content, content, content))], started=1.0, finished=2.0)
        self.assertEqual(summary["outputTokens"], 3)
        self.assertEqual(summary["tokenSource"], "content-events")

    def test_qwen3_reasoning_delta_counts_as_first_token(self) -> None:
        # Live 2026-09-04 shape: role delta, then `reasoning` deltas, then one `content` delta.
        events = [{"choices": [{"delta": {"role": "assistant"}}]},
                  {"choices": [{"delta": {"reasoning": "thinking"}}]},
                  {"choices": [{"delta": {"content": "Hello"}}]}]
        summary = LOAD.summarize_stream([(2.0, sse(*events))], started=1.0, finished=2.5)
        self.assertEqual(summary["contentEvents"], 2)
        self.assertEqual(summary["ttftSeconds"], 1.0)

    def test_split_event_across_chunks_is_reassembled(self) -> None:
        payload = sse({"choices": [{"delta": {"content": "z"}}]})
        half = len(payload) // 2
        summary = LOAD.summarize_stream([(1.1, payload[:half]), (1.4, payload[half:])], started=1.0, finished=1.5)
        self.assertEqual(summary["contentEvents"], 1)
        self.assertAlmostEqual(summary["ttftSeconds"], 0.4)

    def test_level_summary_percentiles_and_throughput(self) -> None:
        records = [
            {"passed": True, "ttftSeconds": 0.5, "e2eSeconds": 4.5, "outputTokens": 200, "httpStatus": 200},
            {"passed": True, "ttftSeconds": 0.7, "e2eSeconds": 4.7, "outputTokens": 200, "httpStatus": 200},
            {"passed": False, "httpStatus": 429, "e2eSeconds": 0.2},
        ]
        level = LOAD.summarize_level(4, records, wall_seconds=5.0)
        self.assertEqual((level["succeeded"], level["failed"]), (2, 1))
        self.assertEqual(level["statusHistogram"], {"200": 2, "429": 1})
        self.assertEqual(level["ttftSecondsP95"], 0.7)
        self.assertEqual(level["aggregateOutputTokensPerSecond"], 80.0)
        self.assertEqual(level["perRequestOutputTokensPerSecondMedian"], 50.0)

    def test_requests_per_level_scales_with_concurrency(self) -> None:
        self.assertEqual(LOAD.requests_for_level(1, 8), 8)
        self.assertEqual(LOAD.requests_for_level(32, 8), 64)

    def test_line_emission_round_trips_and_detects_truncation(self) -> None:
        result = {"label": "private", "passed": True, "levels": [{"concurrency": 1}],
                  "requests": [{"httpStatus": 200, "concurrency": 1}, {"httpStatus": 200, "concurrency": 1}]}
        lines = LOAD.emit_lines(result)
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(len(line) < 16_000 for line in lines))
        self.assertEqual(LOAD.collect_lines(lines), result)
        with self.assertRaisesRegex(ValueError, "expected 2"):
            LOAD.collect_lines(lines[:1] + lines[2:])
        with self.assertRaisesRegex(ValueError, "end marker"):
            LOAD.collect_lines(lines[:-1])

    def test_aci_command_embeds_source_hash_and_arguments(self) -> None:
        source = (SCRIPTS / "load_test_endpoint.py").read_bytes()
        command, digest = ACI.build_load_command(
            source, "https://example.services.ai.azure.com/openai/v1/chat/completions",
            "dep", [1, 4], 8, 256)
        self.assertEqual(len(digest), 64)
        self.assertIn("--label", command)
        self.assertEqual(command[command.index("--label") + 1], "private")
        self.assertEqual(command[-2:], ["1", "4"])
        self.assertIn("load_test_endpoint.py", command[2])


if __name__ == "__main__":
    unittest.main()
