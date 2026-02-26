#!/usr/bin/env python3
"""
Qwen3-32B-FP8 Full Benchmark Script for vLLM

This script performs comprehensive benchmarking of vLLM inference performance,
measuring QPS, concurrency, TTFT (Time To First Token), and throughput.

Author: Xinyu Wei (魏新宇)
Date: 2026-02-04

Usage:
    python3 full_bench.py [--url URL] [--model MODEL]

Example:
    python3 full_bench.py --url http://localhost:8088 --model ./models/Qwen3-32B-FP8
"""

import requests
import time
import json
import argparse
import concurrent.futures
from typing import Optional, Tuple, List, Dict


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="vLLM Benchmark Script for Qwen3-32B-FP8"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8088",
        help="vLLM server URL (default: http://localhost:8088)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="Qwen3-32B-FP8",
        help="Model name or path (default: Qwen3-32B-FP8)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Request timeout in seconds (default: 600)"
    )
    return parser.parse_args()


def generate_prompt(tokens: int) -> str:
    """
    Generate a prompt with approximately the specified number of tokens.
    
    Args:
        tokens: Target number of tokens (approximate)
    
    Returns:
        Generated prompt string
    """
    base_text = "The quick brown fox jumps over the lazy dog. "
    # Approximate 4 characters per token
    return (base_text * ((tokens * 4) // len(base_text) + 1))[:tokens * 4]


def single_request(
    url: str,
    model: str,
    input_tokens: int,
    max_output: int,
    stream: bool = True,
    timeout: int = 600
) -> Tuple[Optional[float], Optional[float], int]:
    """
    Send a single inference request to vLLM server.
    
    Args:
        url: vLLM server URL
        model: Model name
        input_tokens: Number of input tokens
        max_output: Maximum output tokens
        stream: Whether to use streaming mode
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (TTFT in seconds, total time in seconds, output token count)
    """
    endpoint = f"{url}/v1/chat/completions"
    data = {
        "model": model,
        "messages": [{"role": "user", "content": generate_prompt(input_tokens)}],
        "max_tokens": max_output,
        "stream": stream,
        "stream_options": {"include_usage": True}  # Request usage stats in stream
    }
    
    start = time.time()
    ttft = None
    token_count = 0
    full_content = []  # Collect all content for accurate token counting
    
    try:
        resp = requests.post(endpoint, json=data, stream=stream, timeout=timeout)
        
        if stream:
            for line in resp.iter_lines():
                if line and line.startswith(b'data: '):
                    if line == b'data: [DONE]':
                        break
                    try:
                        chunk = json.loads(line[6:])
                        
                        # Check for usage in the chunk (vLLM 0.15+ with stream_options)
                        usage = chunk.get('usage')
                        if usage and 'completion_tokens' in usage:
                            token_count = usage['completion_tokens']
                        
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content')
                        if content:
                            if ttft is None:
                                ttft = time.time() - start
                            full_content.append(content)
                    except json.JSONDecodeError:
                        pass
            
            # Fallback: estimate tokens if usage not provided
            # Using ~4 characters per token as approximation
            if token_count == 0 and full_content:
                total_chars = sum(len(c) for c in full_content)
                token_count = max(1, total_chars // 4)
        else:
            result = resp.json()
            token_count = result.get('usage', {}).get('completion_tokens', 0)
            ttft = time.time() - start  # Non-streaming has no TTFT
            
    except Exception as e:
        print(f"Error: {e}")
        return None, None, 0
    
    return ttft, time.time() - start, token_count


def bench_single(
    url: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    runs: int = 3,
    timeout: int = 600
) -> Optional[List[float]]:
    """
    Benchmark single-request performance.
    
    Args:
        url: vLLM server URL
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        runs: Number of test runs
        timeout: Request timeout in seconds
    
    Returns:
        List of [avg_ttft, avg_total, avg_tokens, avg_throughput] or None
    """
    print(f"\n=== Single Request: Input {input_tokens} -> Output {output_tokens} ({runs} runs) ===")
    results = []
    
    for i in range(runs):
        ttft, total, tokens = single_request(url, model, input_tokens, output_tokens, timeout=timeout)
        if ttft is not None:
            throughput = tokens / total if total > 0 else 0
            results.append((ttft, total, tokens, throughput))
            print(f"  Run {i+1}: TTFT={ttft*1000:.0f}ms, Total={total:.2f}s, "
                  f"Tokens={tokens}, Throughput={throughput:.1f} t/s")
    
    if results:
        avg = [sum(r[i] for r in results) / len(results) for i in range(4)]
        print(f"  AVG: TTFT={avg[0]*1000:.0f}ms, Total={avg[1]:.2f}s, "
              f"Tokens={avg[2]:.0f}, Throughput={avg[3]:.1f} t/s")
        return avg
    return None


def bench_concurrent(
    url: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    concurrency: int,
    total_requests: int = 10,
    timeout: int = 600
) -> Optional[Dict]:
    """
    Benchmark concurrent request performance.
    
    Args:
        url: vLLM server URL
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        concurrency: Number of concurrent requests
        total_requests: Total number of requests to send
        timeout: Request timeout in seconds
    
    Returns:
        Dictionary with benchmark results or None
    """
    print(f"\n=== Concurrent={concurrency}: Input {input_tokens} -> Output {output_tokens} "
          f"({total_requests} requests) ===")
    
    results = []
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(single_request, url, model, input_tokens, output_tokens, True, timeout)
            for _ in range(total_requests)
        ]
        for f in concurrent.futures.as_completed(futures):
            ttft, total, tokens = f.result()
            if ttft is not None:
                results.append((ttft, total, tokens))
    
    total_time = time.time() - start
    
    if results:
        completed = len(results)
        qps = completed / total_time
        avg_ttft = sum(r[0] for r in results) / completed
        avg_latency = sum(r[1] for r in results) / completed
        total_tokens = sum(r[2] for r in results)
        throughput = total_tokens / total_time
        
        print(f"  Completed: {completed}/{total_requests}, Total Time: {total_time:.2f}s")
        print(f"  QPS: {qps:.2f} req/s")
        print(f"  Avg TTFT: {avg_ttft*1000:.0f}ms")
        print(f"  Avg Latency: {avg_latency:.2f}s")
        print(f"  Throughput: {throughput:.1f} tokens/s")
        
        return {
            "qps": qps,
            "ttft_ms": avg_ttft * 1000,
            "latency_s": avg_latency,
            "throughput": throughput,
            "completed": completed,
            "total_requests": total_requests
        }
    return None


def main():
    """Main benchmark entry point."""
    args = parse_args()
    
    print("=" * 70)
    print("Qwen3-32B-FP8 vLLM Benchmark")
    print("=" * 70)
    print(f"Server URL: {args.url}")
    print(f"Model: {args.model}")
    print(f"Mode: Streaming")
    print("=" * 70)
    
    # Warmup
    print("\n== Warmup ==")
    single_request(args.url, args.model, 128, 128, timeout=args.timeout)
    print("  Warmup complete")
    
    # Part 1: Single request tests
    print("\n\n" + "=" * 50)
    print("Part 1: Single Request Throughput Test")
    print("=" * 50)
    
    r1 = bench_single(args.url, args.model, 1024, 1024, runs=3, timeout=args.timeout)
    r2 = bench_single(args.url, args.model, 10240, 1024, runs=3, timeout=args.timeout)
    
    # Part 2: Concurrency tests
    print("\n\n" + "=" * 50)
    print("Part 2: Concurrency Throughput Test")
    print("=" * 50)
    
    concurrency_results = []
    concurrency_levels = [1, 4, 8, 16, 32, 64, 128, 256, 512]
    
    for conc in concurrency_levels:
        total_reqs = max(conc * 2, 20)
        result = bench_concurrent(
            args.url, args.model, 1024, 1024, conc,
            total_requests=total_reqs, timeout=args.timeout
        )
        if result:
            result["concurrency"] = conc
            concurrency_results.append(result)
        else:
            print(f"  ⚠️ Concurrency={conc} failed, may have reached GPU memory limit")
            break
    
    # Summary
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print("\nEnvironment:")
    print(f"  Model: {args.model}")
    print(f"  Server: {args.url}")
    print("  Mode: Streaming")
    
    print("\nSingle Request Results:")
    print("| Scenario | Input | Output | TTFT (ms) | Throughput (t/s) |")
    print("|----------|-------|--------|-----------|------------------|")
    if r1:
        print(f"| Short    | 1024  | 1024   | {r1[0]*1000:>9.0f} | {r1[3]:>16.1f} |")
    if r2:
        print(f"| Long     | 10240 | 1024   | {r2[0]*1000:>9.0f} | {r2[3]:>16.1f} |")
    
    print("\nConcurrency Test Results (Input=1024, Output=1024):")
    print("| Concurrency | QPS (req/s) | Avg TTFT (ms) | Throughput (t/s) |")
    print("|-------------|-------------|---------------|------------------|")
    for r in concurrency_results:
        print(f"| {r['concurrency']:>11} | {r['qps']:>11.2f} | "
              f"{r['ttft_ms']:>13.0f} | {r['throughput']:>16.1f} |")
    
    # Find peak performance
    if concurrency_results:
        peak = max(concurrency_results, key=lambda x: x['throughput'])
        print(f"\n🏆 Peak Throughput: {peak['throughput']:.1f} t/s "
              f"@ {peak['concurrency']} concurrent requests")


if __name__ == "__main__":
    main()
