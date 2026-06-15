#!/usr/bin/env python3
"""Concurrent serving benchmark: P50/P95/throughput across concurrency levels."""
import argparse
import asyncio
import base64
import json
import statistics
import time
from pathlib import Path

import httpx


def img_b64(p):
    with open(p, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


async def one_request(client, url, model, sys_msg, usr_text, img_url, max_tokens):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": usr_text},
            ]},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    r = await client.post(url, json=payload, timeout=120)
    t1 = time.time()
    if r.status_code != 200:
        return None, (t1 - t0) * 1000, 0
    j = r.json()
    out_tok = j.get("usage", {}).get("completion_tokens", 0)
    return j["choices"][0]["message"]["content"], (t1 - t0) * 1000, out_tok


async def run_concurrency(samples, base_url, model, concurrency, total):
    url = base_url.rstrip("/") + "/chat/completions"
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def task(rec):
        async with sem:
            sys_msg = next((m["content"] for m in rec["messages"] if m["role"] == "system"), "")
            usr_text = next((m["content"] for m in rec["messages"] if m["role"] == "user"), "").replace("<image>", "").strip()
            img_url = img_b64(rec["images"][0])
            return await one_request(client, url, model, sys_msg, usr_text, img_url, 256)

    async with httpx.AsyncClient(http2=False, timeout=120) as client:
        t_start = time.time()
        coros = [task(samples[i % len(samples)]) for i in range(total)]
        results = await asyncio.gather(*coros, return_exceptions=True)
        t_end = time.time()

    latencies = [r[1] for r in results if isinstance(r, tuple) and r[0] is not None]
    out_toks = [r[2] for r in results if isinstance(r, tuple) and r[0] is not None]
    n_ok = len(latencies)
    n_err = total - n_ok
    elapsed = t_end - t_start
    return {
        "concurrency": concurrency,
        "total_requests": total,
        "ok": n_ok,
        "errors": n_err,
        "elapsed_s": round(elapsed, 2),
        "throughput_req_per_s": round(n_ok / elapsed, 3) if elapsed else 0,
        "p50_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "p95_ms": round(sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)], 1) if latencies else 0,
        "mean_ms": round(statistics.mean(latencies), 1) if latencies else 0,
        "mean_out_tokens": round(statistics.mean(out_toks), 1) if out_toks else 0,
    }


async def main_async(args):
    val = json.loads(Path(args.val_json).read_text())
    print(f"Loaded {len(val)} samples")
    rows = []
    for c in [int(x) for x in args.concurrencies.split(",")]:
        total = max(c * args.repeats, c)
        print(f"\n>>> concurrency={c} total={total}")
        row = await run_concurrency(val, args.base_url, args.model, c, total)
        print(json.dumps(row, ensure_ascii=False, indent=2))
        rows.append(row)
    Path(args.output).write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"\n✅ Saved → {args.output}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-json", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--concurrencies", default="1,2,4,8,16")
    ap.add_argument("--repeats", type=int, default=2, help="requests per concurrent slot")
    ap.add_argument("--output", required=True)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
