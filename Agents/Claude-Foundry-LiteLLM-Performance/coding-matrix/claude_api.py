"""Direct client for the Foundry Anthropic Messages API (no gateway).

The measured runs used the benchmark VM's system-assigned managed identity.
DefaultAzureCredential picks that identity on an Azure VM and the Azure CLI
sign-in on a workstation. Every stage (probe, bench, cache test) uses
stream_message(), so timing points are defined in one place.
"""
import datetime
import hashlib
import json
import os
import threading
import time

import httpx
from azure.identity import DefaultAzureCredential

from pricing import PRICES, cost_usd  # noqa: F401  (re-exported for bench.py and cache_test.py)

BASE = os.environ.get("FOUNDRY_ANTHROPIC_BASE", "").rstrip("/")
if not BASE:
    raise SystemExit("Set FOUNDRY_ANTHROPIC_BASE=https://<resource>.services.ai.azure.com/anthropic")
SCOPE = "https://ai.azure.com/.default"
API_VERSION = "2023-06-01"

KEEP_HEADER_PARTS = ("ratelimit", "retry", "region", "request-id", "processing",
                     "upstream", "apim", "anthropic", "x-ms-", "served", "deployment")


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def sha256_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class TokenProvider:
    def __init__(self):
        self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        self._lock = threading.Lock()
        self._token = None

    def get(self):
        with self._lock:
            if self._token is None or self._token.expires_on - time.time() < 300:
                self._token = self._credential.get_token(SCOPE)
            return self._token.token


def new_client():
    timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
    return httpx.Client(timeout=timeout, http2=False)


def _keep_headers(headers):
    kept = {}
    for name, value in headers.items():
        lowered = name.lower()
        if lowered in ("authorization", "set-cookie"):
            continue
        if any(part in lowered for part in KEEP_HEADER_PARTS):
            kept[lowered] = value
    return kept


def _safe_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw[:4000].decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)[:4000]}


def stream_message(client, tokens, body, deadline_s=1800.0, extra_headers=None):
    """POST /v1/messages with stream=true and return one measurement record.

    Times are seconds from just before the request is written. Text is kept;
    thinking text and signatures are not (only their presence and size).
    """
    record = {"sent_utc": utcnow(), "status": None, "http_status": None}
    headers = {
        "Authorization": "Bearer " + tokens.get(),
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
        **(extra_headers or {}),
    }
    payload = json.dumps(body).encode("utf-8")
    timing = {}
    blocks = {}
    usage = {}
    text_parts = []
    stop_reason = None
    events = 0
    event_types = {}
    start = time.perf_counter()

    def mark(name):
        if name not in timing:
            timing[name] = round(time.perf_counter() - start, 4)

    try:
        with client.stream("POST", BASE + "/v1/messages", content=payload, headers=headers) as response:
            mark("headers")
            record["http_status"] = response.status_code
            record["headers"] = _keep_headers(response.headers)
            if response.status_code != 200:
                record["error_body"] = _safe_json(response.read())
                mark("end")
                record["status"] = "http_error"
                return _finish(record, timing, usage, text_parts, blocks, stop_reason, events, event_types)
            event_name, data_lines = None, []
            for line in response.iter_lines():
                mark("first_line")
                if time.perf_counter() - start > deadline_s:
                    record["status"] = "deadline_exceeded"
                    break
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                    continue
                if line.strip() or not data_lines:
                    continue
                data = _safe_json("\n".join(data_lines))
                data_lines = []
                kind = data.get("type") or event_name
                event_name = None
                events += 1
                event_types[kind] = event_types.get(kind, 0) + 1
                mark("first_event")
                if kind == "message_start":
                    mark("message_start")
                    message = data.get("message") or {}
                    usage.update(message.get("usage") or {})
                    record["response_model"] = message.get("model")
                    record["message_id"] = message.get("id")
                elif kind == "content_block_start":
                    block = data.get("content_block") or {}
                    index = data.get("index")
                    blocks[index] = {"type": block.get("type"), "chars": 0, "signature": False}
                    if block.get("type") == "thinking":
                        mark("thinking_block_start")
                    elif block.get("type") == "redacted_thinking":
                        mark("thinking_block_start")
                    if block.get("text"):
                        text_parts.append(block["text"])
                        mark("first_text")
                elif kind == "content_block_delta":
                    delta = data.get("delta") or {}
                    block = blocks.setdefault(data.get("index"), {"type": None, "chars": 0, "signature": False})
                    dtype = delta.get("type")
                    if dtype == "text_delta":
                        chunk = delta.get("text") or ""
                        if chunk:
                            mark("first_text")
                            text_parts.append(chunk)
                            block["chars"] += len(chunk)
                    elif dtype == "thinking_delta":
                        chunk = delta.get("thinking") or ""
                        if chunk:
                            mark("first_thinking_text")
                            block["chars"] += len(chunk)
                    elif dtype == "signature_delta":
                        block["signature"] = True
                        mark("first_signature")
                elif kind == "message_delta":
                    stop_reason = (data.get("delta") or {}).get("stop_reason") or stop_reason
                    for key, value in (data.get("usage") or {}).items():
                        if value is not None:
                            usage[key] = value
                elif kind == "message_stop":
                    mark("message_stop")
                elif kind == "error":
                    record["stream_error"] = data.get("error") or data
                    record["status"] = "stream_error"
            mark("end")
    except httpx.TimeoutException as exc:
        mark("end")
        record["status"] = "timeout"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)[:500]}
    except httpx.HTTPError as exc:
        mark("end")
        record["status"] = "transport_error"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)[:500]}
    return _finish(record, timing, usage, text_parts, blocks, stop_reason, events, event_types)


def _finish(record, timing, usage, text_parts, blocks, stop_reason, events, event_types):
    record["timing"] = timing
    record["usage"] = usage or None
    record["stop_reason"] = stop_reason
    record["text"] = "".join(text_parts)
    record["blocks"] = [dict(index=k, **v) for k, v in sorted(blocks.items(), key=lambda kv: (kv[0] is None, kv[0]))]
    record["events"] = events
    record["event_types"] = event_types
    if record["status"] is None:
        if "message_stop" not in timing:
            record["status"] = "stream_incomplete"
        elif stop_reason == "max_tokens":
            record["status"] = "max_tokens"
        elif not record["text"].strip():
            record["status"] = "empty_answer"
        else:
            record["status"] = "completed"
    return record
