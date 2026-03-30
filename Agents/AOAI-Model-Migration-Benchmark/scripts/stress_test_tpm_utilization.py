#!/usr/bin/env python3
"""
PTU/PAYGO TPM Utilization Stress Test
======================================
Concurrent streaming requests to observe x-ratelimit-remaining-tokens header in real time.

Purpose:
  - Capture TPM utilization via response headers (x-ratelimit-remaining-tokens / x-ratelimit-limit-tokens)
  - Observe how utilization climbs under concurrent load
  - Detect 429 throttling and retry-after-ms headers
  - Validate APIM proactive routing feasibility (switch at >95% utilization)

Usage:
  python3 stress_test_tpm_utilization.py \
    --endpoint https://YOUR_ENDPOINT.openai.azure.com \
    --api-key YOUR_API_KEY \
    --deployment gpt-5.4-nano \
    --concurrency 50 --total 300

Author: Xinyu Wei (魏新宇)
"""
import argparse
import httpx
import time
import json
import threading
import sys
from collections import deque


def parse_args():
    p = argparse.ArgumentParser(description="PTU/PAYGO TPM Utilization Stress Test")
    p.add_argument("--endpoint", required=True, help="Azure OpenAI endpoint URL")
    p.add_argument("--api-key", required=True, help="Azure OpenAI API key")
    p.add_argument("--deployment", default="gpt-5.4-nano", help="Deployment name")
    p.add_argument("--api-version", default="2025-04-01-preview", help="API version")
    p.add_argument("--concurrency", type=int, default=50, help="Number of concurrent threads")
    p.add_argument("--total", type=int, default=300, help="Total number of requests")
    p.add_argument("--max-tokens", type=int, default=800, help="max_completion_tokens per request")
    p.add_argument("--output", default=None, help="Output JSON file path for results")
    return p.parse_args()


