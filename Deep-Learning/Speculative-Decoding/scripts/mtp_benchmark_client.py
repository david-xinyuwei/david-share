#!/usr/bin/env python3
"""
Benchmark client for MTP / DFlash speculative decoding on Qwen3.6-27B.
Streaming mode measures approximate TTFT from the first SSE chunk.
--no-stream mode uses usage.completion_tokens for accurate TPS but cannot measure TTFT.

Usage:
  python3 mtp_benchmark_client.py --base-url http://127.0.0.1:8000 --runs 3 --warmup 1 --output results.json
"""
import argparse
import json
import time
import sys
import urllib.request
import os

PROMPTS = {
    "coding": {
        "messages": [
            {"role": "user", "content": "/no_think Write a Python function that implements merge sort. Include type hints and a docstring."}
        ],
        "max_tokens": 512,
    },
    "math": {
        "messages": [
            {"role": "user", "content": "/no_think Solve step by step: If f(x) = 3x^2 - 2x + 1, find f'(x) and evaluate f'(4)."}
        ],
        "max_tokens": 256,
    },
    "chat": {
        "messages": [
            {"role": "user", "content": "/no_think Explain in three sentences why the sky appears blue during the day but red at sunset."}
        ],
        "max_tokens": 256,
    },
}


def do_request(base_url: str, messages: list, max_tokens: int, temperature: float = 0.0) -> dict:
    """Send a chat completion request and measure timing."""
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    t_start = time.perf_counter()
    t_first_token = None
    total_tokens = 0
    content_parts = []

    resp = urllib.request.urlopen(req, timeout=300)
    for raw_line in resp:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data: "):
            continue
        body = line[6:]
        if body == "[DONE]":
            break
        try:
            chunk = json.loads(body)
        except json.JSONDecodeError:
            continue
        delta = chunk.get("choices", [{}])[0].get("delta", {})
        text = delta.get("content") or delta.get("reasoning") or ""
        if text and t_first_token is None:
            t_first_token = time.perf_counter()
        if delta.get("content"):
            content_parts.append(delta["content"])
            total_tokens += 1  # approximate; SSE chunks ≈ tokens for most engines

    t_end = time.perf_counter()
    if t_first_token is None:
        t_first_token = t_end

    return {
        "ttft_s": round(t_first_token - t_start, 4),
        "total_s": round(t_end - t_start, 4),
        "gen_tokens_approx": total_tokens,
        "gen_tps_approx": round(total_tokens / max(t_end - t_first_token, 0.001), 2),
        "content_preview": "".join(content_parts)[:200],
    }


def do_request_non_stream(base_url: str, messages: list, max_tokens: int, temperature: float = 0.0) -> dict:
    """Fallback: non-streaming request using usage.completion_tokens for accurate TPS."""
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    t_start = time.perf_counter()
    resp_bytes = urllib.request.urlopen(req, timeout=300).read()
    t_end = time.perf_counter()

    obj = json.loads(resp_bytes)
    usage = obj.get("usage", {})
    completion_tokens = usage.get("completion_tokens", 0)
    msg = obj["choices"][0]["message"]
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning") or ""
    total_s = t_end - t_start

    return {
        "ttft_s": None,  # not measurable in non-stream
        "total_s": round(total_s, 4),
        "gen_tokens": completion_tokens,
        "gen_tps": round(completion_tokens / max(total_s, 0.001), 2),
        "content_preview": content[:200],
        "reasoning_preview": reasoning[:200],
        "finish_reason": obj["choices"][0].get("finish_reason"),
    }


def run_benchmark(base_url: str, warmup: int, runs: int, use_stream: bool) -> list:
    results = []
    request_fn = do_request if use_stream else do_request_non_stream

    for domain, cfg in PROMPTS.items():
        # warmup
        for w in range(warmup):
            print(f"  warmup {domain} {w+1}/{warmup} ...", end=" ", flush=True)
            try:
                r = request_fn(base_url, cfg["messages"], cfg["max_tokens"])
                print(f"ok ({r.get('total_s',0):.2f}s)")
            except Exception as e:
                print(f"FAIL: {e}")

        # timed runs
        for run_i in range(runs):
            print(f"  run {domain} {run_i+1}/{runs} ...", end=" ", flush=True)
            try:
                r = request_fn(base_url, cfg["messages"], cfg["max_tokens"])
                r["domain"] = domain
                r["run"] = run_i + 1
                results.append(r)
                tps_key = "gen_tps" if "gen_tps" in r else "gen_tps_approx"
                print(f"ok  total={r['total_s']:.2f}s  {tps_key}={r[tps_key]}")
            except Exception as e:
                print(f"FAIL: {e}")
                results.append({"domain": domain, "run": run_i + 1, "error": str(e)})

    return results


def main():
    parser = argparse.ArgumentParser(description="MTP/DFlash benchmark client")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--output", default="benchmark_results.json")
    parser.add_argument("--label", default="unknown", help="Route label (e.g. vllm-mtp, vllm-dflash, llamacpp-mtp)")
    parser.add_argument("--no-stream", action="store_true", help="Use non-streaming API for accurate token count")
    args = parser.parse_args()

    meta = {
        "label": args.label,
        "base_url": args.base_url,
        "runs": args.runs,
        "warmup": args.warmup,
        "stream": not args.no_stream,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
    }
    print(f"Benchmark: {args.label} @ {args.base_url}")
    print(f"  runs={args.runs}, warmup={args.warmup}, stream={not args.no_stream}")

    results = run_benchmark(args.base_url, args.warmup, args.runs, use_stream=not args.no_stream)

    output = {"meta": meta, "results": results}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
