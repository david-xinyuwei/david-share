#!/usr/bin/env python3
"""Minimal Azure AI Foundry Fireworks chat call with prompt-cache-friendly settings."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one prompt-cache-friendly Fireworks chat request.")
    parser.add_argument("--endpoint", default=os.getenv("FIREWORKS_AZURE_ENDPOINT"), help="Azure AI Services endpoint")
    parser.add_argument("--deployment", default=os.getenv("FIREWORKS_DEPLOYMENT"), help="Azure AI Foundry deployment name")
    parser.add_argument("--api-version", default=os.getenv("FIREWORKS_API_VERSION", "2025-04-01-preview"))
    parser.add_argument("--bearer-token", default=os.getenv("FIREWORKS_BEARER_TOKEN"), help="Microsoft Entra token")
    parser.add_argument("--api-key", default=os.getenv("FIREWORKS_API_KEY"), help="API key, if local auth is enabled")
    parser.add_argument("--user-id", default="user-123", help="Stable end-user identifier")
    parser.add_argument("--conversation-id", default="chat-456", help="Stable conversation/session identifier")
    parser.add_argument("--request-id", default="req-789", help="Volatile request id placed at the prompt tail")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true", help="Print request URL, headers, and payload without sending")
    return parser.parse_args()


def build_request(args: argparse.Namespace) -> tuple[str, dict[str, str], dict[str, object]]:
    if not args.endpoint or not args.deployment:
        raise SystemExit("Provide --endpoint/--deployment or FIREWORKS_AZURE_ENDPOINT/FIREWORKS_DEPLOYMENT.")
    if not args.bearer_token and not args.api_key:
        raise SystemExit("Provide --bearer-token or --api-key, or set FIREWORKS_BEARER_TOKEN/FIREWORKS_API_KEY.")

    endpoint = args.endpoint.rstrip("/")
    session_key = f"{args.user_id}:{args.conversation_id}"

    stable_persona = """
You are a warm AI companion. Be concise, supportive, and practical.
Do not mention internal cache, routing, or benchmark details to the user.
""".strip()

    stable_memory_items = [
        "The user prefers short replies with one concrete next step.",
        "The user values gentle encouragement over direct criticism.",
        "The user is building a calmer evening routine.",
    ]
    stable_memory = "\n".join(f"- {item}" for item in stable_memory_items)

    static_app_policy = """
Prompt layout rules:
1. Stable persona and policy first.
2. Stable memory in deterministic order.
3. Conversation history in chronological order.
4. Current user message and volatile request context last.
""".strip()

    current_user_message = "I feel tired today. Help me decide one small next step."
    volatile_tail_context = f"request_id={args.request_id}"

    messages = [
        {
            "role": "system",
            "content": f"{stable_persona}\n\nStable user memory:\n{stable_memory}\n\n{static_app_policy}",
        },
        {
            "role": "user",
            "content": f"{current_user_message}\n\nVolatile context, placed last:\n{volatile_tail_context}",
        },
    ]

    url = f"{endpoint}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    payload: dict[str, object] = {
        "messages": messages,
        "temperature": 0,
        "max_tokens": args.max_tokens,
        "prompt_cache_key": session_key,
        "perf_metrics_in_response": True,
    }
    headers = {"Content-Type": "application/json", "x-session-affinity": session_key}
    if args.bearer_token:
        headers["Authorization"] = f"Bearer {args.bearer_token}"
    else:
        headers["api-key"] = args.api_key or ""
    return url, headers, payload


def main() -> None:
    args = parse_args()
    url, headers, payload = build_request(args)

    if args.dry_run:
        safe_headers = dict(headers)
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "Bearer <redacted>"
        if "api-key" in safe_headers:
            safe_headers["api-key"] = "<redacted>"
        print(json.dumps({"url": url, "headers": safe_headers, "payload": payload}, indent=2))
        return

    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))

    usage = body.get("usage", {})
    details = usage.get("prompt_tokens_details", {})
    perf = body.get("perf_metrics", {})
    print(json.dumps({
        "answer": body["choices"][0]["message"].get("content"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "cached_tokens": details.get("cached_tokens"),
        "server_ttft_sec": perf.get("server-time-to-first-token"),
        "ttft_note": "If server_ttft_sec is null on your Azure non-streaming path, use streaming_ttft_loadtest.py or companion_multiturn_loadtest.py for TTFT.",
    }, indent=2))


if __name__ == "__main__":
    main()