#!/usr/bin/env python3
"""
Fair FP8 Benchmark Script - Prefill vs Decode with Same Concurrency
Author: Xinyu Wei (Microsoft GBB AI Architect)
Date: 2026-01-03

This script does FAIR comparison by testing both prefill and decode
at the SAME concurrency levels (1 and 50).

Key insight:
- Prefill = Compute-bound (large matrix multiplication on entire prompt)
- Decode = Memory-bound (small computation, bottleneck is reading KV cache)
- High concurrency can shift decode from memory-bound to compute-bound

Test Matrix:
| Scenario              | Concurrency | Expected Bottleneck |
|-----------------------|-------------|---------------------|
| Prefill (single)      | 1           | Compute-bound       |
| Prefill (concurrent)  | 50          | Compute-bound       |
| Decode (single)       | 1           | Memory-bound        |
| Decode (concurrent)   | 50          | Compute-bound (batched) |

Usage:
    # Start vLLM server (BF16 baseline):
    vllm serve Qwen/Qwen2.5-14B-Instruct --port 8080 --max-model-len 4096
    
    # Run all 4 scenarios:
    python benchmark_fair.py --url http://localhost:8080
    
    # Run specific test:
    python benchmark_fair.py --test prefill_single
    python benchmark_fair.py --test prefill_concurrent
    python benchmark_fair.py --test decode_single
    python benchmark_fair.py --test decode_concurrent
    
    # Custom concurrency:
    python benchmark_fair.py --concurrent 100
    
    # Then restart with FP8 and compare:
    vllm serve neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic --port 8080 --max-model-len 4096
"""

import requests
import time
import random
import argparse
import json
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, List, Tuple


# ============================================================
# Configuration
# ============================================================

DEFAULT_CONFIG = {
    "model": "Qwen/Qwen2.5-14B-Instruct",
    "prefill_tokens": 4000,      # Target ~4K input tokens
    "decode_max_tokens": 100,    # Output tokens per request
    "warmup_requests": 3,        # Warmup before timing
    "test_runs": 3,              # Runs for averaging
    "timeout": 120,              # Request timeout
}


# ============================================================
# Test Functions
# ============================================================

def generate_long_prompt(target_tokens: int = 4000) -> str:
    """Generate a prompt with approximately target_tokens tokens."""
    base = "Explain the concept of artificial intelligence and machine learning. "
    repetitions = target_tokens // 10
    random_prefix = f"[{random.randint(100000000, 999999999)}] "
    return random_prefix + base * repetitions


def generate_short_prompt(idx: int = 0) -> str:
    """Generate a short prompt for decode test."""
    return f"[{random.randint(100000000, 999999999)}] Write a detailed story about AI assistant number {idx}."


