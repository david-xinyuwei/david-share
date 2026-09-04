#!/usr/bin/env python3
"""Measure streaming Chat Completions latency and throughput at fixed concurrency levels.

Standard library only so the same bytes can run inside a private-IP ACI. One
fixed prompt, fixed max_tokens, and one credential are used for every request;
only the concurrency level changes. Generated text is never retained.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime as dt
import hashlib
import ipaddress
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ALLOWED_HOST_SUFFIXES = (".services.ai.azure.com", ".openai.azure.com", ".cognitiveservices.azure.com")
# ACI dropped a single ~110 KB stdout line on 2026-09-04, so the result is emitted as short lines.
META_MARKER = "LOAD_TEST_META_JSON="
REQUEST_MARKER = "LOAD_TEST_REQUEST_JSON="
END_MARKER = "LOAD_TEST_END requests="
# ~420 tokens of neutral technical prose; identical for every request so prompt cost is constant.
FIXED_PROMPT = (
    "You are documenting a network validation exercise. Below is the context. "
    "A Microsoft Foundry resource hosts a GlobalManagedCompute deployment of a 32B "
    "parameter language model on a single H100 80GB accelerator. The resource has a "
    "Private Endpoint attached to connection group account, and three Private DNS zones "
    "are linked to a virtual network: privatelink.cognitiveservices.azure.com, "
    "privatelink.openai.azure.com, and privatelink.services.ai.azure.com. A client "
    "outside the virtual network resolves the public address and, once public network "
    "access is disabled, receives HTTP 403 with the message Public access is disabled. "
    "A client inside the virtual network resolves an RFC 1918 address and receives HTTP "
    "200 with a chat.completion object. The public setting is later restored to its saved "
    "value and the outside client receives 200 again. The deployment URL and deployment "
    "name never change during the exercise; only the caller network path and the parent "
    "resource setting change. The validation runner inside the network is an Azure "
    "Container Instance with a private IP in a delegated workload subnet; it is not Azure "
    "Bastion. Token delivery to the container uses an ARM secureValue environment "
    "variable. Request identifiers are retained only as SHA-256 digests and generated "
    "content is discarded. Timestamps establish ordering but are not a latency "
    "distribution. Now write a numbered list of at least forty distinct operational "
    "checks a platform team should perform before moving this configuration to "
    "production. Each item must be one complete sentence of at least twelve words and "
    "must not repeat an earlier item. Do not stop early."
)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_endpoint(endpoint: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host or parsed.port or parsed.username:
        raise ValueError("Endpoint must be a plain https URL without port or userinfo")
    if not any(host.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        raise ValueError("Endpoint host must be an Azure AI account hostname")
    return parsed


def classify_addresses(addresses: list[str]) -> str:
    kinds = set()
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        kinds.add("private" if parsed.is_private else "public")
    if not kinds:
        return "unresolved"
    return kinds.pop() if len(kinds) == 1 else "mixed"


def resolve_addresses(hostname: str) -> list[str]:
    return sorted({info[4][0] for info in socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)})


def token_identity_sha256(token: str) -> str | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return sha256_text(f"{claims.get('tid')}:{claims.get('oid')}")
    except Exception:
        return None


def acquire_token(az_executable: str, token_environment_variable: str) -> str:
    token = os.getenv(token_environment_variable)
    if token:
        return token
    completed = subprocess.run(
        [az_executable, "account", "get-access-token", "--resource",
         "https://cognitiveservices.azure.com/", "--query", "accessToken", "--output", "tsv"],
        check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


def build_auth(args: argparse.Namespace) -> tuple[dict[str, str], str, str | None]:
    api_key = os.getenv(args.api_key_environment_variable)
    if api_key:
        return {"api-key": api_key}, "api-key", None
    token = acquire_token(args.az_executable, args.token_environment_variable)
    return {"Authorization": f"Bearer {token}"}, "entra-bearer", token_identity_sha256(token)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return round(ordered[index], 4)


def parse_sse_events(raw: bytes):
    """Yield parsed JSON objects from a Server-Sent Events byte buffer."""
    for block in raw.replace(b"\r\n", b"\n").split(b"\n\n"):
        for line in block.split(b"\n"):
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if not data or data == b"[DONE]":
                continue
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue


# Keys observed live on the Qwen3 GlobalManagedCompute route (2026-09-04): content, reasoning.
CONTENT_DELTA_KEYS = ("content", "reasoning", "reasoning_content")


def delta_has_content(event: dict) -> bool:
    for choice in event.get("choices") or []:
        delta = choice.get("delta") or {}
        if any(delta.get(key) for key in CONTENT_DELTA_KEYS):
            return True
    return False


def summarize_stream(chunks: list[tuple[float, bytes]], started: float, finished: float) -> dict[str, object]:
    """Compute TTFT and token counts from timestamped SSE chunks; content is discarded."""
    ttft = None
    usage = None
    content_events = 0
    buffer = b""
    for received_at, chunk in chunks:
        buffer += chunk
        # Only complete events are parsed; the remainder is carried to the next chunk.
        head, sep, tail = buffer.rpartition(b"\n\n")
        if not sep:
            continue
        buffer = tail
        for event in parse_sse_events(head + sep):
            if event.get("usage"):
                usage = event["usage"]
            if delta_has_content(event):
                content_events += 1
                if ttft is None:
                    ttft = received_at - started
    for event in parse_sse_events(buffer):
        if event.get("usage"):
            usage = event["usage"]
        if delta_has_content(event):
            content_events += 1
            if ttft is None:
                ttft = finished - started
    completion_tokens = (usage or {}).get("completion_tokens")
    return {
        "ttftSeconds": round(ttft, 4) if ttft is not None else None,
        "e2eSeconds": round(finished - started, 4),
        "contentEvents": content_events,
        "promptTokens": (usage or {}).get("prompt_tokens"),
        "outputTokens": completion_tokens if completion_tokens is not None else content_events,
        "tokenSource": "usage" if completion_tokens is not None else "content-events",
    }


def run_request(endpoint: str, headers: dict[str, str], body: bytes, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(endpoint, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(NoRedirectHandler())
    started = time.perf_counter()
    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    chunks: list[tuple[float, bytes]] = []
    status: int | None = None
    request_id = None
    error = None
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            request_id = response.headers.get("x-request-id") or response.headers.get("apim-request-id")
            while True:
                chunk = response.read1(8192) if hasattr(response, "read1") else response.read(8192)
                if not chunk:
                    break
                chunks.append((time.perf_counter(), chunk))
    except urllib.error.HTTPError as http_error:
        status = http_error.code
        request_id = http_error.headers.get("x-request-id") or http_error.headers.get("apim-request-id")
        error = f"HTTP {http_error.code}"
        http_error.read(4096)
    except Exception as exc:  # network / timeout; message kept short and secret-free
        error = type(exc).__name__
    finished = time.perf_counter()
    record: dict[str, object] = {"startedAtUtc": started_utc, "httpStatus": status,
                                 "requestIdSha256": sha256_text(request_id) if request_id else None, "error": error}
    if status == 200 and error is None:
        record.update(summarize_stream(chunks, started, finished))
        record["passed"] = record["contentEvents"] > 0
    else:
        record.update({"e2eSeconds": round(finished - started, 4), "passed": False})
    return record


def summarize_level(concurrency: int, records: list[dict[str, object]], wall_seconds: float) -> dict[str, object]:
    ok = [r for r in records if r.get("passed")]
    ttft = [r["ttftSeconds"] for r in ok if r.get("ttftSeconds") is not None]
    e2e = [r["e2eSeconds"] for r in ok]
    per_request_tps = [
        r["outputTokens"] / (r["e2eSeconds"] - r["ttftSeconds"])
        for r in ok
        if r.get("ttftSeconds") is not None and r["e2eSeconds"] > r["ttftSeconds"] and r["outputTokens"]
    ]
    total_output = sum(int(r.get("outputTokens") or 0) for r in ok)
    statuses: dict[str, int] = {}
    for r in records:
        key = str(r.get("httpStatus") or r.get("error") or "none")
        statuses[key] = statuses.get(key, 0) + 1
    return {
        "concurrency": concurrency,
        "requests": len(records),
        "succeeded": len(ok),
        "failed": len(records) - len(ok),
        "statusHistogram": statuses,
        "wallSeconds": round(wall_seconds, 3),
        "ttftSecondsP50": percentile(ttft, 0.50),
        "ttftSecondsP95": percentile(ttft, 0.95),
        "e2eSecondsP50": percentile(e2e, 0.50),
        "e2eSecondsP95": percentile(e2e, 0.95),
        "perRequestOutputTokensPerSecondMedian": round(statistics.median(per_request_tps), 2) if per_request_tps else None,
        "aggregateOutputTokensPerSecond": round(total_output / wall_seconds, 2) if wall_seconds > 0 and total_output else None,
        "totalOutputTokens": total_output,
    }


def run_level(endpoint: str, headers: dict[str, str], body: bytes, concurrency: int, count: int, timeout: float) -> tuple[list[dict[str, object]], float]:
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        records = list(pool.map(lambda _: run_request(endpoint, headers, body, timeout), range(count)))
    return records, time.perf_counter() - started


def requests_for_level(concurrency: int, minimum: int) -> int:
    return max(minimum, 2 * concurrency)


def run_load_test(args: argparse.Namespace) -> dict[str, object]:
    parsed = validate_endpoint(args.endpoint)
    addresses = resolve_addresses(parsed.hostname)
    headers, auth_method, identity = build_auth(args)
    body = json.dumps({
        "model": args.deployment,
        "messages": [{"role": "user", "content": FIXED_PROMPT}],
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }).encode("utf-8")
    levels = []
    all_records = []
    for concurrency in args.concurrency:
        count = requests_for_level(concurrency, args.min_requests_per_level)
        records, wall = run_level(args.endpoint, headers, body, concurrency, count, args.timeout)
        for r in records:
            r["concurrency"] = concurrency
        all_records.extend(records)
        levels.append(summarize_level(concurrency, records, wall))
        if args.cooldown_seconds and concurrency != args.concurrency[-1]:
            time.sleep(args.cooldown_seconds)
    result: dict[str, object] = {
        "schemaVersion": 1,
        "label": args.label,
        "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hostnameSha256": sha256_text(parsed.hostname),
        "deploymentSha256": sha256_text(args.deployment),
        "dnsClass": classify_addresses(addresses),
        "addressCount": len(addresses),
        "authMethod": auth_method,
        "identitySha256": identity,
        "promptSha256": sha256_text(FIXED_PROMPT),
        "requestBodySha256": hashlib.sha256(body).hexdigest(),
        "maxTokens": args.max_tokens,
        "sourceSha256": args.source_sha256,
        "levels": levels,
        "requests": all_records,
        "passed": all(level["failed"] == 0 for level in levels) and bool(levels),
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Streaming load test for a Foundry Chat Completions endpoint.")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--label", required=True, help="e.g. public or private")
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8, 16, 32])
    parser.add_argument("--min-requests-per-level", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--cooldown-seconds", type=float, default=5)
    parser.add_argument("--az-executable", default="az")
    parser.add_argument("--api-key-environment-variable", default="AZURE_AI_API_KEY")
    parser.add_argument("--token-environment-variable", default="AZURE_ACCESS_TOKEN")
    parser.add_argument("--source-sha256")
    parser.add_argument("--output")
    return parser


def emit_lines(result: dict[str, object]) -> list[str]:
    """Serialize the result as one meta line, one line per request, and an end marker."""
    requests = result.get("requests") or []
    meta = {key: value for key, value in result.items() if key != "requests"}
    lines = [META_MARKER + json.dumps(meta, sort_keys=True, separators=(",", ":"))]
    lines += [REQUEST_MARKER + json.dumps(r, sort_keys=True, separators=(",", ":")) for r in requests]
    lines.append(f"{END_MARKER}{len(requests)}")
    return lines


def collect_lines(lines: list[str]) -> dict[str, object]:
    """Inverse of emit_lines; raises if the stream is incomplete."""
    meta = None
    requests = []
    expected = None
    for line in lines:
        line = line.strip()
        if line.startswith(META_MARKER):
            meta = json.loads(line[len(META_MARKER):])
        elif line.startswith(REQUEST_MARKER):
            requests.append(json.loads(line[len(REQUEST_MARKER):]))
        elif line.startswith(END_MARKER):
            expected = int(line[len(END_MARKER):])
    if meta is None or expected is None:
        raise ValueError("load test log is missing the meta or end marker")
    if expected != len(requests):
        raise ValueError(f"load test log has {len(requests)} request lines, expected {expected}")
    meta["requests"] = requests
    return meta


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_load_test(args)
    except Exception as error:
        print(json.dumps({"passed": False, "error": str(error)}))
        return 2
    for line in emit_lines(result):
        print(line, flush=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
