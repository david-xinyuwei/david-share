#!/usr/bin/env python3
"""
SGLang Qwen3.5-122B-A10B-FP8 Benchmark & Function Calling Test
Author: Xinyu Wei (魏新宇)
Date: 2026-03-09

Hardware: Single NC80adis H100 v5 (2× H100 NVL 94GB, TP=2)
Model: Qwen/Qwen3.5-122B-A10B-FP8 (122B total, 10B activated, 256 experts)
Engine: SGLang (latest main branch)

Test Scenarios:
  1. Stability: High concurrency stress test (zero crashes?)
  2. Performance: Concurrency sweep (1→512) with (1024→1024) tokens
  3. Function Calling: tool_choice=auto/required (qwen3_coder format)
  4. ITL Precision: Single-request inter-token latency measurement

Hyperparameters: Same as previous 235B benchmark
  - Input: 1024 tokens, Output: 1024 tokens
  - Streaming mode, 3 runs median
  - Concurrency: 1,2,4,8,16,32,64,128,256,512
"""

import requests
import time
import json
import sys
import argparse
import concurrent.futures
import statistics
from typing import Optional, Tuple, List, Dict


def parse_args():
    parser = argparse.ArgumentParser(description="SGLang Qwen3.5-122B Benchmark")
    parser.add_argument("--url", type=str, default="http://localhost:8000")
    parser.add_argument("--model", type=str, default="Qwen3.5-122B-A10B-FP8")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--mode", type=str, default="all",
                        choices=["all", "stability", "perf", "func", "itl"],
                        help="Test mode")
    parser.add_argument("--max-concurrency", type=int, default=512)
    parser.add_argument("--runs", type=int, default=3,
                        help="Runs per concurrency level (take median)")
    return parser.parse_args()