def send_request(
    base_url: str, 
    model: str, 
    prompt: str, 
    max_tokens: int,
    timeout: int = 120
) -> Dict[str, Any]:
    """Send a single request and return timing + usage info."""
    start = time.time()
    try:
        r = requests.post(
            f"{base_url}/v1/completions",
            json={
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
            },
            timeout=timeout
        )
        r.raise_for_status()
        elapsed = time.time() - start
        data = r.json()
        usage = data.get("usage", {})
        return {
            "success": True,
            "elapsed": elapsed,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
    except Exception as e:
        return {
            "success": False,
            "elapsed": time.time() - start,
            "error": str(e),
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }


def send_request_wrapper(args: Tuple) -> Dict[str, Any]:
    """Wrapper for concurrent execution."""
    idx, base_url, model, prompt, max_tokens, timeout = args
    result = send_request(base_url, model, prompt, max_tokens, timeout)
    result["idx"] = idx
    return result


def run_concurrent_test(
    base_url: str,
    model: str,
    prompts: List[str],
    max_tokens: int,
    timeout: int = 120
) -> Dict[str, Any]:
    """Run concurrent requests and aggregate results."""
    num_requests = len(prompts)
    
    start_all = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        args_list = [
            (i, base_url, model, prompts[i], max_tokens, timeout)
            for i in range(num_requests)
        ]
        results = list(executor.map(send_request_wrapper, args_list))
    
    total_time = time.time() - start_all
    
    success_count = sum(1 for r in results if r["success"])
    total_prompt_tokens = sum(r["prompt_tokens"] for r in results)
    total_completion_tokens = sum(r["completion_tokens"] for r in results)
    
    return {
        "num_requests": num_requests,
        "success_count": success_count,
        "total_time": total_time,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "prefill_throughput": total_prompt_tokens / total_time if total_time > 0 else 0,
        "decode_throughput": total_completion_tokens / total_time if total_time > 0 else 0,
    }


# ============================================================
# Test Scenarios
# ============================================================

def test_prefill_single(base_url: str, model: str, config: Dict) -> Dict[str, Any]:
    """Scenario 1: Single request prefill (Compute-bound)"""
    print(f"\n{'='*60}")
    print("Scenario 1: Prefill (Single Request) - Compute-bound")
    print(f"{'='*60}")
    
    results = []
    for run in range(config["test_runs"]):
        prompt = generate_long_prompt(config["prefill_tokens"])
        result = send_request(base_url, model, prompt, max_tokens=1, timeout=config["timeout"])
        
        if result["success"]:
            throughput = result["prompt_tokens"] / result["elapsed"]
            results.append({
                "prompt_tokens": result["prompt_tokens"],
                "elapsed": result["elapsed"],
                "throughput": throughput,
            })
            print(f"  Run {run+1}: {result['prompt_tokens']} tokens in {result['elapsed']:.3f}s = {throughput:.0f} tok/s")
        else:
            print(f"  Run {run+1}: FAILED - {result.get('error', 'Unknown')}")
    
    if results:
        avg_throughput = sum(r["throughput"] for r in results) / len(results)
        print(f"\n  ✅ Average: {avg_throughput:.0f} tok/s (prefill)")
        return {"avg_throughput": avg_throughput, "runs": results}
    else:
        print(f"\n  ❌ All runs failed!")
        return {"avg_throughput": 0, "runs": []}


def test_prefill_concurrent(base_url: str, model: str, config: Dict, concurrent: int = 50) -> Dict[str, Any]:
    """Scenario 2: Concurrent prefill (Compute-bound, high batch)"""
    print(f"\n{'='*60}")
    print(f"Scenario 2: Prefill ({concurrent} Concurrent) - Compute-bound")
    print(f"{'='*60}")
    
    print(f"  Warming up ({config['warmup_requests']} requests)...")
    for _ in range(config["warmup_requests"]):
        prompt = generate_long_prompt(config["prefill_tokens"])
        send_request(base_url, model, prompt, max_tokens=1, timeout=config["timeout"])
    
    results = []
    for run in range(config["test_runs"]):
        prompts = [generate_long_prompt(config["prefill_tokens"]) for _ in range(concurrent)]
        result = run_concurrent_test(base_url, model, prompts, max_tokens=1, timeout=config["timeout"])
        
        results.append(result)
        print(f"  Run {run+1}: {result['total_prompt_tokens']} tokens in {result['total_time']:.2f}s = {result['prefill_throughput']:.0f} tok/s")
    
    if results:
        avg_throughput = sum(r["prefill_throughput"] for r in results) / len(results)
        print(f"\n  ✅ Average: {avg_throughput:.0f} tok/s (prefill, {concurrent} concurrent)")
        return {"avg_throughput": avg_throughput, "runs": results, "concurrent": concurrent}
    else:
        return {"avg_throughput": 0, "runs": [], "concurrent": concurrent}


def test_decode_single(base_url: str, model: str, config: Dict) -> Dict[str, Any]:
    """Scenario 3: Single request decode (Memory-bound)"""
    print(f"\n{'='*60}")
    print("Scenario 3: Decode (Single Request) - Memory-bound")
    print(f"{'='*60}")
    
    results = []
    for run in range(config["test_runs"]):
        prompt = generate_short_prompt(run)
        result = send_request(base_url, model, prompt, max_tokens=config["decode_max_tokens"], timeout=config["timeout"])
        
        if result["success"]:
            throughput = result["completion_tokens"] / result["elapsed"]
            results.append({
                "completion_tokens": result["completion_tokens"],
                "elapsed": result["elapsed"],
                "throughput": throughput,
            })
            print(f"  Run {run+1}: {result['completion_tokens']} tokens in {result['elapsed']:.3f}s = {throughput:.0f} tok/s")
        else:
            print(f"  Run {run+1}: FAILED - {result.get('error', 'Unknown')}")
    
    if results:
        avg_throughput = sum(r["throughput"] for r in results) / len(results)
        print(f"\n  ✅ Average: {avg_throughput:.0f} tok/s (decode)")
        return {"avg_throughput": avg_throughput, "runs": results}
    else:
        print(f"\n  ❌ All runs failed!")
        return {"avg_throughput": 0, "runs": []}


def test_decode_concurrent(base_url: str, model: str, config: Dict, concurrent: int = 50) -> Dict[str, Any]:
    """Scenario 4: Concurrent decode (Compute-bound due to batching)"""
    print(f"\n{'='*60}")
    print(f"Scenario 4: Decode ({concurrent} Concurrent) - Compute-bound (batched)")
    print(f"{'='*60}")
    
    print(f"  Warming up ({config['warmup_requests']} requests)...")
    for i in range(config["warmup_requests"]):
        prompt = generate_short_prompt(i)
        send_request(base_url, model, prompt, max_tokens=config["decode_max_tokens"], timeout=config["timeout"])
    
    results = []
    for run in range(config["test_runs"]):
        prompts = [generate_short_prompt(i) for i in range(concurrent)]
        result = run_concurrent_test(base_url, model, prompts, max_tokens=config["decode_max_tokens"], timeout=config["timeout"])
        
        results.append(result)
        print(f"  Run {run+1}: {result['total_completion_tokens']} tokens in {result['total_time']:.2f}s = {result['decode_throughput']:.0f} tok/s")
    
    if results:
        avg_throughput = sum(r["decode_throughput"] for r in results) / len(results)
        print(f"\n  ✅ Average: {avg_throughput:.0f} tok/s (decode, {concurrent} concurrent)")
        return {"avg_throughput": avg_throughput, "runs": results, "concurrent": concurrent}
    else:
        return {"avg_throughput": 0, "runs": [], "concurrent": concurrent}


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Fair FP8 Benchmark - Same concurrency for Prefill and Decode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Matrix:
  | Scenario              | Concurrency | Bottleneck Type |
  |-----------------------|-------------|-----------------|
  | prefill_single        | 1           | Compute-bound   |
  | prefill_concurrent    | 50          | Compute-bound   |
  | decode_single         | 1           | Memory-bound    |
  | decode_concurrent     | 50          | Compute-bound   |

Examples:
  python benchmark_fair.py --url http://localhost:8080
  python benchmark_fair.py --test prefill_single
  python benchmark_fair.py --test decode_concurrent --concurrent 100
  python benchmark_fair.py --output results_bf16.json
        """
    )
    parser.add_argument("--url", default="http://localhost:8080",
                        help="vLLM server URL")
    parser.add_argument("--model", default=DEFAULT_CONFIG["model"],
                        help="Model name")
    parser.add_argument("--test", 
                        choices=["all", "prefill_single", "prefill_concurrent", 
                                 "decode_single", "decode_concurrent"],
                        default="all",
                        help="Which test to run")
    parser.add_argument("--concurrent", type=int, default=50,
                        help="Number of concurrent requests")
    parser.add_argument("--runs", type=int, default=DEFAULT_CONFIG["test_runs"],
                        help="Number of test runs for averaging")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON file for results")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print config and exit without running")
    
    args = parser.parse_args()
    
    config = DEFAULT_CONFIG.copy()
    config["model"] = args.model
    config["test_runs"] = args.runs
    
    print(f"\n{'='*60}")
    print("Fair FP8 Benchmark - Prefill vs Decode")
    print(f"{'='*60}")
    print(f"Server:      {args.url}")
    print(f"Model:       {args.model}")
    print(f"Concurrent:  {args.concurrent}")
    print(f"Test runs:   {args.runs}")
    print(f"Test:        {args.test}")
    print(f"Timestamp:   {datetime.now().isoformat()}")
    
    if args.dry_run:
        print("\n[DRY RUN] Config validated, exiting.")
        return
    
    print(f"\nChecking server connectivity...")
    try:
        r = requests.get(f"{args.url}/v1/models", timeout=10)
        r.raise_for_status()
        models = r.json().get("data", [])
        print(f"  ✅ Server online, {len(models)} model(s) available")
        if models:
            print(f"  📦 Model: {models[0].get('id', 'unknown')}")
    except Exception as e:
        print(f"  ❌ Server not reachable: {e}")
        print(f"\nPlease start vLLM server first:")
        print(f"  vllm serve {args.model} --port 8080 --max-model-len 4096")
        return
    
    all_results = {
        "config": {
            "url": args.url,
            "model": args.model,
            "concurrent": args.concurrent,
            "timestamp": datetime.now().isoformat(),
        },
        "results": {}
    }
    
    if args.test in ["all", "prefill_single"]:
        all_results["results"]["prefill_single"] = test_prefill_single(args.url, args.model, config)
    
    if args.test in ["all", "prefill_concurrent"]:
        all_results["results"]["prefill_concurrent"] = test_prefill_concurrent(
            args.url, args.model, config, args.concurrent)
    
    if args.test in ["all", "decode_single"]:
        all_results["results"]["decode_single"] = test_decode_single(args.url, args.model, config)
    
    if args.test in ["all", "decode_concurrent"]:
        all_results["results"]["decode_concurrent"] = test_decode_concurrent(
            args.url, args.model, config, args.concurrent)
    
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"| {'Scenario':<25} | {'Concurrency':>11} | {'Throughput':>12} | {'Bottleneck':<15} |")
    print(f"|{'-'*27}|{'-'*13}|{'-'*14}|{'-'*17}|")
    
    scenario_info = {
        "prefill_single": ("1", "Compute-bound"),
        "prefill_concurrent": (str(args.concurrent), "Compute-bound"),
        "decode_single": ("1", "Memory-bound"),
        "decode_concurrent": (str(args.concurrent), "Compute-bound"),
    }
    
    for scenario, info in scenario_info.items():
        if scenario in all_results["results"]:
            throughput = all_results["results"][scenario]["avg_throughput"]
            concurrent_str, bottleneck = info
            print(f"| {scenario:<25} | {concurrent_str:>11} | {throughput:>10.0f} tok/s | {bottleneck:<15} |")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n✅ Results saved to: {args.output}")
    
    print(f"\n{'='*60}")
    print("Next Steps:")
    print(f"{'='*60}")
    print("1. Save BF16 results:  python benchmark_fair.py --output results_bf16.json")
    print("2. Restart vLLM with FP8:")
    print("   vllm serve neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic --port 8080 --max-model-len 4096")
    print("3. Run again:          python benchmark_fair.py --output results_fp8.json")
    print("4. Compare results:    python compare_results.py results_bf16.json results_fp8.json")


if __name__ == "__main__":
    main()
