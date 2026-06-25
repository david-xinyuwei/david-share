#!/usr/bin/env python3
"""Remaining inference validation for mission anchor #13/#14.

#13: vLLM --optimization-level feasibility.
#14: vLLM concurrency 16 benchmark using multipart form-data.
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import numpy as np

RESULTS = Path("/root/asr_results")
RESULTS.mkdir(parents=True, exist_ok=True)
VLLM_BIN = "/root/miniconda3/envs/asr-vllm/bin/python"
MODEL = "Qwen/Qwen3-ASR-1.7B"
TEST_WAVS = sorted(Path("/root/asr_results/fleurs_wav").glob("*.wav"))[:32]


def run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def stop_servers() -> None:
    run("pkill -f 'vllm.*82' || true")
    time.sleep(5)


def wait_health(port: int, timeout_s: int = 420) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3)
            return True
        except Exception:
            time.sleep(3)
    return False


def start_vllm(port: int, extra: str, log_path: str) -> bool:
    stop_servers()
    cmd = (
        f"nohup {VLLM_BIN} -m vllm.entrypoints.openai.api_server "
        f"--model {MODEL} --port {port} --max-model-len 4096 {extra} "
        f"> {log_path} 2>&1 &"
    )
    run(cmd)
    return wait_health(port)


def multipart_body(wav_path: Path) -> tuple[bytes, str]:
    boundary = "----BoundaryQwen3ASR"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(b"Content-Disposition: form-data; name=\"model\"\r\n\r\n")
    body.write(f"{MODEL}\r\n".encode())
    body.write(f"--{boundary}\r\n".encode())
    body.write(b"Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n")
    body.write(b"Content-Type: audio/wav\r\n\r\n")
    body.write(wav_path.read_bytes())
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    return body.getvalue(), boundary


def transcribe(port: int, wav_path: Path) -> dict:
    data, boundary = multipart_body(wav_path)
    req = urllib.request.Request(
        f"http://localhost:{port}/v1/audio/transcriptions",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        payload = json.loads(resp.read())
        return {"success": True, "latency_s": time.time() - start, "text": payload.get("text", "")}
    except Exception as exc:
        return {"success": False, "latency_s": time.time() - start, "error": repr(exc)}


def bench_concurrency(port: int, concurrency: int, total_requests: int) -> dict:
    wavs = [TEST_WAVS[i % len(TEST_WAVS)] for i in range(total_requests)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = list(pool.map(lambda p: transcribe(port, p), wavs))
    successes = [r for r in rows if r["success"]]
    failures = [r for r in rows if not r["success"]]
    if successes:
        lat = np.array([r["latency_s"] for r in successes])
        return {
            "concurrency": concurrency,
            "total_requests": total_requests,
            "successes": len(successes),
            "failures": len(failures),
            "p50_ms": round(float(np.percentile(lat, 50)) * 1000, 1),
            "p95_ms": round(float(np.percentile(lat, 95)) * 1000, 1),
            "mean_ms": round(float(lat.mean()) * 1000, 1),
            "wall_clock_s": round(float(lat.max()), 3),
            "throughput_rps_estimated": round(len(successes) / float(lat.max()), 2),
            "sample_text": successes[0].get("text", "")[:80],
        }
    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "successes": 0,
        "failures": len(failures),
        "first_error": failures[0].get("error") if failures else "unknown",
    }


def test_concurrency_16() -> dict:
    print("[14] Starting default vLLM for c16 benchmark", flush=True)
    ready = start_vllm(8214, "", "/root/asr_results/vllm_c16.log")
    if not ready:
        log = Path("/root/asr_results/vllm_c16.log").read_text(errors="ignore")[-2000:]
        return {"status": "server_failed", "log_tail": log}
    # Warm up graph capture.
    for wav in TEST_WAVS[:4]:
        transcribe(8214, wav)
    result = bench_concurrency(8214, 16, 64)
    stop_servers()
    return {"status": "done", "result": result}


def test_optimization_level() -> dict:
    print("[13] Testing vLLM --optimization-level 3", flush=True)
    ready = start_vllm(8213, "--optimization-level 3", "/root/asr_results/vllm_opt_level3.log")
    if not ready:
        log = Path("/root/asr_results/vllm_opt_level3.log").read_text(errors="ignore")[-3000:]
        return {"status": "server_failed", "optimization_level": 3, "log_tail": log}
    row = transcribe(8213, TEST_WAVS[0])
    stop_servers()
    return {"status": "done", "optimization_level": 3, "single_request": row}


def main() -> None:
    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL,
        "concurrency_16": test_concurrency_16(),
        "optimization_level_3": test_optimization_level(),
    }
    out = RESULTS / "remaining_inference_tests.json"
    out.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(all_results, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
