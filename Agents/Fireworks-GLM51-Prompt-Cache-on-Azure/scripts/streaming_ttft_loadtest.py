#!/usr/bin/env python3
"""Streaming TTFT and generation tokens/sec load test using Hugging Face prompts.

This script samples public prompts from a Hugging Face dataset, sends streaming
Chat Completions requests, and records server-side TTFT from Fireworks
`perf_metrics` plus token usage from the final streaming chunk.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any

import aiohttp
from datasets import load_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run streaming TTFT load test with Hugging Face prompts.")
    parser.add_argument("--endpoint", default=os.getenv("FIREWORKS_AZURE_ENDPOINT"), help="Azure AI Services endpoint")
    parser.add_argument("--deployment", default=os.getenv("FIREWORKS_DEPLOYMENT"), help="Azure AI Foundry deployment name")
    parser.add_argument("--api-version", default=os.getenv("FIREWORKS_API_VERSION", "2025-04-01-preview"))
    parser.add_argument("--bearer-token", default=os.getenv("FIREWORKS_BEARER_TOKEN"), help="Microsoft Entra access token")
    parser.add_argument("--api-key", default=os.getenv("FIREWORKS_API_KEY"), help="API key, if local auth is enabled")
    parser.add_argument("--dataset", default="HuggingFaceH4/ultrachat_200k")
    parser.add_argument("--split", default="test_sft")
    parser.add_argument("--prompt-count", type=int, default=64)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--max-chars", type=int, default=700)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--sessions", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--rounds", nargs="+", default=["cold", "warm"], help="Round names to execute sequentially")
    parser.add_argument("--output-dir", default="data/hf-streaming-run")
    return parser.parse_args()


def auth_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if args.bearer_token:
        headers["Authorization"] = f"Bearer {args.bearer_token}"
    elif args.api_key:
        headers["api-key"] = args.api_key
    else:
        raise SystemExit("Provide FIREWORKS_BEARER_TOKEN or FIREWORKS_API_KEY.")
    return headers


def percentile(values: list[float], p: float) -> float | None:
    values = [value for value in values if value is not None]
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return ordered[int(k)]
    return ordered[lower] * (upper - k) + ordered[upper] * (k - lower)


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_user_prompt(row: dict[str, Any]) -> str:
    for message in row.get("messages") or []:
        if message.get("role") == "user" and message.get("content"):
            return " ".join(message["content"].split())
    return " ".join((row.get("prompt") or "").split())


def sample_prompts(args: argparse.Namespace) -> list[dict[str, Any]]:
    dataset = load_dataset(args.dataset, split=args.split, streaming=True)
    prompts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in dataset:
        text = first_user_prompt(row)
        if args.min_chars <= len(text) <= args.max_chars and text not in seen:
            seen.add(text)
            prompts.append(
                {
                    "id": len(prompts),
                    "source_prompt_id": row.get("prompt_id"),
                    "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "prompt_chars": len(text),
                    "prompt": text,
                }
            )
        if len(prompts) >= args.prompt_count:
            break
    if len(prompts) < args.prompt_count:
        raise SystemExit(f"Only sampled {len(prompts)} prompts from {args.dataset}/{args.split}.")
    return prompts


async def run_one(session: aiohttp.ClientSession, args: argparse.Namespace, url: str, base_headers: dict[str, str], prompt_item: dict[str, Any], round_name: str) -> dict[str, Any]:
    session_id = f"hf-ultrachat-session-{prompt_item['id'] % args.sessions:02d}"
    payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer the user request directly and concisely."},
            {"role": "user", "content": prompt_item["prompt"]},
        ],
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "perf_metrics_in_response": True,
    }
    headers = dict(base_headers)
    headers["x-session-affinity"] = session_id
    started = time.perf_counter()
    usage = None
    perf_metrics = None
    streamed_chars = 0
    chunks = 0
    try:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as response:
            async for raw in response.content:
                for raw_line in raw.decode(errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    chunks += 1
                    usage = obj.get("usage") or usage
                    perf_metrics = obj.get("perf_metrics") or perf_metrics
                    for choice in obj.get("choices") or []:
                        delta = choice.get("delta") or {}
                        streamed_chars += len(delta.get("content") or "")
            elapsed = time.perf_counter() - started
            usage = usage or {}
            details = usage.get("prompt_tokens_details") or {}
            perf_metrics = perf_metrics or {}
            completion_tokens = usage.get("completion_tokens") or 0
            generation_sec = as_float(perf_metrics.get("generation-duration"))
            processing_sec = as_float(perf_metrics.get("server-processing-time"))
            prompt_tokens = usage.get("prompt_tokens") or 0
            cached_tokens = details.get("cached_tokens") or 0
            return {
                "round": round_name,
                "idx": prompt_item["id"],
                "prompt_sha256": prompt_item["prompt_sha256"],
                "prompt_chars": prompt_item["prompt_chars"],
                "session": session_id,
                "http": response.status,
                "elapsed_sec": round(elapsed, 4),
                "server_ttft_sec": as_float(perf_metrics.get("server-time-to-first-token")),
                "server_processing_sec": processing_sec,
                "generation_sec": generation_sec,
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": usage.get("total_tokens"),
                "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
                "output_tokens_per_sec_generation": round(completion_tokens / generation_sec, 4) if generation_sec else None,
                "output_tokens_per_sec_processing": round(completion_tokens / processing_sec, 4) if processing_sec else None,
                "chunks": chunks,
                "streamed_chars": streamed_chars,
            }
    except Exception as error:  # noqa: BLE001 - keep load-test failures in JSONL
        elapsed = time.perf_counter() - started
        return {"round": round_name, "idx": prompt_item["id"], "session": session_id, "exception": repr(error), "elapsed_sec": round(elapsed, 4)}


def summarize(round_name: str, prompts: list[dict[str, Any]], results: list[dict[str, Any]], wall_sec: float, args: argparse.Namespace) -> dict[str, Any]:
    ok = [item for item in results if item.get("http") == 200]
    http_counts: dict[str, int] = {}
    for item in results:
        key = str(item.get("http") or "exception")
        http_counts[key] = http_counts.get(key, 0) + 1

    def values(key: str) -> list[float]:
        return [item[key] for item in ok if item.get(key) is not None]

    prompt_tokens = sum(int(item.get("prompt_tokens") or 0) for item in ok)
    cached_tokens = sum(int(item.get("cached_tokens") or 0) for item in ok)
    completion_tokens = sum(int(item.get("completion_tokens") or 0) for item in ok)
    prompt_lengths = [item["prompt_chars"] for item in prompts]
    return {
        "round": round_name,
        "dataset": args.dataset,
        "split": args.split,
        "prompt_count": len(prompts),
        "concurrency": args.concurrency,
        "sessions": args.sessions,
        "max_tokens": args.max_tokens,
        "wall_sec": round(wall_sec, 4),
        "success": len(ok),
        "errors": len(results) - len(ok),
        "http_counts": http_counts,
        "prompt_chars": {"min": min(prompt_lengths), "median": statistics.median(prompt_lengths), "max": max(prompt_lengths)},
        "tokens": {
            "prompt": prompt_tokens,
            "cached": cached_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens,
            "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
        },
        "server_ttft_sec": {
            "avg": round(statistics.mean(values("server_ttft_sec")), 4) if values("server_ttft_sec") else None,
            "p50": round(percentile(values("server_ttft_sec"), 50), 4) if values("server_ttft_sec") else None,
            "p90": round(percentile(values("server_ttft_sec"), 90), 4) if values("server_ttft_sec") else None,
            "p95": round(percentile(values("server_ttft_sec"), 95), 4) if values("server_ttft_sec") else None,
            "p99": round(percentile(values("server_ttft_sec"), 99), 4) if values("server_ttft_sec") else None,
        },
        "output_tokens_per_sec_generation": {
            "avg": round(statistics.mean(values("output_tokens_per_sec_generation")), 4) if values("output_tokens_per_sec_generation") else None,
            "p50": round(percentile(values("output_tokens_per_sec_generation"), 50), 4) if values("output_tokens_per_sec_generation") else None,
            "p10": round(percentile(values("output_tokens_per_sec_generation"), 10), 4) if values("output_tokens_per_sec_generation") else None,
            "p90": round(percentile(values("output_tokens_per_sec_generation"), 90), 4) if values("output_tokens_per_sec_generation") else None,
        },
        "throughput": {"completion_tps_wall": round(completion_tokens / wall_sec, 4) if wall_sec else None, "requests_per_sec_wall": round(len(ok) / wall_sec, 4) if wall_sec else None},
    }


async def run_round(round_name: str, prompts: list[dict[str, Any]], args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    endpoint = args.endpoint.rstrip("/")
    url = f"{endpoint}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    base_headers = auth_headers(args)
    connector = aiohttp.TCPConnector(limit=args.concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        started = time.perf_counter()
        results = await asyncio.gather(*[run_one(session, args, url, base_headers, prompt, round_name) for prompt in prompts])
        wall_sec = time.perf_counter() - started
    output_path = output_dir / f"hf_stream_{round_name}.jsonl"
    with output_path.open("w", encoding="utf-8") as handle:
        for item in results:
            print(json.dumps(item), file=handle)
    summary = summarize(round_name, prompts, results, wall_sec, args)
    (output_dir / f"hf_stream_{round_name}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


async def main_async(args: argparse.Namespace) -> None:
    if not args.endpoint or not args.deployment:
        raise SystemExit("--endpoint and --deployment are required.")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompts = sample_prompts(args)
    prompt_metadata = {
        "dataset": args.dataset,
        "split": args.split,
        "selection": f"first {args.prompt_count} unique first-user prompts with {args.min_chars} <= chars <= {args.max_chars}",
        "prompt_count": len(prompts),
        "prompts": [{key: item[key] for key in ["id", "source_prompt_id", "prompt_sha256", "prompt_chars"]} for item in prompts],
    }
    (output_dir / "hf_prompt_sample_metadata.json").write_text(json.dumps(prompt_metadata, indent=2), encoding="utf-8")
    summaries = []
    for round_name in args.rounds:
        summaries.append(await run_round(round_name, prompts, args, output_dir))
    (output_dir / "hf_stream_combined_summary.json").write_text(json.dumps({"summaries": summaries}, indent=2), encoding="utf-8")


def main() -> None:
    asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    main()
