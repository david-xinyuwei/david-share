#!/usr/bin/env python3
"""Prompt-cache probe for Azure AI Foundry Fireworks deployments.

This script intentionally contains no endpoint, deployment, subscription, or key.
Pass the target deployment through arguments and environment variables.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small Fireworks prompt-cache probe matrix.")
    parser.add_argument("--endpoint", default=os.getenv("FIREWORKS_AZURE_ENDPOINT"), help="Azure AI Services endpoint, e.g. https://<account>.cognitiveservices.azure.com/")
    parser.add_argument("--deployment", default=os.getenv("FIREWORKS_DEPLOYMENT"), help="Azure AI Foundry deployment name")
    parser.add_argument("--api-version", default=os.getenv("FIREWORKS_API_VERSION", "2025-04-01-preview"))
    parser.add_argument("--bearer-token", default=os.getenv("FIREWORKS_BEARER_TOKEN"), help="Microsoft Entra access token for https://cognitiveservices.azure.com")
    parser.add_argument("--api-key", default=os.getenv("FIREWORKS_API_KEY"), help="API key, if local auth is enabled")
    parser.add_argument("--output", default="data/cache-probe-output.jsonl")
    parser.add_argument("--max-tokens", type=int, default=4)
    return parser.parse_args()


def build_headers(args: argparse.Namespace, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if args.bearer_token:
        headers["Authorization"] = f"Bearer {args.bearer_token}"
    elif args.api_key:
        headers["api-key"] = args.api_key
    else:
        raise SystemExit("Provide FIREWORKS_BEARER_TOKEN or FIREWORKS_API_KEY.")
    if extra:
        headers.update(extra)
    return headers


def call_chat(args: argparse.Namespace, case: dict[str, object]) -> dict[str, object]:
    endpoint = args.endpoint.rstrip("/")
    url = f"{endpoint}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    payload = {
        "messages": [{"role": "user", "content": case["prompt"]}],
        "max_tokens": args.max_tokens,
        "temperature": 0,
    }
    payload.update(case.get("extra_body", {}))
    headers = build_headers(args, case.get("headers"))
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
            elapsed = time.perf_counter() - started
            usage = data.get("usage") or {}
            details = usage.get("prompt_tokens_details") or {}
            prompt_tokens = usage.get("prompt_tokens") or 0
            cached_tokens = details.get("cached_tokens") or 0
            return {
                "case": case["name"],
                "http": response.status,
                "elapsed_sec": round(elapsed, 4),
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "headers": {key: value for key, value in response.headers.items() if key.lower().startswith(("x-ratelimit", "fireworks"))},
            }
    except urllib.error.HTTPError as error:
        elapsed = time.perf_counter() - started
        return {
            "case": case["name"],
            "http": error.code,
            "elapsed_sec": round(elapsed, 4),
            "error_body": error.read().decode(errors="replace")[:1200],
            "headers": {key: value for key, value in error.headers.items() if key.lower().startswith(("x-ratelimit", "fireworks")) or key.lower() in {"retry-after", "apim-request-id"}},
        }


def main() -> None:
    args = parse_args()
    if not args.endpoint or not args.deployment:
        raise SystemExit("--endpoint and --deployment are required.")

    stable_prefix = (
        "Fireworks GLM prompt-cache probe. "
        "Keep this static prefix unchanged across requests. "
        "Put dynamic request data near the end so exact-prefix caching can work. "
    )
    changed_prefix = stable_prefix.replace("Fireworks GLM", "Fireworks changed GLM", 1)
    cases = [
        {"name": "no_affinity_warm", "prompt": stable_prefix + "\nTail A\nTask: answer OK."},
        {"name": "no_affinity_repeat", "prompt": stable_prefix + "\nTail A\nTask: answer OK."},
        {"name": "affinity_warm", "prompt": stable_prefix + "\nTail B\nTask: answer OK.", "headers": {"x-session-affinity": "cache-probe-session-001"}},
        {"name": "affinity_repeat", "prompt": stable_prefix + "\nTail B\nTask: answer OK.", "headers": {"x-session-affinity": "cache-probe-session-001"}},
        {"name": "affinity_suffix_change", "prompt": stable_prefix + "\nTail B changed\nTask: answer OK.", "headers": {"x-session-affinity": "cache-probe-session-001"}},
        {"name": "affinity_prefix_change", "prompt": changed_prefix + "\nTail B\nTask: answer OK.", "headers": {"x-session-affinity": "cache-probe-session-001"}},
        {"name": "prompt_cache_key_warm", "prompt": stable_prefix + "\nTail C\nTask: answer OK.", "extra_body": {"prompt_cache_key": "cache-probe-key-001"}},
        {"name": "prompt_cache_key_repeat", "prompt": stable_prefix + "\nTail C\nTask: answer OK.", "extra_body": {"prompt_cache_key": "cache-probe-key-001"}},
    ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        start = {"event": "start", "deployment": args.deployment, "case_count": len(cases)}
        print(json.dumps(start), file=handle)
        print(json.dumps(start))
        for case in cases:
            result = call_chat(args, case)
            print(json.dumps(result), file=handle)
            print(json.dumps(result))
        end = {"event": "end", "output": str(output)}
        print(json.dumps(end), file=handle)
        print(json.dumps(end))


if __name__ == "__main__":
    main()