def main():
    args = parse_args()
    url = f"{args.endpoint}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    hdrs = {"api-key": args.api_key, "Content-Type": "application/json"}

    results = deque()
    all_results = []
    lock = threading.Lock()
    counter = {"ok": 0, "http429": 0, "errors": 0}
    start_time = time.time()

    def send_request(req_id):
        data = {
            "messages": [
                {"role": "system", "content": "You are a helpful AI assistant. Provide detailed answers."},
                {"role": "user", "content": (
                    "Write a detailed 500-word analysis comparing three leading enterprise laptops. "
                    "Cover build quality, display technology, keyboard, battery life, connectivity, "
                    "pricing strategy, enterprise management features, and sustainability initiatives."
                )}
            ],
            "max_completion_tokens": args.max_tokens,
            "stream": True,
        }
        t0 = time.time()
        status = None
        rem_tok = "N/A"
        lim_tok = "N/A"
        rem_req = "N/A"
        lim_req = "N/A"
        ttft = None
        out_chunks = 0
        retry_after = None

        try:
            with httpx.stream("POST", url, headers=hdrs, json=data, timeout=120) as resp:
                status = resp.status_code
                rem_tok = resp.headers.get("x-ratelimit-remaining-tokens", "N/A")
                lim_tok = resp.headers.get("x-ratelimit-limit-tokens", "N/A")
                rem_req = resp.headers.get("x-ratelimit-remaining-requests", "N/A")
                lim_req = resp.headers.get("x-ratelimit-limit-requests", "N/A")
                retry_after = resp.headers.get("retry-after-ms", None)

                for line in resp.iter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        if ttft is None:
                            ttft = time.time() - t0
                        try:
                            c = json.loads(line[6:])
                            d = c.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if d:
                                out_chunks += 1
                        except Exception:
                            pass
        except Exception as e:
            status = f"ERR:{str(e)[:40]}"

        e2e = time.time() - t0
        elapsed = time.time() - start_time
        if ttft is None:
            ttft = e2e

        try:
            pct = (int(lim_tok) - int(rem_tok)) / int(lim_tok) * 100
        except (ValueError, ZeroDivisionError):
            pct = -1

        record = {
            "id": req_id, "elapsed_s": round(elapsed, 2),
            "status": status,
            "ttft_s": round(ttft, 3), "e2e_s": round(e2e, 3),
            "remaining_tokens": rem_tok, "limit_tokens": lim_tok,
            "remaining_requests": rem_req, "limit_requests": lim_req,
            "utilization_pct": round(pct, 2),
            "retry_after_ms": retry_after,
            "output_chunks": out_chunks,
        }

        with lock:
            if status == 200:
                counter["ok"] += 1
            elif status == 429:
                counter["http429"] += 1
            else:
                counter["errors"] += 1
            results.append(record)
            all_results.append(record)

    # Print header
    print(f"=== TPM Utilization Stress Test ===")
    print(f"Endpoint:    {args.endpoint}")
    print(f"Deployment:  {args.deployment}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Total:       {args.total}")
    print(f"MaxTokens:   {args.max_tokens}")
    print()
    print(f"{'T(s)':>6} {'#':>4} {'HTTP':>5} {'TTFT':>6} {'E2E':>6} {'RemTok':>10} {'LimTok':>10} {'TPM%':>6} {'429s':>5} {'RetryMs':>8}")
    print("=" * 80)

    # Launch concurrent threads
    threads = []
    for i in range(args.total):
        t = threading.Thread(target=send_request, args=(i,))
        threads.append(t)
        t.start()
        if len([t for t in threads if t.is_alive()]) >= args.concurrency:
            while len([t for t in threads if t.is_alive()]) >= args.concurrency:
                time.sleep(0.1)
                while results:
                    r = results.popleft()
                    retry = r["retry_after_ms"] or "-"
                    mark = ""
                    if r["status"] == 429:
                        mark = " <<< 429!"
                    elif r["utilization_pct"] > 90:
                        mark = " !!!>90%!!!"
                    elif r["utilization_pct"] > 70:
                        mark = " **>70%**"
                    elif r["utilization_pct"] > 50:
                        mark = " >50%"
                    print(f"{r['elapsed_s']:>5.1f}s #{r['id']:>3} {str(r['status']):>5} "
                          f"{r['ttft_s']:>5.2f}s {r['e2e_s']:>5.2f}s "
                          f"{str(r['remaining_tokens']):>10} {str(r['limit_tokens']):>10} "
                          f"{r['utilization_pct']:>5.1f}% {counter['http429']:>5} "
                          f"{retry:>8}{mark}")
                    sys.stdout.flush()

    for t in threads:
        t.join()

    # Print remaining
    while results:
        r = results.popleft()
        retry = r["retry_after_ms"] or "-"
        mark = ""
        if r["status"] == 429:
            mark = " <<< 429!"
        elif r["utilization_pct"] > 90:
            mark = " !!!>90%!!!"
        print(f"{r['elapsed_s']:>5.1f}s #{r['id']:>3} {str(r['status']):>5} "
              f"{r['ttft_s']:>5.2f}s {r['e2e_s']:>5.2f}s "
              f"{str(r['remaining_tokens']):>10} {str(r['limit_tokens']):>10} "
              f"{r['utilization_pct']:>5.1f}% {counter['http429']:>5} "
              f"{retry:>8}{mark}")

    total_time = time.time() - start_time
    total_reqs = counter["ok"] + counter["http429"] + counter["errors"]
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total time:    {total_time:.1f}s")
    print(f"  Success (200): {counter['ok']}")
    print(f"  HTTP 429:      {counter['http429']}")
    print(f"  Other errors:  {counter['errors']}")
    print(f"  Throughput:    {total_reqs/total_time:.1f} req/s")
    if total_reqs > 0:
        print(f"  429 Rate:      {counter['http429']/total_reqs*100:.1f}%")

    # Save results
    if args.output:
        out = {
            "test_config": {
                "endpoint": args.endpoint,
                "deployment": args.deployment,
                "concurrency": args.concurrency,
                "total_requests": args.total,
                "max_completion_tokens": args.max_tokens,
                "api_version": args.api_version,
            },
            "summary": {
                "total_time_s": round(total_time, 2),
                "success_200": counter["ok"],
                "http_429": counter["http429"],
                "other_errors": counter["errors"],
                "throughput_rps": round(total_reqs / total_time, 2),
                "throttle_rate_pct": round(counter["http429"] / total_reqs * 100, 2) if total_reqs else 0,
            },
            "results": sorted(all_results, key=lambda x: x["elapsed_s"]),
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\n  Results saved to: {args.output}")


if __name__ == "__main__":
    main()
