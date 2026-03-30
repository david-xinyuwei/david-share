#!/usr/bin/env python3
"""
Qira web_search Benchmark — Direct AOAI + Responses API + web_search_preview
=============================================================================
Tests the ACTUAL customer architecture: Responses API with built-in web_search
(NOT Foundry Agent + BingGroundingAgentTool).

2 Scenarios:
  S1: Direct AOAI (no search)    — baseline
  S4: Direct AOAI + web_search   — customer's Bing path

5 Models × 3 Queries × 10 iterations (2 warmup) = 24 samples/model/scenario/run
Author: Xinyu Wei (魏新宇)
"""

import json, time, datetime, os
from openai import AzureOpenAI

# ──────────────────────────────────────────────────────────────────
AOAI_ENDPOINT = "https://<your-endpoint>.openai.azure.com"
AOAI_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "<your-api-key>")
AOAI_API_VER = "2025-04-01-preview"

MODELS = [
    # (display_name, deployment_name, effort_s1, effort_web_search)
    # web_search doesn't work with effort=minimal, need at least "low" for gpt-5
    ("gpt-4o-mini",   "gpt-4o-mini",   None,      None),
    ("gpt-5-mini",    "gpt-5-mini",    "minimal", "low"),
    ("gpt-5-nano",    "gpt-5-nano",    "minimal", "low"),
    ("gpt-5.4-mini",  "gpt-5.4-mini",  "none",    "none"),
    ("gpt-5.4-nano",  "gpt-5.4-nano",  "none",    "none"),
]

SYSTEM_MSG = "You are Qira, a helpful AI assistant. Answer concisely."
BING_INSTRUCTION = (
    "You are Qira, a helpful AI assistant. Answer concisely. "
    "CRITICAL: Perform exactly ONE search. Do NOT refine or repeat searches. "
    "Use first results immediately."
)

QUERIES = [
    ("pricing",  "What is the latest retail price for a ThinkPad X1 Carbon Gen 12?", 300),
    ("news",     "What are the top AI news stories this week?", 300),
    ("weather",  "What is the current weather in Seattle, Washington?", 200),
]

ITERS = 10
WARMUP = 2

# ──────────────────────────────────────────────────────────────────

def run_s1(client, deploy, effort, query, max_tokens):
    """S1: Direct AOAI Responses API + Streaming (no search)"""
    t0 = time.perf_counter()
    ttft = None
    txt = ""
    kwargs = {
        "model": deploy,
        "stream": True,
        "input": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": query},
        ],
        "max_output_tokens": max_tokens,
    }
    if effort:
        kwargs["reasoning"] = {"effort": effort}

    stream = client.responses.create(**kwargs)
    for ev in stream:
        if hasattr(ev, "type") and ev.type == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - t0
            txt += ev.delta
    e2e = time.perf_counter() - t0
    if ttft is None:
        ttft = e2e
    return ttft, e2e, len(txt)


def run_s4_websearch(client, deploy, effort, query, max_tokens):
    """S4: Direct AOAI + web_search_preview (customer's actual Bing path)"""
    t0 = time.perf_counter()
    ttft = None
    txt = ""
    searched = False
    kwargs = {
        "model": deploy,
        "stream": True,
        "tools": [{"type": "web_search_preview", "search_context_size": "low"}],
        # tool_choice defaults to "auto" — model decides when to search
        "input": [
            {"role": "system", "content": BING_INSTRUCTION},
            {"role": "user", "content": query},
        ],
        "max_output_tokens": max_tokens,
    }
    if effort:
        kwargs["reasoning"] = {"effort": effort}

    stream = client.responses.create(**kwargs)
    for ev in stream:
        etype = getattr(ev, "type", "")
        if etype == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - t0
            txt += ev.delta
        if "web_search" in etype:
            searched = True
    e2e = time.perf_counter() - t0
    if ttft is None:
        ttft = e2e
    return ttft, e2e, len(txt), searched


