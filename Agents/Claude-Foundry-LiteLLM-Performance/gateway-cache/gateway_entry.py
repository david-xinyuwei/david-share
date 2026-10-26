"""Run the frozen benchmark through LiteLLM, changing only route, auth and alias."""
import argparse
import importlib
import json
import os
import runpy
import signal
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

ALIASES = {
    "claude-opus-5-5": "opus55-standard",
    "claude-sonnet-5-5": "sonnet55-standard",
    "claude-haiku-5-5": "haiku55-standard",
}


def check_model_budget():
    directory = os.environ.get("CLAUDE_GATEWAY_BUDGET_ROOT")
    if not directory:
        return
    root = Path(directory)
    spent = 0.0
    files = [*root.glob("**/responses_*.jsonl"), *root.glob("**/cache_results.jsonl")]
    for path in files:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.endswith("\n"):
                    break
                row = json.loads(line)
                if row.get("usage") is None and row.get("status") not in ("client_exception", "http_error"):
                    spent += 3.0
                else:
                    spent += row.get("cost_usd") or 0.0
    if spent >= 95.0:
        record = {"status": "BUDGET_LIMIT", "accounted_usd": spent, "limit_usd": 100,
                  "inflight_reserve_usd": 5}
        (root / "budget-limit.json").write_text(json.dumps(record), encoding="utf-8")
        print(json.dumps(record), file=sys.stderr, flush=True)
        os.kill(os.getpid(), signal.SIGTERM)


class GatewayTokenProvider:
    def get(self):
        check_model_budget()
        key = os.environ.get("CLAUDE_GATEWAY_KEY", "").strip()
        if not key:
            raise RuntimeError("CLAUDE_GATEWAY_KEY is required")
        return key


class GatewayClient(httpx.Client):
    def build_request(self, method, url, **kwargs):
        if method.upper() == "POST" and "content" in kwargs:
            payload = json.loads(kwargs["content"])
            if payload.get("model") not in ALIASES:
                raise ValueError("Unexpected model in gateway benchmark")
            payload["model"] = ALIASES[payload["model"]]
            kwargs["content"] = json.dumps(payload).encode("utf-8")
        return super().build_request(method, url, **kwargs)


def new_gateway_client():
    return GatewayClient(
        timeout=httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0),
        http2=False,
    )


def self_test():
    observed = []

    def receive(request):
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    with GatewayClient(transport=httpx.MockTransport(receive)) as client:
        for model in ALIASES:
            body = {
                "model": model,
                "max_tokens": 128000,
                "stream": True,
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "max"},
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
                "system": [{"type": "text", "text": "Public test context"}],
                "messages": [{"role": "user", "content": "Return OK"}],
            }
            client.post("https://gateway.invalid/v1/messages", content=json.dumps(body).encode())
            expected = dict(body, model=ALIASES[model])
            if observed[-1] != expected:
                raise AssertionError("Gateway adapter changed request semantics")
            if body["model"] != model:
                raise AssertionError("Gateway adapter mutated the original request")
    print(json.dumps({"status": "PASS", "models": len(ALIASES), "model_calls": 0,
                      "only_payload_change": "documented model alias"}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--source")
    parser.add_argument("--gateway-url")
    parser.add_argument("--program", choices=("bench", "cache_test", "probe"))
    args, remaining = parser.parse_known_args()
    if args.self_test:
        self_test()
        return
    if not args.source or not args.gateway_url or not args.program:
        parser.error("--source, --gateway-url and --program are required")
    parsed = urlparse(args.gateway_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/") or parsed.query:
        parser.error("gateway URL must be an HTTPS origin")
    GatewayTokenProvider().get()
    source = Path(args.source).resolve(strict=True)
    sys.path.insert(0, str(source))
    api = importlib.import_module("claude_api")
    api.BASE = args.gateway_url.rstrip("/")
    api.TokenProvider = GatewayTokenProvider
    api.new_client = new_gateway_client
    os.environ["FOUNDRY_ANTHROPIC_BASE"] = api.BASE
    sys.argv = [str(source / (args.program + ".py")), *remaining]
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()