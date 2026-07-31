#!/usr/bin/env python3
import argparse
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


def secret(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def strip_provider(model: str, provider: str) -> str:
    prefix = provider + "/"
    return model[len(prefix) :] if model.startswith(prefix) else model


def count_valid_ping_calls(tool_calls) -> int:
    valid = 0
    for tool_call in tool_calls if isinstance(tool_calls, list) else []:
        if not isinstance(tool_call, dict) or tool_call.get("type") != "function":
            continue
        function = tool_call.get("function")
        if not isinstance(function, dict) or function.get("name") != "ping":
            continue
        arguments = function.get("arguments")
        try:
            parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("value") == "ok":
            valid += 1
    return valid


def request_candidates(mode: str, api_base: str):
    base = api_base.rstrip("/")
    if mode == "azure_foundry":
        if base.endswith("/openai/v1"):
            return [(base + "/chat/completions", "v1")]
        return [(base + "/openai/v1/chat/completions", "v1")]
    return [(base + "/chat/completions", "openai-compatible")]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate chat-completions function-tool support without printing credentials."
    )
    parser.add_argument(
        "--mode",
        choices=("openai_compatible", "azure_foundry", "fireworks"),
        required=True,
    )
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    parsed = urlparse(args.api_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("--api-base must be an absolute HTTP(S) URL")

    if args.mode == "openai_compatible":
        key = secret("MODEL_API_KEY", "HOSTED_VLLM_API_KEY") or "EMPTY"
        headers = {"Authorization": f"Bearer {key}"}
        model = strip_provider(args.model, "hosted_vllm")
    elif args.mode == "fireworks":
        key = secret("MODEL_API_KEY", "FIREWORKS_AI_API_KEY")
        if not key:
            raise SystemExit("Set FIREWORKS_AI_API_KEY or MODEL_API_KEY")
        headers = {"Authorization": f"Bearer {key}"}
        model = strip_provider(args.model, "fireworks_ai")
    else:
        credential = secret(
            "MODEL_API_KEY",
            "AZURE_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "AZURE_AD_TOKEN",
        )
        if not credential:
            raise SystemExit("Set AZURE_API_KEY, AZURE_OPENAI_API_KEY, AZURE_AD_TOKEN, or MODEL_API_KEY")
        headers = {"Authorization": f"Bearer {credential}"}
        model = strip_provider(args.model, "azure")
        model = strip_provider(model, "hosted_vllm")

    headers.update({"Content-Type": "application/json", "User-Agent": "oss-swebench-playbook-preflight/1"})
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "Call the ping tool once with value ok."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "ping",
                        "description": "Return a value",
                        "parameters": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                        },
                    },
                }
            ],
            "tool_choice": "auto",
            "temperature": 0,
            "max_tokens": 128,
        }
    ).encode()

    attempts = []
    for url, route in request_candidates(args.mode, args.api_base):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                payload = json.loads(response.read())
                choice = (payload.get("choices") or [{}])[0]
                tool_calls = (choice.get("message") or {}).get("tool_calls") or []
                valid_ping_calls = count_valid_ping_calls(tool_calls)
                result = {
                    "state": "PASS" if valid_ping_calls else "FAIL",
                    "mode": args.mode,
                    "route": route,
                    "http_status": response.status,
                    "tool_calls": len(tool_calls),
                    "valid_ping_calls": valid_ping_calls,
                    "finish_reason": choice.get("finish_reason"),
                    "request_id_present": bool(
                        response.headers.get("x-request-id")
                        or response.headers.get("apim-request-id")
                    ),
                }
                print(json.dumps(result, sort_keys=True))
                raise SystemExit(0 if valid_ping_calls else 4)
        except urllib.error.HTTPError as error:
            attempts.append({"route": route, "http_status": error.code})
            print(
                json.dumps(
                    {
                        "state": "FAIL",
                        "mode": args.mode,
                        "attempts": attempts,
                        "error_body_bytes": len(error.read()),
                    },
                    sort_keys=True,
                )
            )
            raise SystemExit(3)

    print(json.dumps({"state": "FAIL", "mode": args.mode, "attempts": attempts}, sort_keys=True))
    raise SystemExit(3)


if __name__ == "__main__":
    main()