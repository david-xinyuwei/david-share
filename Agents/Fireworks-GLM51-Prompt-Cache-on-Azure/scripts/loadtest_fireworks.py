#!/usr/bin/env python3
"""Concurrent non-streaming load test for Azure AI Foundry Fireworks deployments.

The latency reported by this script is end-to-end non-streaming response latency,
not server-side time to first token (TTFT). Use a streaming harness if TTFT is
required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any

import aiohttp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a concurrent Fireworks Chat Completions load test.")
    parser.add_argument("--endpoint", default=os.getenv("FIREWORKS_AZURE_ENDPOINT"), help="Azure AI Services endpoint")
    parser.add_argument("--deployment", default=os.getenv("FIREWORKS_DEPLOYMENT"), help="Azure AI Foundry deployment name")
    parser.add_argument("--api-version", default=os.getenv("FIREWORKS_API_VERSION", "2025-04-01-preview"))
    parser.add_argument("--bearer-token", default=os.getenv("FIREWORKS_BEARER_TOKEN"), help="Microsoft Entra access token")
    parser.add_argument("--api-key", default=os.getenv("FIREWORKS_API_KEY"), help="API key, if local auth is enabled")
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--sessions", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--output", default="data/loadtest-output.jsonl")
    parser.add_argument("--summary", default="data/loadtest-summary.json")
    return parser.parse_args()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return ordered[int(k)]
    return ordered[lower] * (upper - k) + ordered[upper] * (k - lower)


def auth_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if args.bearer_token:
        headers["Authorization"] = f"Bearer {args.bearer_token}"
    elif args.api_key:
        headers["api-key"] = args.api_key
    else:
        raise SystemExit("Provide FIREWORKS_BEARER_TOKEN or FIREWORKS_API_KEY.")
    return headers


async def run_one(session: aiohttp.ClientSession, args: argparse.Namespace, url: str, index: int, base_headers: dict[str, str]) -> dict[str, Any]:
    session_id = f"load-session-{index % args.sessions:02d}"
    stable_prefix = (
        "Fireworks GLM-5.1 load-test stable prefix. "
        "This prefix is shared across requests to measure prompt-cache behavior. "
        "Dynamic request identifiers are appended near the end. "
    )
    payload = {
        "messages": [
            {
                "role": "user",
                "content": stable_prefix + f"\nSession={session_id}\nRequest={index}\nTask: produce short numbered tokens.",
            }
        ],
        "max_tokens": args.max_tokens,
        "temperature": 0,
    }
    headers = dict(base_headers)
    headers["x-session-affinity"] = session_id
    started = time.perf_counter()
    try:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
            text = await response.text()
            elapsed = time.perf_counter() - started
            result: dict[str, Any] = {
                "idx": index,
                "session": session_id,
                "http": response.status,
                "elapsed_sec": round(elapsed, 4),
                "headers": {key: value for key, value in response.headers.items() if key.lower().startswith(("x-ratelimit", "fireworks")) or key.lower() in {"retry-after", "apim-request-id"}},
            }
            if response.status == 200:
                data = json.loads(text)
                usage = data.get("usage") or {}
                details = usage.get("prompt_tokens_details") or {}
                prompt_tokens = usage.get("prompt_tokens") or 0
                cached_tokens = details.get("cached_tokens") or 0
                completion_tokens = usage.get("completion_tokens") or 0
                result.update(
                    {
                        "prompt_tokens": prompt_tokens,
                        "cached_tokens": cached_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": usage.get("total_tokens"),
                        "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
                        "completion_tps": round(completion_tokens / elapsed, 4) if elapsed else None,
                    }
                )
            else:
                result["error_body"] = text[:1200]
            return result
    except Exception as error:  # noqa: BLE001 - keep load-test failures visible in JSONL
        elapsed = time.perf_counter() - started
        return {"idx": index, "session": session_id, "exception": repr(error), "elapsed_sec": round(elapsed, 4)}


async def main_async(args: argparse.Namespace) -> None:
    if not args.endpoint or not args.deployment:
        raise SystemExit("--endpoint and --deployment are required.")
    endpoint = args.endpoint.rstrip("/")
    url = f"{endpoint}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    output = Path(args.output)
    summary_path = Path(args.summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    base_headers = auth_headers(args)

    connector = aiohttp.TCPConnector(limit=args.concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        started = time.perf_counter()
        results = await asyncio.gather(*[run_one(session, args, url, index, base_headers) for index in range(args.concurrency)])
        wall_sec = time.perf_counter() - started

    with output.open("w", encoding="utf-8") as handle:
        print(json.dumps({"event": "start", "deployment": args.deployment, "concurrency": args.concurrency, "sessions": args.sessions, "max_tokens": args.max_tokens}), file=handle)
        for item in results:
            print(json.dumps(item), file=handle)

    successes = [item for item in results if item.get("http") == 200]
    latencies = [float(item["elapsed_sec"]) for item in successes]
    prompt_tokens = sum(int(item.get("prompt_tokens") or 0) for item in successes)
    cached_tokens = sum(int(item.get("cached_tokens") or 0) for item in successes)
    completion_tokens = sum(int(item.get("completion_tokens") or 0) for item in successes)
    http_counts: dict[str, int] = {}
    for item in results:
        key = str(item.get("http") or "exception")
        http_counts[key] = http_counts.get(key, 0) + 1

    summary = {
        "deployment": args.deployment,
        "concurrency": args.concurrency,
        "sessions": args.sessions,
        "max_tokens": args.max_tokens,
        "wall_sec": round(wall_sec, 4),
        "success": len(successes),
        "errors": len(results) - len(successes),
        "http_counts": http_counts,
        "response_latency_sec": {
            "avg": round(statistics.mean(latencies), 4) if latencies else None,
            "p50": round(percentile(latencies, 50), 4) if latencies else None,
            "p90": round(percentile(latencies, 90), 4) if latencies else None,
            "p95": round(percentile(latencies, 95), 4) if latencies else None,
            "p99": round(percentile(latencies, 99), 4) if latencies else None,
        },
        "tokens": {
            "prompt": prompt_tokens,
            "cached": cached_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens,
            "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
        },
        "throughput": {
            "completion_tps_wall": round(completion_tokens / wall_sec, 4) if wall_sec else None,
            "requests_per_sec_wall": round(len(successes) / wall_sec, 4) if wall_sec else None,
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    main()
