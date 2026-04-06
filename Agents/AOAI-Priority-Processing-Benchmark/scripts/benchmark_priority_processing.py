#!/usr/bin/env python3
"""
Priority Processing Benchmark: Standard vs Priority (gpt-5.4)
==============================================================
Tests token generation speed (TPS) and E2E latency across multiple
output lengths to find the crossover point where Priority Processing
provides meaningful benefit.

Usage:
  python3 benchmark_priority_processing.py \
    --endpoint https://YOUR_ENDPOINT.openai.azure.com \
    --api-key YOUR_API_KEY \
    --deployment gpt-54

Author: Xinyu Wei
"""
import argparse
import httpx
import time
import json
import sys
import statistics
import threading
from collections import deque


def parse_args():
    p = argparse.ArgumentParser(description="Priority Processing Benchmark: Standard vs Priority")
    p.add_argument("--endpoint", required=True, help="Azure OpenAI endpoint URL")
    p.add_argument("--api-key", required=True, help="Azure OpenAI API key")
    p.add_argument("--deployment", default="gpt-54", help="Deployment name")
    p.add_argument("--api-version", default="2025-04-01-preview")
    p.add_argument("--iterations", type=int, default=8, help="Effective iterations per scenario per tier")
    p.add_argument("--warmup", type=int, default=2, help="Warmup iterations (discarded)")
    p.add_argument("--output", default=None, help="Output JSON file path")
    return p.parse_args()


SCENARIOS = [
    ("20tok",  "What is 2+2? Answer in one word.", 20),
    ("50tok",  "Explain cloud computing in 2 sentences.", 50),
    ("100tok", "Explain how Kubernetes works in 5 sentences.", 100),
    ("200tok", "Write a detailed comparison of AWS vs Azure vs GCP in one paragraph.", 200),
    ("500tok", "Write a comprehensive 400-word analysis of the current state of AI.", 500),
    ("1000tok","Write a thorough 800-word essay about the history and future of AI.", 1000),
]

SYS_MSG = "You are a helpful AI assistant. Answer in detail as requested."


def run_request(endpoint, api_key, deployment, api_version, tier, query, max_tok):
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    data = {
        "messages": [{"role": "system", "content": SYS_MSG}, {"role": "user", "content": query}],
        "max_completion_tokens": max_tok,
        "reasoning_effort": "none",
        "stream": True,
        "stream_options": {"include_usage": True},
        "service_tier": tier,
    }
    t0 = time.time()
    ttft = None
    out_tok = 0
    rsn_tok = 0
    resp_tier = "?"

    with httpx.stream("POST", url, headers=headers, json=data, timeout=120) as resp:
        for line in resp.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                if ttft is None:
                    ttft = (time.time() - t0) * 1000
                try:
                    d = json.loads(line[6:])
                    st = d.get("service_tier")
                    if st:
                        resp_tier = st
                    u = d.get("usage")
                    if u:
                        out_tok = u.get("completion_tokens", 0)
                        rsn_tok = u.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                except Exception:
                    pass

    e2e = (time.time() - t0) * 1000
    real = out_tok - rsn_tok
    gen = e2e - (ttft or e2e)
    tps = real / (gen / 1000) if gen > 0 else 0
    return {
        "tier_req": tier, "tier_resp": resp_tier,
        "ttft": round(ttft, 1) if ttft else None,
        "e2e": round(e2e, 1),
        "tokens": real,
        "gen_ms": round(gen, 1),
        "tps": round(tps, 1),
    }


def main():
    args = parse_args()
    print(f"=== Priority Processing Benchmark ===")
    print(f"Endpoint:   {args.endpoint}")
    print(f"Deployment: {args.deployment}")
    print(f"Iterations: {args.iterations} effective + {args.warmup} warmup")
    print(f"Scenarios:  {len(SCENARIOS)}")
    print()
    print(f"{'Scenario':>10} {'Tier':>10} {'TTFT':>8} {'E2E':>8} {'Tokens':>8} {'TPS':>8}")
    print("=" * 60)

    all_results = []

    for sc_name, sc_query, sc_max in SCENARIOS:
        # Warmup
        for tier in ["default", "priority"]:
            for _ in range(args.warmup):
                try:
                    run_request(args.endpoint, args.api_key, args.deployment,
                                args.api_version, tier, sc_query, sc_max)
                except Exception:
                    pass

        # Interleaved effective runs
        for i in range(args.iterations):
            for tier in ["default", "priority"]:
                try:
                    r = run_request(args.endpoint, args.api_key, args.deployment,
                                    args.api_version, tier, sc_query, sc_max)
                    r["scenario"] = sc_name
                    r["max_tok"] = sc_max
                    all_results.append(r)
                    print(f"{sc_name:>10} {tier:>10} {r['ttft']:>8} {r['e2e']:>8} "
                          f"{r['tokens']:>8} {r['tps']:>8}")
                    sys.stdout.flush()
                except Exception as e:
                    print(f"{sc_name:>10} {tier:>10} ERROR: {str(e)[:40]}")

    # Summary
    print(f"\n{'='*80}")
    print(f"{'Scenario':>10} {'MaxTok':>8} | {'Std TPS':>9} {'Std E2E':>9} | "
          f"{'Pri TPS':>9} {'Pri E2E':>9} | {'ΔTPS%':>7} {'ΔE2E%':>7}")
    print("-" * 80)

    for sc_name, _, sc_max in SCENARIOS:
        std = [r for r in all_results if r.get("scenario") == sc_name
               and r["tier_req"] == "default" and r.get("ttft")]
        pri = [r for r in all_results if r.get("scenario") == sc_name
               and r["tier_req"] == "priority" and r.get("ttft")]
        if not std or not pri:
            continue
        s_tps = statistics.median([r["tps"] for r in std])
        p_tps = statistics.median([r["tps"] for r in pri])
        s_e2e = statistics.median([r["e2e"] for r in std])
        p_e2e = statistics.median([r["e2e"] for r in pri])
        d_tps = (p_tps - s_tps) / s_tps * 100 if s_tps else 0
        d_e2e = (p_e2e - s_e2e) / s_e2e * 100 if s_e2e else 0
        print(f"{sc_name:>10} {sc_max:>8} | {s_tps:>8.1f}  {s_e2e/1000:>8.1f}s | "
              f"{p_tps:>8.1f}  {p_e2e/1000:>8.1f}s | {d_tps:>+6.1f}% {d_e2e:>+6.1f}%")

    # Save
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
