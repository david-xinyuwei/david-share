#!/usr/bin/env python3
"""Concurrent vLLM transcription benchmark using correct multipart form-data format.
Tests concurrency 1/2/4/8 with real audio transcription.
"""
import json, time, subprocess, concurrent.futures, io
from pathlib import Path
import urllib.request
import numpy as np

VLLM_BIN = "/root/miniconda3/envs/asr-vllm/bin/python"
MODEL = "Qwen/Qwen3-ASR-1.7B"
PORT = 8201
RESULTS = Path("/root/asr_results")
TEST_WAVS = sorted(Path("/root/asr_results/fleurs_wav").glob("*.wav"))[:20]

def start_server():
    subprocess.run(f"nohup {VLLM_BIN} -m vllm.entrypoints.openai.api_server --model {MODEL} --port {PORT} --max-model-len 4096 > /tmp/vllm_conc.log 2>&1 &", shell=True)
    for i in range(90):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=3)
            return True
        except:
            time.sleep(3)
    return False

def send_request(wav_path):
    """Send one transcription request using multipart form-data."""
    boundary = "----FormBoundary"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(b"Content-Disposition: form-data; name=\"model\"\r\n\r\n")
    body.write(f"{MODEL}\r\n".encode())
    body.write(f"--{boundary}\r\n".encode())
    body.write(b"Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n")
    body.write(b"Content-Type: audio/wav\r\n\r\n")
    with open(wav_path, "rb") as f:
        body.write(f.read())
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    
    data = body.getvalue()
    req = urllib.request.Request(
        f"http://localhost:{PORT}/v1/audio/transcriptions",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        lat = time.time() - t0
        text = result.get("text", "")
        return {"latency": lat, "text": text, "success": True}
    except Exception as e:
        lat = time.time() - t0
        return {"latency": lat, "error": str(e), "success": False}

def benchmark_concurrency(concurrency, n_requests):
    """Run n_requests with given concurrency level."""
    wavs = [str(TEST_WAVS[i % len(TEST_WAVS)]) for i in range(n_requests)]
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(send_request, w) for w in wavs]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    
    if successes:
        lats = np.array([r["latency"] for r in successes])
        return {
            "concurrency": concurrency,
            "total_requests": n_requests,
            "successes": len(successes),
            "failures": len(failures),
            "p50_ms": round(float(np.percentile(lats, 50)) * 1000, 1),
            "p95_ms": round(float(np.percentile(lats, 95)) * 1000, 1),
            "mean_ms": round(float(lats.mean()) * 1000, 1),
            "throughput_rps": round(len(successes) / lats.sum() * concurrency, 2),
            "sample_text": successes[0]["text"][:50] if successes else "",
        }
    else:
        return {
            "concurrency": concurrency,
            "total_requests": n_requests,
            "successes": 0,
            "failures": len(failures),
            "error": failures[0]["error"] if failures else "unknown",
        }

# Main
print("Starting vLLM server...")
if not start_server():
    print("ERROR: Server failed to start")
    json.dump({"error": "server failed"}, open(RESULTS / "concurrent_benchmark_v2.json", "w"))
    exit(1)

print("Server ready. Running benchmark...")

# Warmup
print("  Warmup (2 requests)...")
send_request(str(TEST_WAVS[0]))
send_request(str(TEST_WAVS[1]))

all_results = []
for conc in [1, 2, 4, 8]:
    n = conc * 4  # 4 requests per worker
    print(f"  Concurrency={conc}, requests={n}...")
    result = benchmark_concurrency(conc, n)
    all_results.append(result)
    if "p50_ms" in result:
        print(f"    P50={result['p50_ms']}ms  P95={result['p95_ms']}ms  throughput={result['throughput_rps']} rps  successes={result['successes']}/{n}")
    else:
        print(f"    FAILED: {result.get('error', 'unknown')}")

# Save
json.dump(all_results, open(RESULTS / "concurrent_benchmark_v2.json", "w"), indent=2, ensure_ascii=False)
print(f"\nSaved: {RESULTS / 'concurrent_benchmark_v2.json'}")

# Cleanup
subprocess.run(f"pkill -f 'vllm.*{PORT}'", shell=True)
print("Done.")
