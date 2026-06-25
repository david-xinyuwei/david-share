#!/usr/bin/env python3
"""CUDA Graph A/B benchmark: default (CUDA Graph ON) vs --enforce-eager (OFF)
Runs on VM, writes result to /root/asr_results/cuda_graph_ab.json
"""
import json, time, subprocess, os
from pathlib import Path

RESULTS = Path("/root/asr_results")
VLLM = "/root/miniconda3/envs/asr-vllm/bin/python"
TEST_WAV = "/root/asr_results/fleurs_wav/0010.wav"
MODEL = "Qwen/Qwen3-ASR-1.7B"
N_REQUESTS = 10  # per mode

def start_server(port, enforce_eager=False):
    cmd = f"nohup {VLLM} -m vllm.entrypoints.openai.api_server --model {MODEL} --port {port} --max-model-len 4096"
    if enforce_eager:
        cmd += " --enforce-eager"
    cmd += f" > /tmp/vllm_{port}.log 2>&1 &"
    subprocess.run(cmd, shell=True)
    # Wait for ready
    import urllib.request
    for i in range(90):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3)
            return True
        except:
            time.sleep(3)
    return False

def benchmark_transformers(n=10):
    """Use qwen-asr directly (no vLLM) as baseline for single-request latency"""
    import torch
    from qwen_asr import Qwen3ASRModel
    model = Qwen3ASRModel.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda")
    
    # Warmup
    model.transcribe([TEST_WAV])
    
    latencies = []
    for i in range(n):
        t0 = time.time()
        r = model.transcribe([TEST_WAV])
        lat = time.time() - t0
        latencies.append(lat)
    
    del model
    torch.cuda.empty_cache()
    time.sleep(5)
    return latencies

def benchmark_vllm(port, n=10):
    """Send requests via OpenAI-compatible API using multipart form"""
    import urllib.request
    latencies = []
    
    for i in range(n):
        t0 = time.time()
        try:
            # Use form-data upload like OpenAI Whisper API
            import io
            boundary = "----FormBoundary7MA4YWxkTrZu0gW"
            body = io.BytesIO()
            
            # model field
            body.write(f"--{boundary}\r\n".encode())
            body.write(b"Content-Disposition: form-data; name=\"model\"\r\n\r\n")
            body.write(f"{MODEL}\r\n".encode())
            
            # file field
            body.write(f"--{boundary}\r\n".encode())
            body.write(b"Content-Disposition: form-data; name=\"file\"; filename=\"test.wav\"\r\n")
            body.write(b"Content-Type: audio/wav\r\n\r\n")
            with open(TEST_WAV, "rb") as f:
                body.write(f.read())
            body.write(b"\r\n")
            body.write(f"--{boundary}--\r\n".encode())
            
            data = body.getvalue()
            req = urllib.request.Request(
                f"http://localhost:{port}/v1/audio/transcriptions",
                data=data,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
            )
            resp = urllib.request.urlopen(req, timeout=30)
            lat = time.time() - t0
            result = json.loads(resp.read())
            latencies.append(lat)
        except Exception as e:
            latencies.append(None)
    
    return [l for l in latencies if l is not None]

def main():
    import numpy as np
    results = {}
    
    # 1. Transformers baseline (no serving overhead)
    print("=== Transformers baseline (no vLLM) ===")
    tf_lats = benchmark_transformers(N_REQUESTS)
    arr = np.array(tf_lats)
    results["transformers_bf16"] = {
        "mode": "transformers direct inference",
        "p50_ms": round(float(np.median(arr)) * 1000, 1),
        "p95_ms": round(float(np.percentile(arr, 95)) * 1000, 1),
        "mean_ms": round(float(arr.mean()) * 1000, 1),
        "n": len(tf_lats),
    }
    print(f"  P50={results['transformers_bf16']['p50_ms']}ms  P95={results['transformers_bf16']['p95_ms']}ms")
    
    # 2. vLLM with CUDA Graph (default)
    print("\n=== vLLM default (CUDA Graph ON) ===")
    if start_server(8201, enforce_eager=False):
        print("  Server ready, benchmarking...")
        cg_lats = benchmark_vllm(8201, N_REQUESTS)
        if cg_lats:
            arr = np.array(cg_lats)
            results["vllm_cuda_graph_on"] = {
                "mode": "vLLM default (CUDA Graph ON)",
                "p50_ms": round(float(np.median(arr)) * 1000, 1),
                "p95_ms": round(float(np.percentile(arr, 95)) * 1000, 1),
                "mean_ms": round(float(arr.mean()) * 1000, 1),
                "n": len(cg_lats),
            }
            print(f"  P50={results['vllm_cuda_graph_on']['p50_ms']}ms  P95={results['vllm_cuda_graph_on']['p95_ms']}ms")
        else:
            results["vllm_cuda_graph_on"] = {"error": "all requests failed", "n": 0}
            print("  All requests failed")
    else:
        results["vllm_cuda_graph_on"] = {"error": "server failed to start"}
    
    subprocess.run("pkill -f 'vllm.*8201'", shell=True)
    time.sleep(10)
    
    # 3. vLLM with --enforce-eager (CUDA Graph OFF)
    print("\n=== vLLM --enforce-eager (CUDA Graph OFF) ===")
    if start_server(8202, enforce_eager=True):
        print("  Server ready, benchmarking...")
        eager_lats = benchmark_vllm(8202, N_REQUESTS)
        if eager_lats:
            arr = np.array(eager_lats)
            results["vllm_cuda_graph_off"] = {
                "mode": "vLLM --enforce-eager (CUDA Graph OFF)",
                "p50_ms": round(float(np.median(arr)) * 1000, 1),
                "p95_ms": round(float(np.percentile(arr, 95)) * 1000, 1),
                "mean_ms": round(float(arr.mean()) * 1000, 1),
                "n": len(eager_lats),
            }
            print(f"  P50={results['vllm_cuda_graph_off']['p50_ms']}ms  P95={results['vllm_cuda_graph_off']['p95_ms']}ms")
        else:
            results["vllm_cuda_graph_off"] = {"error": "all requests failed", "n": 0}
    else:
        results["vllm_cuda_graph_off"] = {"error": "server failed to start"}
    
    subprocess.run("pkill -f 'vllm.*8202'", shell=True)
    
    # Summary
    print("\n=== SUMMARY ===")
    for k, v in results.items():
        if "p50_ms" in v:
            print(f"  {v['mode']}: P50={v['p50_ms']}ms  P95={v['p95_ms']}ms")
        else:
            print(f"  {k}: {v}")
    
    json.dump(results, open(RESULTS / "cuda_graph_ab.json", "w"), indent=2)
    print(f"\nSaved: {RESULTS / 'cuda_graph_ab.json'}")

if __name__ == "__main__":
    main()
