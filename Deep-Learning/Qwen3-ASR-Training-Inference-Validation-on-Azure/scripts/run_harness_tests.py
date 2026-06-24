#!/usr/bin/env python3
"""Run repeatable local validation tests for the ASR harness."""

from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MockAsrHandler(http.server.BaseHTTPRequestHandler):
    status_code = 200

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        content_length = int(self.headers.get("content-length", "0"))
        self.rfile.read(content_length)
        payload = json.dumps({"text": "mock transcript"}).encode()
        self.send_response(self.status_code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        return


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(command)}")
    return result


def test_py_compile() -> dict[str, object]:
    run([sys.executable, "-m", "py_compile", *[str(path) for path in sorted((ROOT / "scripts").glob("*.py"))]])
    return {"name": "py_compile", "ok": True}


def run_eval_case(reference: str, hypothesis: str, hotwords: str = "") -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        reference_path = temp_dir / "reference.txt"
        hypothesis_path = temp_dir / "hypothesis.txt"
        hotwords_path = temp_dir / "hotwords.txt"
        output_path = temp_dir / "metrics.json"
        reference_path.write_text(reference, encoding="utf-8")
        hypothesis_path.write_text(hypothesis, encoding="utf-8")
        hotwords_path.write_text(hotwords, encoding="utf-8")
        command = [
            sys.executable,
            "scripts/eval_asr_metrics.py",
            "--reference",
            str(reference_path),
            "--hypothesis",
            str(hypothesis_path),
            "--output",
            str(output_path),
        ]
        if hotwords:
            command.extend(["--hotwords", str(hotwords_path)])
        run(command)
        return json.loads(output_path.read_text(encoding="utf-8"))


def test_eval_metrics() -> dict[str, object]:
    exact = run_eval_case("sample ASR 测试", "sample ASR 测试", "sample\nASR\n")
    substitution = run_eval_case("语音转文字 ASR 测试", "语音转文本 ASR 测试", "语音转文字\nASR\n")
    insertion = run_eval_case("hello world", "hello brave world")
    assert exact["wer"] == 0
    assert exact["cer"] == 0
    assert exact["hotword_recall"] == 1.0
    assert substitution["wer"] > 0
    assert substitution["cer"] > 0
    assert insertion["wer"] > 0
    return {"name": "eval_metrics", "ok": True, "cases": {"exact": exact, "substitution": substitution, "insertion": insertion}}


def run_benchmark_against_mock(status_code: int, output_name: str) -> dict[str, object]:
    MockAsrHandler.status_code = status_code
    with tempfile.TemporaryDirectory() as temp_dir_name:
        audio_path = Path(temp_dir_name) / "sample.wav"
        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 16000)
        with socketserver.TCPServer(("127.0.0.1", 0), MockAsrHandler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            output_path = ROOT / "results" / output_name
            run(
                [
                    sys.executable,
                    "scripts/benchmark_endpoint.py",
                    "--url",
                    f"http://127.0.0.1:{port}/transcribe",
                    "--audio",
                    str(audio_path),
                    "--output",
                    str(output_path),
                ]
            )
            server.shutdown()
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_benchmark_endpoint() -> dict[str, object]:
    success_payload = run_benchmark_against_mock(200, "benchmark_endpoint_mock_success.json")
    failure_payload = run_benchmark_against_mock(503, "benchmark_endpoint_mock_failure.json")
    assert success_payload["summary"]["successes"] == 1
    assert success_payload["summary"]["failures"] == 0
    assert failure_payload["summary"]["successes"] == 0
    assert failure_payload["summary"]["failures"] == 1
    return {"name": "benchmark_endpoint", "ok": True, "success": success_payload["summary"], "failure": failure_payload["summary"]}


def main() -> None:
    results = [test_py_compile(), test_eval_metrics(), test_benchmark_endpoint()]
    output_path = ROOT / "results" / "harness_test_results.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps({"tests": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": results, "output": str(output_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()