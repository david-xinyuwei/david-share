#!/usr/bin/env python3
"""
Benchmark vLLM Multi-LoRA serving performance.
Measures latency, throughput, TTFT for base model and all LoRA adapters.

Author: Xinyu Wei
"""
import json
import time
import requests
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

VLLM_URL = "http://localhost:8080/v1/chat/completions"
MODELS = [
    "/data/EXAONE-3.5-2.4B-Instruct",
    "medical",
    "legal",
    "customer_support",
    "code",
]

PROMPTS = [
    "Explain the concept of machine learning in simple terms.",
    "What are the benefits of cloud computing for enterprises?",
    "How does containerization differ from virtualization?",
    "Describe the role of a load balancer in distributed systems.",
    "What is the CAP theorem and why does it matter?",
]

NUM_RUNS = 3  # runs per model per prompt


def benchmark_single(model: str, prompt: str, max_tokens: int = 128) -> dict:
    """Benchmark a single request: measure TTFT (streaming) and total latency."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "stream": True,
    }
    start = time.time()
    ttft = None
    total_tokens = 0
    full_text = ""

    resp = requests.post(VLLM_URL, json=payload, stream=True, timeout=60)
    resp.raise_for_status()

    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8")
        if line_str.startswith("data: "):
            data_str = line_str[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content and ttft is None:
                    ttft = time.time() - start
                if content:
                    full_text += content
                    total_tokens += 1  # approximate
                # Check for usage in final chunk
                usage = chunk.get("usage")
                if usage and usage.get("completion_tokens"):
                    total_tokens = usage["completion_tokens"]
            except (json.JSONDecodeError, KeyError):
                pass

    total_time = time.time() - start
    tps = total_tokens / total_time if total_time > 0 else 0

    return {
        "model": model,
        "ttft_ms": round(ttft * 1000, 1) if ttft else None,
        "total_time_s": round(total_time, 3),
        "completion_tokens": total_tokens,
        "tokens_per_sec": round(tps, 1),
    }


def benchmark_concurrent(models: list, prompt: str, max_tokens: int = 128) -> list:
    """Send concurrent requests to different adapters."""
    results = []
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {
            executor.submit(benchmark_single, m, prompt, max_tokens): m
            for m in models
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"model": futures[future], "error": str(e)})
    return results


def main():
    print("=" * 80)
    print("EXAONE Multi-LoRA Benchmark")
    print("=" * 80)

    # ---- Sequential benchmark ----
    print("\n[1/2] Sequential Benchmark (per-model latency)")
    print("-" * 60)

    all_results = {}
    for model in MODELS:
        model_label = model.split("/")[-1] if "/" in model else model
        all_results[model_label] = []
        for prompt in PROMPTS:
            for run in range(NUM_RUNS):
                result = benchmark_single(model, prompt)
                all_results[model_label].append(result)
                sys.stdout.write(".")
                sys.stdout.flush()
        print(f" {model_label} done")

    # Summary
    print(f"\n{'Model':<25} {'Avg TTFT':>10} {'Avg Latency':>12} {'Avg TPS':>10}")
    print("-" * 60)
    summary = {}
    for model_label, results in all_results.items():
        ttfts = [r["ttft_ms"] for r in results if r.get("ttft_ms")]
        latencies = [r["total_time_s"] for r in results]
        tps_list = [r["tokens_per_sec"] for r in results]

        avg_ttft = statistics.mean(ttfts) if ttfts else 0
        avg_lat = statistics.mean(latencies)
        avg_tps = statistics.mean(tps_list)

        summary[model_label] = {
            "avg_ttft_ms": round(avg_ttft, 1),
            "avg_latency_s": round(avg_lat, 3),
            "avg_tokens_per_sec": round(avg_tps, 1),
            "p50_ttft_ms": round(statistics.median(ttfts), 1) if ttfts else 0,
            "p95_latency_s": round(sorted(latencies)[int(len(latencies) * 0.95)], 3),
            "num_requests": len(results),
        }
        print(f"{model_label:<25} {avg_ttft:>8.1f}ms {avg_lat:>10.3f}s {avg_tps:>8.1f}")

    # ---- Concurrent benchmark ----
    print(f"\n[2/2] Concurrent Benchmark (all {len(MODELS)} models simultaneously)")
    print("-" * 60)

    concurrent_results = []
    for prompt in PROMPTS[:3]:  # 3 prompts
        for run in range(NUM_RUNS):
            batch = benchmark_concurrent(MODELS, prompt)
            concurrent_results.extend(batch)
            sys.stdout.write(".")
            sys.stdout.flush()
    print(" done")

    # Concurrent summary
    conc_by_model = {}
    for r in concurrent_results:
        if "error" in r:
            continue
        label = r["model"].split("/")[-1] if "/" in r["model"] else r["model"]
        conc_by_model.setdefault(label, []).append(r)

    print(f"\n{'Model':<25} {'Avg TTFT':>10} {'Avg Latency':>12} {'Avg TPS':>10}")
    print("-" * 60)
    for label, results in conc_by_model.items():
        ttfts = [r["ttft_ms"] for r in results if r.get("ttft_ms")]
        latencies = [r["total_time_s"] for r in results]
        tps_list = [r["tokens_per_sec"] for r in results]
        avg_ttft = statistics.mean(ttfts) if ttfts else 0
        avg_lat = statistics.mean(latencies)
        avg_tps = statistics.mean(tps_list)
        print(f"{label:<25} {avg_ttft:>8.1f}ms {avg_lat:>10.3f}s {avg_tps:>8.1f}")

    # Save all results
    output = {
        "sequential": summary,
        "concurrent_raw": [
            {k: v for k, v in r.items()} for r in concurrent_results if "error" not in r
        ],
    }
    with open("/tmp/benchmark_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to /tmp/benchmark_results.json")


if __name__ == "__main__":
    main()
