#!/usr/bin/env python3
"""
vLLM FP8 Benchmark Script for H100 / A100 GPUs
Author: Xinyu Wei (Microsoft GBB AI Architect)
Date: 2025-12-18

This script tests vLLM inference performance in two scenarios:
- Memory-bound: Single request with long prefill (~4K tokens)
- Compute-bound: High concurrency decode (50 concurrent requests)

Usage:
    # Start vLLM server (BF16 baseline):
    vllm serve Qwen/Qwen2.5-14B-Instruct --port 8080 --max-model-len 4096

    # Run all tests:
    python benchmark.py --url http://localhost:8080

    # Test specific scenario:
    python benchmark.py --mode prefill   # Memory-bound test
    python benchmark.py --mode decode    # Compute-bound test

    # Then restart with FP8 and compare:
    vllm serve Qwen/Qwen2.5-14B-Instruct --port 8080 --max-model-len 4096 --quantization fp8

For SGLang (RTX PRO 6000), use benchmark_sglang.py instead.
"""

import requests
import time
import random
import argparse
import concurrent.futures


def test_prefill(base_url: str, model: str, num_runs: int = 3):
    """Test single request prefill throughput (memory-bound scenario)"""
    print(f"\n{'='*60}")
    print("Scenario: Single Request Prefill (Memory-Bound)")
    print(f"{'='*60}")

    results = []
    for i in range(num_runs):
        # Random prefix to avoid cache hit
        random_prefix = str(random.randint(100000000, 999999999))
        long_text = random_prefix + " Explain quantum computing in detail. " * 500

        start = time.time()
        r = requests.post(
            f"{base_url}/v1/completions",
            json={"model": model, "prompt": long_text, "max_tokens": 1},
            timeout=120
        )
        elapsed = time.time() - start

        usage = r.json().get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        throughput = prompt_tokens / elapsed if elapsed > 0 else 0
        results.append(throughput)
        print(f"  Run {i+1}: {prompt_tokens} tokens in {elapsed:.3f}s = {throughput:.0f} tok/s")

    avg = sum(results) / len(results)
    print(f"\n  Average Prefill Throughput: {avg:.0f} tok/s")
    return avg


def send_decode_request(args):
    """Send a single decode request"""
    i, base_url, model = args
    prompt = f"{random.randint(1000000, 9999999)} Write a short story about AI number {i}."
    try:
        r = requests.post(
            f"{base_url}/v1/completions",
            json={"model": model, "prompt": prompt, "max_tokens": 100},
            timeout=120
        )
        return r.json().get("usage", {}).get("completion_tokens", 0)
    except Exception as e:
        print(f"  Error in request {i}: {e}")
        return 0


def test_decode(base_url: str, model: str, num_concurrent: int = 50):
    """Test concurrent decode throughput (compute-bound scenario)"""
    print(f"\n{'='*60}")
    print(f"Scenario: {num_concurrent} Concurrent Decode (Compute-Bound)")
    print(f"{'='*60}")

    # Warmup
    print("  Warming up...")
    send_decode_request((0, base_url, model))

    # Concurrent test
    print(f"  Running {num_concurrent} concurrent requests...")
    start_all = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        args = [(i, base_url, model) for i in range(num_concurrent)]
        results = list(executor.map(send_decode_request, args))

    total_time = time.time() - start_all
    total_tokens = sum(results)
    throughput = total_tokens / total_time if total_time > 0 else 0

    print(f"\n  Requests: {num_concurrent}")
    print(f"  Total tokens: {total_tokens}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Decode Throughput: {throughput:.0f} tok/s")
    return throughput


def main():
    parser = argparse.ArgumentParser(
        description="vLLM FP8 Benchmark for H100/A100",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python benchmark.py --url http://localhost:8080
    python benchmark.py --mode prefill --url http://localhost:8080
    python benchmark.py --mode decode --concurrent 100
        """
    )
    parser.add_argument("--mode", choices=["prefill", "decode", "all"], default="all",
                        help="Test mode: prefill (memory-bound), decode (compute-bound), or all")
    parser.add_argument("--url", default="http://localhost:8080",
                        help="vLLM server URL")
    parser.add_argument("--model", default="Qwen/Qwen2.5-14B-Instruct",
                        help="Model name")
    parser.add_argument("--concurrent", type=int, default=50,
                        help="Number of concurrent requests for decode test")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("vLLM FP8 Benchmark (H100/A100)")
    print(f"{'='*60}")
    print(f"Server: {args.url}")
    print(f"Model: {args.model}")

    results = {}

    if args.mode in ["prefill", "all"]:
        results["prefill"] = test_prefill(args.url, args.model)

    if args.mode in ["decode", "all"]:
        results["decode"] = test_decode(args.url, args.model, args.concurrent)

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    for key, value in results.items():
        print(f"  {key.capitalize()}: {value:.0f} tok/s")

    return results


if __name__ == "__main__":
    main()