def generate_prompt(tokens: int) -> str:
    """Generate prompt of approximately `tokens` tokens."""
    base_text = "The quick brown fox jumps over the lazy dog. "
    return (base_text * ((tokens * 4) // len(base_text) + 1))[:tokens * 4]


def single_request(
    url: str, model: str, input_tokens: int, max_output: int,
    stream: bool = True, timeout: int = 600
) -> Tuple[Optional[float], Optional[float], int, List[float]]:
    """
    Send a single request and return (ttft, total_time, token_count, itl_list).
    itl_list contains inter-token latencies in seconds.
    """
    endpoint = f"{url}/v1/chat/completions"
    data = {
        "model": model,
        "messages": [{"role": "user", "content": generate_prompt(input_tokens)}],
        "max_tokens": max_output,
        "stream": stream,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False}
    }

    start = time.time()
    ttft = None
    token_count = 0
    full_content = []
    itl_list = []
    last_token_time = None

    try:
        resp = requests.post(endpoint, json=data, stream=stream, timeout=timeout)
        if resp.status_code != 200:
            return None, None, 0, []

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

                        usage = chunk.get('usage')
                        if usage and 'completion_tokens' in usage:
                            token_count = usage['completion_tokens']

                        choices = chunk.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content')
                            if content:
                                now = time.time()
                                if ttft is None:
                                    ttft = now - start
                                    last_token_time = now
                                else:
                                    itl_list.append(now - last_token_time)
                                    last_token_time = now
                                full_content.append(content)
                    except json.JSONDecodeError:
                        pass

            if token_count == 0 and full_content:
                total_chars = sum(len(c) for c in full_content)
                token_count = max(1, total_chars // 4)
        else:
            result = resp.json()
            token_count = result.get('usage', {}).get('completion_tokens', 0)
            ttft = time.time() - start

    except Exception as e:
        return None, None, 0, []

    total_time = time.time() - start
    if ttft is None:
        ttft = total_time * 0.1
    return ttft, total_time, token_count, itl_list


def bench_concurrent(
    url: str, model: str,
    input_tokens: int, output_tokens: int,
    concurrency: int, total_requests: int = 10,
    timeout: int = 600
) -> Optional[Dict]:
    """Benchmark concurrent requests."""
    print(f"\n  C={concurrency}: {total_requests} requests ...", end="", flush=True)

    results = []
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(single_request, url, model, input_tokens, output_tokens, True, timeout)
            for _ in range(total_requests)
        ]
        for f in concurrent.futures.as_completed(futures):
            ttft, total, tokens, _ = f.result()
            if ttft is not None and tokens > 0:
                results.append((ttft, total, tokens))

    total_time = time.time() - start

    if results:
        completed = len(results)
        failed = total_requests - completed
        qps = completed / total_time
        avg_ttft = sum(r[0] for r in results) / completed
        avg_latency = sum(r[1] for r in results) / completed
        total_tokens = sum(r[2] for r in results)
        throughput = total_tokens / total_time

        status = "OK" if failed == 0 else f"WARN({failed} failed)"
        print(f" {status} | {throughput:.1f} t/s | TTFT={avg_ttft*1000:.0f}ms | QPS={qps:.2f}")

        return {
            "concurrency": concurrency,
            "qps": round(qps, 2),
            "ttft_ms": round(avg_ttft * 1000),
            "latency_s": round(avg_latency, 2),
            "throughput": round(throughput, 1),
            "completed": completed,
            "failed": failed,
            "total_requests": total_requests
        }
    else:
        print(f" FAILED (all {total_requests} requests failed)")
    return None


# ============================================================
# Test 1: Stability (high concurrency stress test)
# ============================================================
def test_stability(args):
    print("\n" + "=" * 70)
    print("TEST 1: STABILITY — High concurrency stress test")
    print(f"  Model: {args.model}")
    print(f"  Config: (1024 → 512) tokens, ramp-up concurrency")
    print("=" * 70)

    # Warmup
    print("\n[Warmup]")
    ttft, total, tokens, _ = single_request(args.url, args.model, 128, 128)
    if tokens > 0:
        print(f"  Warmup OK: {tokens} tokens in {total:.2f}s")
    else:
        print("  Warmup FAILED! Aborting.")
        return False

    concurrency_levels = [1, 4, 8, 16, 32, 64, 128]
    results = []

    for conc in concurrency_levels:
        if conc > args.max_concurrency:
            break
        if conc <= 4:
            total_reqs = 10
        elif conc <= 32:
            total_reqs = conc * 2
        else:
            total_reqs = min(conc * 2, 256)

        r = bench_concurrent(args.url, args.model, 1024, 512, conc, total_reqs, args.timeout)
        if r:
            results.append(r)
            if r['failed'] > r['total_requests'] * 0.3:
                print(f"  ⚠️ >30% failure at C={conc}, stopping ramp up")
                break
        else:
            print(f"  ❌ C={conc} completely failed, stopping")
            break

    # Post-stress health check
    print("\n[Post-stress health check]")
    ttft, total, tokens, _ = single_request(args.url, args.model, 128, 64)
    alive = tokens > 0
    print(f"  Service alive: {'✅ YES' if alive else '❌ NO (CRASHED!)'}")

    # Summary
    print("\n" + "-" * 70)
    print("Stability Summary:")
    print("-" * 70)
    print("| Concurrency | Requests | Completed | Failed | Throughput (t/s) |")
    print("|:-----------:|:--------:|:---------:|:------:|:----------------:|")
    total_sent = 0
    total_failed = 0
    for r in results:
        print(f"| {r['concurrency']:>11} | {r['total_requests']:>8} | {r['completed']:>9} | {r['failed']:>6} | {r['throughput']:>16.1f} |")
        total_sent += r['total_requests']
        total_failed += r['failed']
    print(f"| **Total** | **{total_sent}** | **{total_sent - total_failed}** | **{total_failed}** | — |")

    print(f"\nMax concurrency tested: {results[-1]['concurrency'] if results else 0}")
    print(f"Service alive after stress: {'✅' if alive else '❌'}")

    return alive


# ============================================================
# Test 2: Performance (concurrency sweep, 3 runs median)
# ============================================================
def test_performance(args):
    print("\n" + "=" * 70)
    print("TEST 2: PERFORMANCE — Concurrency sweep (1024 → 1024)")
    print(f"  Model: {args.model}")
    print(f"  Runs per level: {args.runs} (take median)")
    print(f"  Max concurrency: {args.max_concurrency}")
    print("=" * 70)

    # Previous 235B SGLang baseline for comparison
    baseline_235b = {
        "single_tps": 70.1,
        "peak_throughput": 1320.4,
        "peak_concurrency": 128,
        "itl_avg_ms": 13.3
    }

    print(f"\n📌 Previous 235B SGLang Baseline:")
    print(f"   Single: {baseline_235b['single_tps']} t/s, Peak: {baseline_235b['peak_throughput']} t/s @ C={baseline_235b['peak_concurrency']}")
    print(f"   ITL: {baseline_235b['itl_avg_ms']} ms")

    concurrency_levels = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    concurrency_levels = [c for c in concurrency_levels if c <= args.max_concurrency]

    all_results = []

    for conc in concurrency_levels:
        if conc <= 4:
            total_reqs = 10
        elif conc <= 32:
            total_reqs = conc * 2
        else:
            total_reqs = min(conc * 2, 256)

        run_results = []
        for run_idx in range(args.runs):
            r = bench_concurrent(args.url, args.model, 1024, 1024, conc, total_reqs, args.timeout)
            if r:
                run_results.append(r)
            else:
                break

        if run_results:
            # Take median by throughput
            run_results.sort(key=lambda x: x['throughput'])
            median_r = run_results[len(run_results) // 2]
            all_results.append(median_r)

            if median_r['failed'] > median_r['total_requests'] * 0.5:
                print(f"  ⚠️ >50% failures at C={conc}, stopping")
                break
        else:
            print(f"  ❌ C={conc} completely failed, stopping")
            break

    # Summary table
    print("\n" + "-" * 70)
    print("Performance Summary: Qwen3.5-122B-A10B-FP8 (1024 → 1024)")
    print("-" * 70)
    print("| Concurrency | Throughput (t/s) | TTFT (ms) | QPS  |")
    print("|:-----------:|:----------------:|:---------:|:----:|")
    for r in all_results:
        print(f"| {r['concurrency']:>11} | {r['throughput']:>16.1f} | {r['ttft_ms']:>9} | {r['qps']:>4.2f} |")

    if all_results:
        single = all_results[0]
        peak = max(all_results, key=lambda x: x['throughput'])
        print(f"\n📊 Qwen3.5-122B Results:")
        print(f"   Single request: {single['throughput']:.1f} t/s (TTFT={single['ttft_ms']}ms)")
        print(f"   Peak: {peak['throughput']:.1f} t/s @ C={peak['concurrency']}")
        print(f"\n📊 vs Previous 235B SGLang:")
        print(f"   Single: {single['throughput']:.1f} vs {baseline_235b['single_tps']:.1f} t/s "
              f"({single['throughput']/baseline_235b['single_tps']:.2f}x)")
        print(f"   Peak:   {peak['throughput']:.1f} vs {baseline_235b['peak_throughput']:.1f} t/s "
              f"({peak['throughput']/baseline_235b['peak_throughput']:.2f}x)")

    return all_results


# ============================================================
# Test 3: Function Calling (qwen3_coder format)
# ============================================================
def test_function_calling(args):
    print("\n" + "=" * 70)
    print("TEST 3: FUNCTION CALLING — qwen3_coder format")
    print(f"  Model: {args.model}")
    print("=" * 70)

    endpoint = f"{args.url}/v1/chat/completions"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a given city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                    },
                    "required": ["city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_database",
                "description": "Search for records in a database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results"}
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    test_cases = [
        {
            "name": "3a. tool_choice=auto (should call tool)",
            "messages": [{"role": "user", "content": "What's the weather in Beijing today?"}],
            "tool_choice": "auto",
            "expect_tool": True
        },
        {
            "name": "3b. tool_choice=required (must call tool)",
            "messages": [{"role": "user", "content": "Tell me about the weather in Shanghai"}],
            "tool_choice": "required",
            "expect_tool": True
        },
        {
            "name": "3c. tool_choice=auto (no tool needed)",
            "messages": [{"role": "user", "content": "What is 2 + 3?"}],
            "tool_choice": "auto",
            "expect_tool": False
        },
        {
            "name": "3d. Specific tool choice",
            "messages": [{"role": "user", "content": "Find information about AI agents"}],
            "tool_choice": {"type": "function", "function": {"name": "search_database"}},
            "expect_tool": True,
            "expect_tool_name": "search_database"
        },
        {
            "name": "3e. tool_choice=required (streaming)",
            "messages": [{"role": "user", "content": "What's the temperature in Tokyo?"}],
            "tool_choice": "required",
            "expect_tool": True,
            "stream": True
        }
    ]

    passed = 0
    failed = 0

    for tc in test_cases:
        print(f"\n--- {tc['name']} ---")
        data = {
            "model": args.model,
            "messages": tc["messages"],
            "tools": tools,
            "tool_choice": tc["tool_choice"],
            "max_tokens": 256,
            "temperature": 0,
            "stream": tc.get("stream", False)
        }

        try:
            start = time.time()
            resp = requests.post(endpoint, json=data, timeout=args.timeout,
                                stream=tc.get("stream", False))

            if resp.status_code != 200:
                print(f"  ❌ HTTP {resp.status_code}: {resp.text[:300]}")
                failed += 1
                continue

            if tc.get("stream", False):
                tool_calls_parts = {}
                content_parts = []
                for line in resp.iter_lines():
                    if not line or not line.startswith(b'data: '):
                        continue
                    data_str = line[6:].decode('utf-8')
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            if delta.get('tool_calls'):
                                for tc_part in delta['tool_calls']:
                                    idx = tc_part.get('index', 0)
                                    if idx not in tool_calls_parts:
                                        tool_calls_parts[idx] = {'name': '', 'arguments': ''}
                                    fn = tc_part.get('function', {})
                                    if fn.get('name'):
                                        tool_calls_parts[idx]['name'] = fn['name']
                                    if fn.get('arguments'):
                                        tool_calls_parts[idx]['arguments'] += fn['arguments']
                            if delta.get('content'):
                                content_parts.append(delta['content'])
                    except json.JSONDecodeError:
                        pass

                elapsed = time.time() - start
                has_tool = len(tool_calls_parts) > 0

                if has_tool and tc.get("expect_tool"):
                    for idx, info in tool_calls_parts.items():
                        print(f"  Tool: {info['name']}({info['arguments']})")
                    print(f"  ✅ PASS (stream, {elapsed:.2f}s)")
                    passed += 1
                elif not has_tool and not tc.get("expect_tool"):
                    print(f"  Content: {''.join(content_parts)[:100]}...")
                    print(f"  ✅ PASS (no tool, stream, {elapsed:.2f}s)")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: expect_tool={tc.get('expect_tool')}, got_tool={has_tool}")
                    failed += 1
            else:
                result = resp.json()
                elapsed = time.time() - start
                msg = result['choices'][0]['message']
                has_tool = bool(msg.get('tool_calls'))

                if has_tool:
                    for tc_item in msg['tool_calls']:
                        fn = tc_item.get('function', {})
                        print(f"  Tool: {fn.get('name')}({fn.get('arguments')})")

                if has_tool and tc.get("expect_tool"):
                    if tc.get("expect_tool_name"):
                        actual = msg['tool_calls'][0]['function']['name']
                        if actual == tc['expect_tool_name']:
                            print(f"  ✅ PASS (correct tool: {actual}, {elapsed:.2f}s)")
                            passed += 1
                        else:
                            print(f"  ❌ FAIL: Expected {tc['expect_tool_name']}, got {actual}")
                            failed += 1
                    else:
                        print(f"  ✅ PASS ({elapsed:.2f}s)")
                        passed += 1
                elif not has_tool and not tc.get("expect_tool"):
                    print(f"  Content: {msg.get('content', '')[:100]}...")
                    print(f"  ✅ PASS (no tool as expected, {elapsed:.2f}s)")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: expect_tool={tc.get('expect_tool')}, got_tool={has_tool}")
                    failed += 1

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Function Calling Results: {passed}/{passed+failed} passed")
    print(f"{'=' * 40}")
    return passed, failed


# ============================================================
# Test 4: ITL Precision (single-request, detailed timing)
# ============================================================
def test_itl_precision(args):
    print("\n" + "=" * 70)
    print("TEST 4: ITL PRECISION — Single-request inter-token latency")
    print(f"  Model: {args.model}")
    print("=" * 70)

    scenarios = [
        ("Short CN (128→512)", 128, 512),
        ("Medium EN (512→1024)", 512, 1024),
        ("Long EN (1024→1024)", 1024, 1024),
        ("Long CN (1024→1024)", 1024, 1024),
    ]

    results = []

    for name, inp, out in scenarios:
        print(f"\n  {name}: ", end="", flush=True)
        ttft, total, tokens, itl_list = single_request(
            args.url, args.model, inp, out, stream=True, timeout=args.timeout
        )
        if tokens > 0 and itl_list:
            itl_avg = statistics.mean(itl_list) * 1000  # ms
            itl_p50 = statistics.median(itl_list) * 1000
            itl_p99 = sorted(itl_list)[int(len(itl_list) * 0.99)] * 1000 if len(itl_list) > 10 else max(itl_list) * 1000
            tps = tokens / (total - ttft) if total > ttft else tokens / total

            print(f"TTFT={ttft*1000:.0f}ms | ITL avg={itl_avg:.1f}ms p50={itl_p50:.1f}ms p99={itl_p99:.1f}ms | TPS={tps:.1f}")
            results.append({
                "scenario": name,
                "ttft_ms": round(ttft * 1000),
                "itl_avg_ms": round(itl_avg, 1),
                "itl_p50_ms": round(itl_p50, 1),
                "itl_p99_ms": round(itl_p99, 1),
                "tps": round(tps, 1),
                "tokens": tokens
            })
        else:
            print("FAILED")

    # Summary table
    print("\n" + "-" * 70)
    print("ITL Precision Summary:")
    print("-" * 70)
    print("| Scenario | TTFT (ms) | ITL avg (ms) | ITL P50 (ms) | ITL P99 (ms) | TPS |")
    print("|----------|:---------:|:------------:|:------------:|:------------:|:---:|")
    for r in results:
        print(f"| {r['scenario']} | {r['ttft_ms']} | {r['itl_avg_ms']} | {r['itl_p50_ms']} | {r['itl_p99_ms']} | {r['tps']} |")

    return results


# ============================================================
# Main
# ============================================================
def main():
    args = parse_args()

    print("=" * 70)
    print("SGLang Qwen3.5-122B-A10B-FP8 Benchmark Suite")
    print(f"  Server: {args.url}")
    print(f"  Model: {args.model}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Hardware: NC80adis H100 v5 (2× H100 NVL 94GB, TP=2)")
    print(f"  Mode: {args.mode}")
    print("=" * 70)

    if args.mode in ["all", "stability"]:
        stable = test_stability(args)
        if not stable and args.mode == "all":
            print("\n🔴 Service crashed! Skipping remaining tests.")
            return

    if args.mode in ["all", "perf"]:
        test_performance(args)

    if args.mode in ["all", "func"]:
        test_function_calling(args)

    if args.mode in ["all", "itl"]:
        test_itl_precision(args)

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
