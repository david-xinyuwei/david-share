#!/usr/bin/env python3
"""
gpt-5.6 Luna / Sol / Terra Direct Latency Benchmark - Knowledge-only Prompts (no tools)
=====================================================================================
Scenario S1-KQ: Direct AOAI Responses API, no agent, no web search, no tools.

The prompts are chosen so that a model can answer from parametric knowledge alone
(for example "What are the seven wonders of the world?"). Nothing in the request
triggers retrieval or tool orchestration, so the measurement isolates:

    queueing + prefill + first token  -> TTFT (streaming) / TTFB (non-streaming)
    decode throughput                  -> visible output tokens per second
    end-to-end wall clock              -> E2E

Per request the script records HTTP status, request id (x-request-id /
apim-request-id), SDK retries taken, input/output/reasoning token usage, the
Responses API status (completed / incomplete), and a light answer sanity flag.

Defaults deliberately mirror what a customer gets out of the box, except that
SDK automatic retries are disabled (--max-retries 0) so a single "successful"
timing can never hide a hidden 429/5xx + back-off + retry. Re-run with
--max-retries 2 (the SDK default) to measure that effect as a single variable.

Authentication: --api-key / AZURE_OPENAI_API_KEY, or Microsoft Entra ID via
Azure CLI login when no key is given (honours AZURE_CONFIG_DIR).

Author: Xinyu Wei
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import statistics
import sys
import time
from typing import Any, Callable

import openai
from openai import OpenAI

SCRIPT_PATH = os.path.abspath(__file__)

# ── Knowledge-only query set ────────────────────────────────────────────
# (id, prompt, default max_output_tokens, sanity checker)
# Sanity checkers are deliberately permissive: they flag an obviously broken or
# truncated answer, they do not grade quality.

SEVEN_WONDERS_TERMS = [
    "great wall", "petra", "colosseum", "chichen itza", "machu picchu",
    "taj mahal", "christ the redeemer", "giza", "pyramid", "babylon",
    "hanging gardens", "zeus", "artemis", "mausoleum", "halicarnassus",
    "colossus", "rhodes", "lighthouse", "pharos",
]


def check_seven_wonders(text: str) -> bool:
    lowered = text.lower()
    return sum(term in lowered for term in SEVEN_WONDERS_TERMS) >= 5


def check_tcp_udp(text: str) -> bool:
    lowered = text.lower()
    return "tcp" in lowered and "udp" in lowered and "connection" in lowered


def check_palindrome(text: str) -> bool:
    return "def is_palindrome" in text


def check_speed(text: str) -> bool:
    # 150 km in 1 h 40 min = 90 km/h = 55.9 mph
    return "90" in text and ("55.9" in text or "56" in text)


def check_json_capitals(text: str) -> bool:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return False
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False
    return "paris" in json.dumps(data).lower()


QUERY_SET: dict[str, tuple[str, int, Callable[[str], bool]]] = {
    "seven_wonders": (
        "What are the seven wonders of the world?",
        1024,
        check_seven_wonders,
    ),
    "tcp_udp": (
        "Explain the difference between TCP and UDP in five bullet points.",
        600,
        check_tcp_udp,
    ),
    "palindrome_py": (
        "Write a Python function is_palindrome(s) that ignores case and "
        "non-alphanumeric characters, then show two example calls.",
        600,
        check_palindrome,
    ),
    "speed_math": (
        "A car travels 150 kilometers in 1 hour 40 minutes. What is its average "
        "speed in km/h and in mph? Show the calculation.",
        600,
        check_speed,
    ),
    "json_capitals": (
        "Return a JSON object whose keys are France, Japan and Brazil and whose "
        "values are objects with 'capital' and 'population_millions'. Output JSON only.",
        400,
        check_json_capitals,
    ),
}


# ── CLI ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Direct AOAI knowledge-only latency benchmark for gpt-5.6 Luna/Sol/Terra and peers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                        help="Resource endpoint, e.g. https://<res>.openai.azure.com or "
                             "https://<res>.services.ai.azure.com (the /openai/v1 path is appended)")
    parser.add_argument("--api-key", dest="api_key", default=os.environ.get("AZURE_OPENAI_API_KEY", ""),
                        help="API key. When empty, Microsoft Entra ID via Azure CLI login is used")
    parser.add_argument("--token-scope", dest="token_scope",
                        default="https://cognitiveservices.azure.com/.default",
                        help="Entra ID token scope used when no API key is given")
    parser.add_argument("--models", default="gpt-5.6-luna,gpt-5.6-sol,gpt-5.6-terra,gpt-5.4-nano",
                        help="Comma-separated deployment names. Append :<effort> to set reasoning "
                             "effort per model, e.g. gpt-5.4:none (default: model default)")
    parser.add_argument("--queries", default="seven_wonders",
                        help="Comma-separated query ids from the built-in set, or 'all'. "
                             f"Available: {', '.join(QUERY_SET)}")
    parser.add_argument("--custom-query", dest="custom_query", default="",
                        help="Additional ad-hoc prompt, recorded with id 'custom'")
    parser.add_argument("--system", default="",
                        help="Optional system instructions (default: none, like a bare client loop)")
    parser.add_argument("--mode", choices=("stream", "nonstream", "both"), default="stream",
                        help="stream=True (TTFT + E2E), stream=False (TTFB == E2E), or both per iteration")
    parser.add_argument("--iterations", type=int, default=10,
                        help="Iterations per model per query per mode, including warmup")
    parser.add_argument("--warmup", type=int, default=2, help="Leading iterations excluded from statistics")
    parser.add_argument("--order", choices=("roundrobin", "sequential"), default="roundrobin",
                        help="roundrobin interleaves models within each iteration; sequential runs "
                             "one model to completion at a time (like a simple customer loop)")
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=0,
                        help="Override the per-query max_output_tokens (0 = per-query default)")
    parser.add_argument("--max-retries", dest="max_retries", type=int, default=0,
                        help="openai SDK automatic retries (SDK default is 2)")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-request timeout in seconds")
    parser.add_argument("--new-client-per-request", dest="new_client", action="store_true",
                        help="Create a fresh client (new TLS connection) for every request")
    parser.add_argument("--no-store", dest="no_store", action="store_true",
                        help="Send store=false in the request body")
    parser.add_argument("--sleep", type=float, default=0.3, help="Pause between calls in seconds")
    parser.add_argument("--output-dir", dest="output_dir", default="outputs")
    parser.add_argument("--tag", default="", help="Free-text tag stored in the output file name and meta")
    parser.add_argument("--verbose", action="store_true", help="Print a preview of every answer")
    parser.add_argument("--report-from", dest="report_from", default="",
                        help="Only recompute and print the summary from an existing output JSON")
    args = parser.parse_args()
    if args.report_from:
        return args
    if not args.endpoint:
        parser.error("--endpoint or AZURE_OPENAI_ENDPOINT is required")
    if args.iterations < 1 or args.warmup < 0 or args.warmup >= args.iterations:
        parser.error("iterations must be >= 1 and warmup must be < iterations")
    return args


def parse_models(spec: str) -> list[tuple[str, str | None]]:
    models: list[tuple[str, str | None]] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        deploy, _, effort = item.partition(":")
        models.append((deploy, effort or None))
    if not models:
        raise SystemExit("--models resolved to an empty list")
    return models


def select_queries(args: argparse.Namespace) -> list[tuple[str, str, int, Callable[[str], bool] | None]]:
    ids = list(QUERY_SET) if args.queries.strip() == "all" else [q.strip() for q in args.queries.split(",") if q.strip()]
    selected: list[tuple[str, str, int, Callable[[str], bool] | None]] = []
    for qid in ids:
        if qid not in QUERY_SET:
            raise SystemExit(f"Unknown query id '{qid}'. Available: {', '.join(QUERY_SET)}")
        prompt, max_tokens, checker = QUERY_SET[qid]
        selected.append((qid, prompt, args.max_output_tokens or max_tokens, checker))
    if args.custom_query:
        selected.append(("custom", args.custom_query, args.max_output_tokens or 1024, None))
    if not selected:
        raise SystemExit("No queries selected")
    return selected


# ── Client ──────────────────────────────────────────────────────────────

def build_base_url(endpoint: str) -> str:
    endpoint = endpoint.strip().rstrip("/")
    if endpoint.endswith("/openai/v1"):
        return endpoint
    if endpoint.endswith("/openai"):
        return endpoint + "/v1"
    return endpoint + "/openai/v1"


def make_credential(args: argparse.Namespace) -> str | Callable[[], str]:
    if args.api_key:
        return args.api_key
    from azure.identity import AzureCliCredential, get_bearer_token_provider
    # `az` can take well over the 10 s default on a busy workstation; the provider caches
    # the token, so priming it here keeps the first measured request free of CLI latency.
    provider = get_bearer_token_provider(AzureCliCredential(process_timeout=90), args.token_scope)
    t0 = time.perf_counter()
    provider()
    print(f"Entra ID token acquired via Azure CLI in {time.perf_counter() - t0:.1f}s (scope {args.token_scope})")
    return provider


def make_client(args: argparse.Namespace, credential: str | Callable[[], str]) -> OpenAI:
    api_key: Any = credential
    if callable(credential):
        # openai>=1.100 accepts a callable api_key; fall back to a one-shot token otherwise.
        try:
            return OpenAI(base_url=build_base_url(args.endpoint), api_key=credential,
                          max_retries=args.max_retries, timeout=args.timeout)
        except TypeError:
            api_key = credential()
    return OpenAI(base_url=build_base_url(args.endpoint), api_key=api_key,
                  max_retries=args.max_retries, timeout=args.timeout)


# ── Single request ──────────────────────────────────────────────────────

def request_kwargs(args: argparse.Namespace, deploy: str, effort: str | None,
                   prompt: str, max_tokens: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model": deploy, "input": prompt, "max_output_tokens": max_tokens}
    if args.system:
        kwargs["instructions"] = args.system
    if effort:
        kwargs["reasoning"] = {"effort": effort}
    if args.no_store:
        kwargs["store"] = False
    return kwargs


def header_request_id(headers: Any) -> str | None:
    if headers is None:
        return None
    return headers.get("x-request-id") or headers.get("apim-request-id")


def usage_fields(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {"input_tokens": None, "output_tokens": None, "reasoning_tokens": None, "cached_tokens": None}
    details = getattr(usage, "output_tokens_details", None)
    input_details = getattr(usage, "input_tokens_details", None)
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details else None,
        "cached_tokens": getattr(input_details, "cached_tokens", None) if input_details else None,
    }


def run_once(client: OpenAI, stream: bool, kwargs: dict[str, Any]) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "stream": stream, "success": False, "http_status": None, "request_id": None,
        "response_id": None, "response_status": None, "incomplete_reason": None,
        "retries_taken": None, "retry_after": None, "ttfb": None, "ttft": None, "e2e": None, "text_len": 0,
        **usage_fields(None),
    }
    text_parts: list[str] = []
    t0 = time.perf_counter()
    try:
        if stream:
            raw = client.responses.with_raw_response.create(stream=True, **kwargs)
            rec["ttfb"] = round(time.perf_counter() - t0, 3)
            rec["http_status"] = raw.status_code
            rec["request_id"] = header_request_id(raw.headers)
            rec["retries_taken"] = getattr(raw, "retries_taken", None)
            final = None
            for event in raw.parse():
                etype = getattr(event, "type", "")
                if etype == "response.output_text.delta":
                    if rec["ttft"] is None:
                        rec["ttft"] = round(time.perf_counter() - t0, 3)
                    text_parts.append(event.delta)
                elif etype in ("response.completed", "response.incomplete", "response.failed"):
                    final = event.response
            rec["e2e"] = round(time.perf_counter() - t0, 3)
            if final is not None:
                rec["response_id"] = final.id
                rec["response_status"] = final.status
                incomplete = getattr(final, "incomplete_details", None)
                rec["incomplete_reason"] = getattr(incomplete, "reason", None) if incomplete else None
                rec.update(usage_fields(final.usage))
            rec["text"] = "".join(text_parts)
            rec["success"] = rec["response_status"] == "completed" and bool(rec["text"])
        else:
            raw = client.responses.with_raw_response.create(**kwargs)
            response = raw.parse()
            rec["e2e"] = round(time.perf_counter() - t0, 3)
            # The SDK reads the whole body before returning, so TTFB is not observable here.
            rec["http_status"] = raw.status_code
            rec["request_id"] = header_request_id(raw.headers)
            rec["retries_taken"] = getattr(raw, "retries_taken", None)
            rec["response_id"] = response.id
            rec["response_status"] = response.status
            incomplete = getattr(response, "incomplete_details", None)
            rec["incomplete_reason"] = getattr(incomplete, "reason", None) if incomplete else None
            rec.update(usage_fields(response.usage))
            rec["text"] = response.output_text or ""
            rec["success"] = response.status == "completed" and bool(rec["text"])
    except openai.APIStatusError as error:
        rec["e2e"] = round(time.perf_counter() - t0, 3)
        rec["http_status"] = error.status_code
        headers = getattr(error.response, "headers", None)
        rec["request_id"] = error.request_id or header_request_id(headers)
        rec["retry_after"] = headers.get("retry-after-ms") or headers.get("retry-after") if headers is not None else None
        # A surfaced 408/409/429/5xx means the SDK already exhausted its automatic retries.
        rec["retries_taken"] = client.max_retries if error.status_code in (408, 409, 429) or error.status_code >= 500 else 0
        rec["error"] = f"{type(error).__name__}: {str(error)[:500]}"
    except (openai.APITimeoutError, openai.APIConnectionError) as error:
        rec["e2e"] = round(time.perf_counter() - t0, 3)
        rec["error"] = f"{type(error).__name__}: {str(error)[:500]}"
    except Exception as error:  # noqa: BLE001 - keep the loop alive, record everything
        rec["e2e"] = round(time.perf_counter() - t0, 3)
        rec["error"] = f"{type(error).__name__}: {str(error)[:500]}"
    rec["text_len"] = len(rec.get("text", ""))
    visible = (rec["output_tokens"] or 0) - (rec["reasoning_tokens"] or 0)
    first = rec["ttft"] if stream else None
    if rec["success"] and first is not None and rec["e2e"] and rec["e2e"] > first and visible > 1:
        rec["visible_tps"] = round(visible / (rec["e2e"] - first), 1)
    else:
        rec["visible_tps"] = None
    return rec


# ── Statistics ──────────────────────────────────────────────────────────

def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def dist(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": round(percentile(values, 0.95), 3),
        "max": round(max(values), 3),
        "min": round(min(values), 3),
        "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
    }


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(r["model"], r.get("reasoning_effort", "default"), r["query"], r["stream"]) for r in records},
                  key=lambda k: (k[2], not k[3], k[0], k[1]))
    summary: list[dict[str, Any]] = []
    for model, effort, query, stream in keys:
        group = [r for r in records if r["model"] == model and r.get("reasoning_effort", "default") == effort
                 and r["query"] == query and r["stream"] == stream and not r["warmup"]]
        if not group:
            continue
        ok = [r for r in group if r["success"]]
        e2e = [r["e2e"] for r in ok]
        ttft = [r["ttft"] for r in ok if r.get("ttft") is not None]
        ttfb = [r["ttfb"] for r in ok if r.get("ttfb") is not None]
        tps = [r["visible_tps"] for r in ok if r.get("visible_tps") is not None]
        out_tokens = [r["output_tokens"] for r in ok if r.get("output_tokens") is not None]
        reasoning = [r["reasoning_tokens"] or 0 for r in ok if r.get("output_tokens") is not None]
        sanity = [r["sanity_pass"] for r in ok if r.get("sanity_pass") is not None]
        request_ids = {r["request_id"] for r in group if r.get("request_id")}
        summary.append({
            "model": model if effort == "default" else f"{model}:{effort}", "deployment": model,
            "reasoning_effort": effort, "query": query, "mode": "stream" if stream else "nonstream",
            "requests": len(group), "successful": len(ok), "failed": len(group) - len(ok),
            "http_statuses": sorted({str(r["http_status"]) for r in group}),
            "unique_request_ids": len(request_ids),
            "retries_taken_total": sum(r["retries_taken"] or 0 for r in group),
            "incomplete": sum(1 for r in group if r.get("response_status") == "incomplete"),
            "ttft": dist(ttft), "ttfb": dist(ttfb), "e2e": dist(e2e),
            "over_5s": sum(v > 5 for v in e2e), "over_10s": sum(v > 10 for v in e2e), "over_20s": sum(v > 20 for v in e2e),
            "output_tokens_mean": round(statistics.mean(out_tokens), 1) if out_tokens else None,
            "reasoning_tokens_mean": round(statistics.mean(reasoning), 1) if reasoning else None,
            "visible_tps_p50": round(statistics.median(tps), 1) if tps else None,
            "sanity_pass_rate": round(sum(sanity) / len(sanity), 3) if sanity else None,
        })
    return summary


def fmt(value: Any, suffix: str = "") -> str:
    return "-" if value is None else f"{value}{suffix}"


def print_summary(summary: list[dict[str, Any]]) -> None:
    header = (f"{'Query':<14}{'Mode':<10}{'Model':<22}{'N':>4}{'OK':>4}"
              f"{'TTFT p50':>10}{'TTFT p95':>10}{'E2E p50':>9}{'E2E p95':>9}{'E2E max':>9}"
              f"{'>5s':>5}{'>20s':>5}{'OutTok':>8}{'Reason':>8}{'tok/s':>7}{'Sane':>6}{'ReqIDs':>7}{'Retry':>6}")
    print("\n" + "=" * len(header))
    print("  Knowledge-only direct latency summary (warmup excluded)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for row in summary:
        print(f"{row['query']:<14}{row['mode']:<10}{row['model']:<22}{row['requests']:>4}{row['successful']:>4}"
              f"{fmt(row['ttft'].get('p50'), 's'):>10}{fmt(row['ttft'].get('p95'), 's'):>10}"
              f"{fmt(row['e2e'].get('p50'), 's'):>9}{fmt(row['e2e'].get('p95'), 's'):>9}{fmt(row['e2e'].get('max'), 's'):>9}"
              f"{row['over_5s']:>5}{row['over_20s']:>5}{fmt(row['output_tokens_mean']):>8}{fmt(row['reasoning_tokens_mean']):>8}"
              f"{fmt(row['visible_tps_p50']):>7}{fmt(row['sanity_pass_rate']):>6}{row['unique_request_ids']:>7}{row['retries_taken_total']:>6}")


def markdown_summary(summary: list[dict[str, Any]]) -> str:
    lines = ["| Query | Mode | Model | N ok/total | TTFT p50 / p95 | E2E mean / p50 / p95 / max | >5s | Out tok (reasoning) | tok/s p50 | Sanity | Unique req IDs |",
             "|---|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|"]
    for row in summary:
        ttft = f"{fmt(row['ttft'].get('p50'), 's')} / {fmt(row['ttft'].get('p95'), 's')}" if row["mode"] == "stream" else "n/a (non-stream)"
        e2e = row["e2e"]
        lines.append(
            f"| {row['query']} | {row['mode']} | `{row['model']}` | {row['successful']}/{row['requests']} | {ttft} | "
            f"{fmt(e2e.get('mean'), 's')} / {fmt(e2e.get('p50'), 's')} / {fmt(e2e.get('p95'), 's')} / {fmt(e2e.get('max'), 's')} | "
            f"{row['over_5s']} | {fmt(row['output_tokens_mean'])} ({fmt(row['reasoning_tokens_mean'])}) | {fmt(row['visible_tps_p50'])} | "
            f"{fmt(row['sanity_pass_rate'])} | {row['unique_request_ids']} |")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if args.report_from:
        with open(args.report_from, encoding="utf-8") as handle:
            payload = json.load(handle)
        summary = summarize(payload["records"])
        print_summary(summary)
        print("\n" + markdown_summary(summary))
        return 0

    models = parse_models(args.models)
    queries = select_queries(args)
    modes = [True, False] if args.mode == "both" else [args.mode == "stream"]
    with open(SCRIPT_PATH, "rb") as handle:
        script_sha = hashlib.sha256(handle.read()).hexdigest()
    credential = make_credential(args)
    shared_client = None if args.new_client else make_client(args, credential)

    total = len(models) * len(queries) * len(modes) * args.iterations
    started = dt.datetime.now(dt.timezone.utc)
    print(f"Knowledge-only direct benchmark: {len(models)} models x {len(queries)} queries x {len(modes)} mode(s) x "
          f"{args.iterations} iterations = {total} calls ({args.warmup} warmup per cell)")
    print(f"Endpoint: {build_base_url(args.endpoint)} | auth: {'api-key' if args.api_key else 'Entra ID (Azure CLI)'} | "
          f"max_retries={args.max_retries} | timeout={args.timeout}s | order={args.order} | "
          f"client={'new per request' if args.new_client else 'shared'} | openai=={openai.__version__}")

    records: list[dict[str, Any]] = []

    def execute(deploy: str, effort: str | None, qid: str, prompt: str, max_tokens: int,
                checker: Callable[[str], bool] | None, stream: bool, iteration: int) -> None:
        client = shared_client or make_client(args, credential)
        kwargs = request_kwargs(args, deploy, effort, prompt, max_tokens)
        rec = run_once(client, stream, kwargs)
        if args.new_client:
            client.close()
        text = rec.pop("text", "")
        rec.update({
            "scenario": "S1_direct_knowledge_only", "model": deploy, "reasoning_effort": effort or "default",
            "query": qid, "iteration": iteration, "warmup": iteration <= args.warmup,
            "max_output_tokens": max_tokens, "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sanity_pass": checker(text) if (checker and rec["success"]) else None,
            "answer_preview": text[:160],
        })
        records.append(rec)
        tag = "WU" if rec["warmup"] else "  "
        mode = "stream" if stream else "nonstr"
        status = "ok " if rec["success"] else "ERR"
        print(f"  {tag} i{iteration:>2} {qid:<13} {mode} {deploy:<16} {status} http={fmt(rec['http_status'])} "
              f"ttft={fmt(rec['ttft'], 's')} e2e={fmt(rec['e2e'], 's')} out={fmt(rec['output_tokens'])} "
              f"reason={fmt(rec['reasoning_tokens'])} tps={fmt(rec['visible_tps'])} sane={fmt(rec['sanity_pass'])} "
              f"rid={fmt(rec['request_id'])}" + (f" err={rec['error'][:120]}" if rec.get("error") else ""), flush=True)
        if args.verbose and text:
            print(f"       > {text[:300]!r}")
        time.sleep(args.sleep)

    for qid, prompt, max_tokens, checker in queries:
        print(f"\n[{qid}] max_output_tokens={max_tokens} prompt={prompt!r}")
        if args.order == "roundrobin":
            for iteration in range(1, args.iterations + 1):
                for deploy, effort in models:
                    for stream in modes:
                        execute(deploy, effort, qid, prompt, max_tokens, checker, stream, iteration)
        else:
            for deploy, effort in models:
                for stream in modes:
                    for iteration in range(1, args.iterations + 1):
                        execute(deploy, effort, qid, prompt, max_tokens, checker, stream, iteration)

    finished = dt.datetime.now(dt.timezone.utc)
    summary = summarize(records)
    print_summary(summary)
    print("\n" + markdown_summary(summary))

    payload = {
        "meta": {
            "scenario": "S1_direct_knowledge_only",
            "started_utc": started.isoformat(), "finished_utc": finished.isoformat(),
            "endpoint_host": build_base_url(args.endpoint).split("/")[2],
            "auth": "api-key" if args.api_key else f"entra-id ({args.token_scope})",
            "models": [{"deployment": d, "reasoning_effort": e or "default"} for d, e in models],
            "queries": [{"id": q, "prompt": p, "max_output_tokens": m} for q, p, m, _ in queries],
            "system_instructions": args.system or None,
            "modes": ["stream" if s else "nonstream" for s in modes],
            "iterations": args.iterations, "warmup": args.warmup, "order": args.order,
            "max_retries": args.max_retries, "timeout_seconds": args.timeout,
            "new_client_per_request": args.new_client, "store": False if args.no_store else "default",
            "sleep_seconds": args.sleep, "tag": args.tag or None,
            "openai_sdk": openai.__version__, "python": sys.version.split()[0], "platform": platform.platform(),
            "script": os.path.basename(SCRIPT_PATH), "script_sha256": script_sha,
        },
        "summary": summary,
        "records": records,
    }
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{re.sub(r'[^A-Za-z0-9._-]+', '-', args.tag)}" if args.tag else ""
    outfile = os.path.join(args.output_dir, f"benchmark_luna_knowledge_qa_{stamp}{suffix}.json")
    with open(outfile, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    failed = sum(1 for r in records if not r["success"])
    print(f"\nSaved {len(records)} records -> {outfile}")
    print(f"BENCHMARK_STATUS={'PASS' if failed == 0 else 'PARTIAL'} failed={failed} script_sha256={script_sha}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
