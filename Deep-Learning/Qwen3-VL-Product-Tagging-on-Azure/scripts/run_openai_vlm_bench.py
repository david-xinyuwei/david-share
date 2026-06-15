#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_payload(args):
    content = [
        {"type": "image_url", "image_url": {"url": args.image_url}},
        {"type": "text", "text": args.prompt},
    ]
    return {
        "model": args.model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }


def call_once(endpoint, payload, timeout):
    started = time.perf_counter()
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    result = {
        "ok": False,
        "latency_ms": None,
        "status": None,
        "error": None,
        "usage": None,
        "content": None,
    }
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            data = json.loads(raw)
            message = data.get("choices", [{}])[0].get("message", {})
            result.update(
                ok=True,
                latency_ms=elapsed_ms,
                status=response.status,
                usage=data.get("usage"),
                content=message.get("content"),
            )
    except urllib.error.HTTPError as exc:
        result.update(
            latency_ms=(time.perf_counter() - started) * 1000.0,
            status=exc.code,
            error=exc.read().decode("utf-8", errors="replace")[:2000],
        )
    except Exception as exc:
        result.update(
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error=repr(exc),
        )
    return result


def summarize(results, total_wall_s):
    ok_results = [item for item in results if item["ok"]]
    latencies = [item["latency_ms"] for item in ok_results]
    completion_tokens = [
        item.get("usage", {}).get("completion_tokens")
        for item in ok_results
        if item.get("usage") and item["usage"].get("completion_tokens") is not None
    ]
    prompt_tokens = [
        item.get("usage", {}).get("prompt_tokens")
        for item in ok_results
        if item.get("usage") and item["usage"].get("prompt_tokens") is not None
    ]
    total_completion_tokens = sum(completion_tokens)
    total_prompt_tokens = sum(prompt_tokens)
    return {
        "requests": len(results),
        "success": len(ok_results),
        "errors": len(results) - len(ok_results),
        "wall_time_s": total_wall_s,
        "request_throughput_rps": len(ok_results) / total_wall_s if total_wall_s else None,
        "completion_tokens_per_s": total_completion_tokens / total_wall_s if total_wall_s else None,
        "prompt_tokens_per_s": total_prompt_tokens / total_wall_s if total_wall_s else None,
        "latency_ms_avg": statistics.mean(latencies) if latencies else None,
        "latency_ms_p50": percentile(latencies, 50),
        "latency_ms_p90": percentile(latencies, 90),
        "latency_ms_p95": percentile(latencies, 95),
        "completion_tokens_avg": statistics.mean(completion_tokens) if completion_tokens else None,
        "prompt_tokens_avg": statistics.mean(prompt_tokens) if prompt_tokens else None,
    }


def run_concurrency(args, concurrency):
    payload = build_payload(args)
    for _ in range(args.warmup):
        call_once(args.endpoint, payload, args.timeout)

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(call_once, args.endpoint, payload, args.timeout)
            for _ in range(args.requests)
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    wall_time_s = time.perf_counter() - started
    return {
        "concurrency": concurrency,
        "summary": summarize(results, wall_time_s),
        "results": results,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark an OpenAI-compatible VLM endpoint.")
    parser.add_argument("--endpoint", default="http://localhost:8000")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--image-url", default="https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg")
    parser.add_argument("--image-url-file", default=None, help="Read image URL from file (useful for base64 data URIs that exceed ARG_MAX)")
    parser.add_argument("--prompt", default="Describe the image in one short sentence.")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--label", default="vllm-bf16")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.image_url_file:
        args.image_url = Path(args.image_url_file).read_text(encoding="utf-8").strip()
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    benchmark = {
        "label": args.label,
        "started_at": started_at,
        "endpoint": args.endpoint,
        "model": args.model,
        "image_url": args.image_url,
        "prompt": args.prompt,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "warmup": args.warmup,
        "requests_per_concurrency": args.requests,
        "runs": [],
    }

    for concurrency in args.concurrency:
        run = run_concurrency(args, concurrency)
        benchmark["runs"].append(run)
        summary = run["summary"]
        print(
            json.dumps(
                {
                    "concurrency": concurrency,
                    "success": summary["success"],
                    "errors": summary["errors"],
                    "latency_ms_p50": summary["latency_ms_p50"],
                    "request_throughput_rps": summary["request_throughput_rps"],
                    "completion_tokens_per_s": summary["completion_tokens_per_s"],
                },
                ensure_ascii=True,
            ),
            flush=True,
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(benchmark, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"wrote {output}", flush=True)


if __name__ == "__main__":
    main()