def main():
    import numpy as np

    client = AzureOpenAI(
        api_key=AOAI_KEY,
        azure_endpoint=AOAI_ENDPOINT,
        api_version=AOAI_API_VER,
    )

    results = []
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    effective = (ITERS - WARMUP) * len(QUERIES)
    print(f"Benchmark: web_search_preview — {len(MODELS)} models × {len(QUERIES)} queries × {ITERS} iter")
    print(f"Warmup: {WARMUP} → {effective} effective samples/model/scenario")
    print(f"Endpoint: {AOAI_ENDPOINT}")

    # ─── S1: Direct AOAI ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("  S1: Direct AOAI — Responses API + Streaming (no search)")
    print("=" * 70)

    for qname, qtext, maxtok in QUERIES:
        print(f"\n  [{qname}] max_tokens={maxtok}")
        for i in range(1, ITERS + 1):
            is_wu = i <= WARMUP
            prefix = "WU" if is_wu else "  "
            for name, deploy, effort_s1, _ in MODELS:
                try:
                    ttft, e2e, tlen = run_s1(client, deploy, effort_s1, qtext, maxtok)
                    results.append({
                        "scenario": "S1_direct",
                        "model": name, "query": qname, "iter": i,
                        "warmup": is_wu,
                        "ttft": round(ttft, 3), "e2e": round(e2e, 3), "len": tlen,
                    })
                    print(f"  {prefix} i{i:2d} {name:15s} TTFT={ttft:.2f}s E2E={e2e:.2f}s len={tlen}")
                except Exception as e:
                    print(f"  {prefix} i{i:2d} {name:15s} ERROR: {str(e)[:80]}")

    # S1 summary
    print("\n" + "=" * 70)
    print("  S1 Summary (warmup discarded)")
    print("=" * 70)
    print(f"{'Model':<16} {'effort':<8} {'Avg TTFT':>10} {'P50':>8} {'P95':>8} {'σ':>6} {'Avg E2E':>10} {'N':>4}")
    for name, _, effort_s1, _ in MODELS:
        recs = [r for r in results if r["scenario"] == "S1_direct" and r["model"] == name and not r["warmup"]]
        if recs:
            arr = np.array([r["ttft"] for r in recs])
            e2es = np.array([r["e2e"] for r in recs])
            eff = effort_s1 or "N/A"
            print(f"{name:<16} {eff:<8} {np.mean(arr):>9.2f}s {np.percentile(arr,50):>7.2f}s {np.percentile(arr,95):>7.2f}s {np.std(arr):>5.2f}s {np.mean(e2es):>9.2f}s {len(arr):>4}")

    # ─── S4: Direct AOAI + web_search_preview ──────────────────
    print("\n" + "=" * 70)
    print("  S4: Direct AOAI + web_search_preview (customer's Bing path)")
    print("  tool_choice=required, single-search instruction")
    print("=" * 70)

    for qname, qtext, maxtok in QUERIES:
        print(f"\n  [{qname}] max_tokens={maxtok}")
        for i in range(1, ITERS + 1):
            is_wu = i <= WARMUP
            prefix = "WU" if is_wu else "  "
            for name, deploy, _, effort_ws in MODELS:
                try:
                    ttft, e2e, tlen, searched = run_s4_websearch(client, deploy, effort_ws, qtext, maxtok)
                    tag = "🔍" if searched else "⚠️NS"
                    results.append({
                        "scenario": "S4_websearch",
                        "model": name, "query": qname, "iter": i,
                        "warmup": is_wu,
                        "ttft": round(ttft, 3), "e2e": round(e2e, 3), "len": tlen,
                        "searched": searched,
                    })
                    print(f"  {prefix} i{i:2d} {name:15s} TTFT={ttft:.2f}s E2E={e2e:.2f}s len={tlen} {tag}")
                except Exception as e:
                    print(f"  {prefix} i{i:2d} {name:15s} ERROR: {str(e)[:80]}")

    # S4 summary — only count samples where web_search was confirmed
    print("\n" + "=" * 70)
    print("  S4 Summary (warmup discarded, web_search confirmed only)")
    print("=" * 70)
    print(f"{'Model':<16} {'effort':<8} {'Avg TTFT':>10} {'P50':>8} {'P95':>8} {'σ':>6} {'Avg E2E':>10} {'N':>4} {'Skip':>5}")
    for name, _, _, effort_ws in MODELS:
        all_recs = [r for r in results if r["scenario"] == "S4_websearch" and r["model"] == name and not r["warmup"]]
        recs = [r for r in all_recs if r.get("searched", True)]
        skipped = len(all_recs) - len(recs)
        if recs:
            arr = np.array([r["ttft"] for r in recs])
            e2es = np.array([r["e2e"] for r in recs])
            eff = effort_ws or "N/A"
            print(f"{name:<16} {eff:<8} {np.mean(arr):>9.2f}s {np.percentile(arr,50):>7.2f}s {np.percentile(arr,95):>7.2f}s {np.std(arr):>5.2f}s {np.mean(e2es):>9.2f}s {len(arr):>4} {skipped:>5}")

    # ─── Grand Summary ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  GRAND SUMMARY — S1 vs S4 (web_search)")
    print("=" * 70)
    print(f"{'Model':<16} {'eff':>8} | {'S1 P50':>8} {'S1 E2E':>8} | {'S4 P50':>8} {'S4 E2E':>8} | {'WS OH':>8}")
    print("-" * 80)
    for name, _, effort_s1, effort_ws in MODELS:
        s1 = [r["ttft"] for r in results if r["scenario"] == "S1_direct" and r["model"] == name and not r["warmup"]]
        s4 = [r["ttft"] for r in results if r["scenario"] == "S4_websearch" and r["model"] == name and not r["warmup"] and r.get("searched", True)]
        s1e = [r["e2e"] for r in results if r["scenario"] == "S1_direct" and r["model"] == name and not r["warmup"]]
        s4e = [r["e2e"] for r in results if r["scenario"] == "S4_websearch" and r["model"] == name and not r["warmup"] and r.get("searched", True)]
        if s1 and s4:
            s1p = np.percentile(s1, 50)
            s4p = np.percentile(s4, 50)
            oh = s4p - s1p
            eff = effort_s1 or "N/A"
            print(f"{name:<16} {eff:>8} | {s1p:>7.2f}s {np.mean(s1e):>7.2f}s | {s4p:>7.2f}s {np.mean(s4e):>7.2f}s | {'+'+f'{oh:.2f}s':>8}")

    # Save
    outfile = f"outputs/benchmark_websearch_{ts}.json"
    with open(outfile, "w") as f:
        json.dump({
            "benchmark": "websearch_2scenarios",
            "timestamp": ts,
            "config": {
                "endpoint": AOAI_ENDPOINT,
                "api_version": AOAI_API_VER,
                "iterations": ITERS,
                "warmup": WARMUP,
                "models": [m[0] for m in MODELS],
                "note": "S4 uses web_search_preview (customer actual path), NOT Foundry Agent + Bing"
            },
            "results": results,
        }, f, indent=2)
    print(f"\nSaved: {outfile}")
    print("DONE.")


if __name__ == "__main__":
    main()
