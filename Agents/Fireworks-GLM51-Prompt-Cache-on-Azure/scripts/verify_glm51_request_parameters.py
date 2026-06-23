#!/usr/bin/env python3
"""Verify Azure AI Foundry Fireworks GLM-5.1 request parameters.

This script sends real Chat Completions requests to an Azure AI Foundry
Fireworks deployment and checks whether request parameters are accepted.

It intentionally does not contain endpoint, deployment name, subscription ID,
resource group, API key, or bearer token. Pass those through arguments or
environment variables.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify request parameter acceptance and cache behavior on Azure Fireworks GLM-5.1."
    )
    parser.add_argument("--endpoint", default=os.getenv("FIREWORKS_AZURE_ENDPOINT"), help="Azure AI Services endpoint")
    parser.add_argument("--deployment", default=os.getenv("FIREWORKS_DEPLOYMENT"), help="Azure AI Foundry Fireworks deployment name")
    parser.add_argument("--api-version", default=os.getenv("FIREWORKS_API_VERSION", "2025-04-01-preview"))
    parser.add_argument("--bearer-token", default=os.getenv("FIREWORKS_BEARER_TOKEN"), help="Microsoft Entra bearer token")
    parser.add_argument("--api-key", default=os.getenv("FIREWORKS_API_KEY"), help="API key, if local auth is enabled")
    parser.add_argument(
        "--use-az-cli-token",
        action="store_true",
        help="Fetch a Microsoft Entra token by running az account get-access-token for cognitiveservices.",
    )
    parser.add_argument("--runs", type=int, default=2, help="Number of repeated calls per case. Use 2 to observe cache warm/repeat.")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output", default="data/request-parameter-verification.jsonl")
    parser.add_argument("--summary", default="data/request-parameter-verification-summary.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print planned cases without sending requests.")
    return parser.parse_args()


def get_az_cli_token() -> str:
    completed = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            "https://cognitiveservices.azure.com",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    token = completed.stdout.strip()
    if not token:
        raise SystemExit("az CLI returned an empty token.")
    return token


def auth_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    bearer_token = args.bearer_token
    if args.use_az_cli_token and not bearer_token:
        bearer_token = get_az_cli_token()
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif args.api_key:
        headers["api-key"] = args.api_key
    else:
        raise SystemExit("Provide --bearer-token, --api-key, FIREWORKS_BEARER_TOKEN, FIREWORKS_API_KEY, or --use-az-cli-token.")
    return headers


def stable_prompt(run_id: str, case_name: str) -> str:
    stable_prefix = " ".join(
        [
            "Azure Fireworks GLM-5.1 request-parameter verification.",
            "This prompt prefix is intentionally stable across repeated calls.",
            "Only request headers and request body parameters change between cases.",
            "The goal is to verify parameter acceptance and cached token accounting.",
        ]
        * 6
    )
    return f"run={run_id}; case={case_name}\n{stable_prefix}\nTask: answer OK."


def cases(run_id: str) -> list[dict[str, Any]]:
    stable_session = f"{run_id}:user-001:chat-001"
    isolation = f"{run_id}:tenant-001"
    return [
        {
            "name": "baseline_no_extra_cache_param",
            "headers": {},
            "body": {"temperature": 0, "max_tokens": 8},
            "expected": "Should be accepted. Repeat may or may not hit same backend without explicit routing.",
        },
        {
            "name": "x_session_affinity_header",
            "headers": {"x-session-affinity": stable_session},
            "body": {"temperature": 0, "max_tokens": 8},
            "expected": "Should be accepted. Header-level stable session routing hint.",
        },
        {
            "name": "user_body_field",
            "headers": {},
            "body": {"temperature": 0, "max_tokens": 8, "user": stable_session},
            "expected": "Should be accepted if Fireworks OpenAI-compatible user field is enabled through Azure path.",
        },
        {
            "name": "prompt_cache_key_body_field",
            "headers": {},
            "body": {"temperature": 0, "max_tokens": 8, "prompt_cache_key": stable_session},
            "expected": "Should be accepted. Fireworks API documents this as preferred session-affinity field.",
        },
        {
            "name": "prompt_cache_key_plus_isolation_key",
            "headers": {},
            "body": {
                "temperature": 0,
                "max_tokens": 8,
                "prompt_cache_key": stable_session,
                "prompt_cache_isolation_key": isolation,
            },
            "expected": "Should be accepted. Isolation key partitions cache namespace; it is not a cache-lift knob.",
        },
        {
            "name": "x_session_affinity_plus_prompt_cache_key",
            "headers": {"x-session-affinity": stable_session},
            "body": {"temperature": 0, "max_tokens": 8, "prompt_cache_key": stable_session},
            "expected": "Should be accepted. Valid combination; compare with x-session-affinity alone.",
        },
        {
            "name": "generation_params_temperature_top_p_max_tokens",
            "headers": {"x-session-affinity": stable_session},
            "body": {"temperature": 0.2, "top_p": 0.9, "max_tokens": 12, "prompt_cache_key": stable_session},
            "expected": "Should be accepted. Generation controls do not fix prompt-cache layout problems.",
        },
        {
            "name": "perf_metrics_in_response",
            "headers": {"x-session-affinity": stable_session},
            "body": {"temperature": 0, "max_tokens": 8, "prompt_cache_key": stable_session, "perf_metrics_in_response": True},
            "expected": "Should be accepted. Body perf_metrics may be null on some Azure non-streaming paths; streaming scripts are safer for TTFT.",
        },
    ]


def send_request(
    url: str,
    base_headers: dict[str, str],
    prompt: str,
    case: dict[str, Any],
    run_number: int,
    timeout: float,
) -> dict[str, Any]:
    headers = dict(base_headers)
    headers.update(case["headers"])
    payload = {"messages": [{"role": "user", "content": prompt}], **case["body"]}
    started = time.perf_counter()
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            elapsed = time.perf_counter() - started
    except urllib.error.HTTPError as error:
        elapsed = time.perf_counter() - started
        return {
            "case": case["name"],
            "run": run_number,
            "accepted": False,
            "http": error.code,
            "elapsed_sec": round(elapsed, 4),
            "error_body": error.read().decode(errors="replace")[:1000],
        }
    except Exception as error:  # noqa: BLE001 - keep diagnostics in JSONL
        elapsed = time.perf_counter() - started
        return {
            "case": case["name"],
            "run": run_number,
            "accepted": False,
            "http": "exception",
            "elapsed_sec": round(elapsed, 4),
            "exception": repr(error),
        }

    usage = body.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    perf = body.get("perf_metrics") or {}
    prompt_tokens = usage.get("prompt_tokens") or 0
    cached_tokens = details.get("cached_tokens") or 0
    return {
        "case": case["name"],
        "run": run_number,
        "accepted": True,
        "http": 200,
        "elapsed_sec": round(elapsed, 4),
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
        "completion_tokens": usage.get("completion_tokens"),
        "server_ttft_sec": perf.get("server-time-to-first-token"),
        "perf_metrics_in_body": bool(perf),
    }


def main() -> None:
    args = parse_args()
    if not args.endpoint or not args.deployment:
        raise SystemExit("Provide --endpoint/--deployment or FIREWORKS_AZURE_ENDPOINT/FIREWORKS_DEPLOYMENT.")

    run_id = f"param-verify-{int(time.time())}"
    all_cases = cases(run_id)
    if args.dry_run:
        print(json.dumps({"run_id": run_id, "cases": all_cases}, indent=2))
        return

    output_path = Path(args.output)
    summary_path = Path(args.summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"{args.endpoint.rstrip('/')}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    base_headers = auth_headers(args)
    results: list[dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as handle:
        start = {"event": "start", "run_id": run_id, "deployment": args.deployment, "runs_per_case": args.runs}
        print(json.dumps(start), file=handle, flush=True)
        print(json.dumps(start), flush=True)
        for case in all_cases:
            prompt = stable_prompt(run_id, case["name"])
            for run_number in range(1, args.runs + 1):
                result = send_request(url, base_headers, prompt, case, run_number, args.timeout)
                result["expected"] = case["expected"]
                results.append(result)
                print(json.dumps(result), file=handle, flush=True)
                print(json.dumps(result), flush=True)

    by_case: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_case.setdefault(result["case"], []).append(result)

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case",
                "accepted_runs",
                "total_runs",
                "repeat_cache_ratio",
                "repeat_cached_tokens",
                "repeat_prompt_tokens",
                "repeat_server_ttft_sec",
                "note",
            ],
        )
        writer.writeheader()
        for case in all_cases:
            rows = by_case[case["name"]]
            accepted = [row for row in rows if row.get("accepted")]
            repeat = rows[-1] if rows else {}
            writer.writerow(
                {
                    "case": case["name"],
                    "accepted_runs": len(accepted),
                    "total_runs": len(rows),
                    "repeat_cache_ratio": repeat.get("cache_ratio"),
                    "repeat_cached_tokens": repeat.get("cached_tokens"),
                    "repeat_prompt_tokens": repeat.get("prompt_tokens"),
                    "repeat_server_ttft_sec": repeat.get("server_ttft_sec"),
                    "note": case["expected"],
                }
            )
    print(json.dumps({"event": "complete", "jsonl": str(output_path), "summary_csv": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()