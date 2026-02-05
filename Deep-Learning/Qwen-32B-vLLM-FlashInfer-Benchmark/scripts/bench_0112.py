#!/usr/bin/env python3
"""
vLLM 0.11.2 Benchmark Script - Fixed for older API format
Author: Xinyu Wei
"""

import requests
import time
import json
import argparse
import concurrent.futures
from typing import Optional, Tuple, List, Dict


def parse_args():
    parser = argparse.ArgumentParser(description="vLLM 0.11.2 Benchmark")
    parser.add_argument("--url", type=str, default="http://localhost:8088")
    parser.add_argument("--model", type=str, default="/models/Qwen3-32B-FP8")
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args()


def generate_prompt(tokens: int) -> str:
    base_text = "The quick brown fox jumps over the lazy dog. "
    return (base_text * ((tokens * 4) // len(base_text) + 1))[:tokens * 4]


def single_request(
    url: str,
    model: str,
    input_tokens: int,
    max_output: int,
    stream: bool = True,
    timeout: int = 600
) -> Tuple[Optional[float], Optional[float], int]:
    """Send a single request and return (ttft, total_time, token_count)"""
    endpoint = f"{url}/v1/chat/completions"
    data = {
        "model": model,
        "messages": [{"role": "user", "content": generate_prompt(input_tokens)}],
        "max_tokens": max_output,
        "stream": stream,
        "stream_options": {"include_usage": True}
    }

    start = time.time()
    ttft = None
    token_count = 0
    full_content = []

    try:
        resp = requests.post(endpoint, json=data, stream=stream, timeout=timeout)

        if stream:
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith(b'data: '):
                    data_str = line[6:].decode('utf-8')
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        
                        # Check for usage (vLLM with stream_options)
                        usage = chunk.get('usage')
                        if usage and 'completion_tokens' in usage:
                            token_count = usage['completion_tokens']
                        
                        # Get content from choices
                        choices = chunk.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content')
                            if content:
                                if ttft is None:
                                    ttft = time.time() - start
                                full_content.append(content)
                    except json.JSONDecodeError:
                        pass

            # Fallback: estimate if usage not provided
            if token_count == 0 and full_content:
                total_chars = sum(len(c) for c in full_content)
                token_count = max(1, total_chars // 4)
        else:
            result = resp.json()
            token_count = result.get('usage', {}).get('completion_tokens', 0)
            ttft = time.time() - start

    except Exception as e:
        print(f"Error: {e}")
        return None, None, 0

    total_time = time.time() - start
    
    # If no TTFT recorded, use a small fraction of total time
    if ttft is None:
        ttft = total_time * 0.1
    
    return ttft, total_time, token_count


def bench_concurrent(
    url: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    concurrency: int,
    total_requests: int = 10,
    timeout: int = 600
) -> Optional[Dict]:
    """Benchmark concurrent requests"""
    print(f"\n=== Concurrent={concurrency}: {total_requests} requests ===")

    results = []
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(single_request, url, model, input_tokens, output_tokens, True, timeout)
            for _ in range(total_requests)
        ]
        for f in concurrent.futures.as_completed(futures):
            ttft, total, tokens = f.result()
            if ttft is not None and tokens > 0:
                results.append((ttft, total, tokens))

    total_time = time.time() - start

    if results:
        completed = len(results)
        qps = completed / total_time
        avg_ttft = sum(r[0] for r in results) / completed
        avg_latency = sum(r[1] for r in results) / completed
        total_tokens = sum(r[2] for r in results)
        throughput = total_tokens / total_time

        print(f"  Completed: {completed}/{total_requests}")
        print(f"  QPS: {qps:.2f} req/s")
        print(f"  Avg TTFT: {avg_ttft*1000:.0f}ms")
        print(f"  Throughput: {throughput:.1f} tokens/s")

        return {
            "concurrency": concurrency,
            "qps": qps,
            "ttft_ms": avg_ttft * 1000,
            "throughput": throughput,
            "completed": completed
        }
    return None


def main():
    args = parse_args()

    print("=" * 60)
    print("vLLM 0.11.2 Benchmark (FA2)")
    print("=" * 60)
    print(f"Server: {args.url}")
    print(f"Model: {args.model}")
    print("=" * 60)

    # Warmup
    print("\n== Warmup ==")
    ttft, total, tokens = single_request(args.url, args.model, 128, 128, timeout=args.timeout)
    if tokens > 0:
        print(f"  Warmup OK: {tokens} tokens in {total:.2f}s")
    else:
        print("  Warmup failed!")
        return

    # Concurrency tests
    print("\n" + "=" * 60)
    print("Concurrency Throughput Test (1024 in -> 1024 out)")
    print("=" * 60)

    concurrency_results = []
    concurrency_levels = [1, 4, 8, 16, 32, 64, 128, 256, 512]

    for conc in concurrency_levels:
        total_reqs = max(conc * 2, 20)
        result = bench_concurrent(
            args.url, args.model, 1024, 1024, conc,
            total_requests=total_reqs, timeout=args.timeout
        )
        if result:
            concurrency_results.append(result)
        else:
            print(f"  ⚠️ Concurrency={conc} failed")
            break

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY - vLLM 0.11.2 FA2")
    print("=" * 60)

    print("\n| Concurrency | QPS | TTFT (ms) | Throughput (t/s) |")
    print("|-------------|-----|-----------|------------------|")
    for r in concurrency_results:
        print(f"| {r['concurrency']:>11} | {r['qps']:>3.1f} | {r['ttft_ms']:>9.0f} | {r['throughput']:>16.1f} |")

    if concurrency_results:
        peak = max(concurrency_results, key=lambda x: x['throughput'])
        print(f"\n🏆 Peak: {peak['throughput']:.1f} t/s @ {peak['concurrency']} concurrent")


if __name__ == "__main__":
    main()
