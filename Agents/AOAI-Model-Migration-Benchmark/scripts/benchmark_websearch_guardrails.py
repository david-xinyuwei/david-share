#!/usr/bin/env python3
"""
AI assistant web_search Benchmark — Comprehensive (Customer Actual Architecture)
========================================================================
Tests the customer production path:
    - Responses API + web_search_preview (NOT Foundry Agent)
    - Optional WebIQ explicit retrieval path for every web-search scenario
  - GUARDRAILS system prompt (~1066 tokens, triggers prompt caching)
  - search_context_size="low"
  - tool_choice="auto" (verified 100% search trigger via streaming events)
  - reasoning_effort: none for 5.4, low for 5 (minimal not supported with web_search)

3 Scenarios per run:
  S1: Direct AOAI (no search, with GUARDRAILS prompt)
  S4: Direct AOAI + web_search_preview (with GUARDRAILS prompt)
  S5: WebIQ search + AOAI generation (explicit retrieval, optional --webiq-key)

5 Models × 3 Queries × 10 iterations (2 warmup) = 24 samples/model/scenario/run
Run multiple times for statistical robustness.

Author: Xinyu Wei (魏新宇)
"""

import json, time, datetime, os, argparse, re
import numpy as np
from openai import AzureOpenAI

try:
    from webiq import WebIQClient, ApiKeyAuth
    WEBIQ_AVAILABLE = True
except ImportError:
    WEBIQ_AVAILABLE = False

# ── GUARDRAILS system prompt (1066 tokens — triggers prompt caching) ──
GUARDRAILS = """
[GUARDRAILS — AI Assistant Behavioral Framework v2.1]

Section 1: Identity & Persona
You are a system-level cross-device AI assistant. You serve users across PCs, tablets, and phones. Maintain a professional, helpful, and concise communication style.

Section 2: Safety & Content Policy
Never generate harmful, hateful, violent, sexually explicit, or illegal content. Decline requests for malware, weapons, or dangerous activities. Redirect users to emergency services when life-threatening situations are detected.

Section 3: Privacy & Data Protection
Never request, store, or transmit personal identification numbers, passwords, financial account details, or health records. Do not reference previous conversation history unless explicitly provided in the current session.

Section 4: Accuracy & Hallucination Prevention
Only provide information you are confident about. When uncertain, clearly state limitations. Never fabricate citations, URLs, product specifications, or pricing. For real-time data, use Bing grounding.

Section 5: Brand & Product Guidelines
Represent products accurately. Do not make comparative claims against competitors unless backed by published benchmarks. Always recommend consulting official support channels for hardware issues.

Section 6: Response Format Standards
Keep responses concise and actionable. Use bullet points for lists exceeding 3 items. Include relevant disclaimers for medical, legal, or financial topics. Format code blocks with appropriate syntax highlighting.

Section 7: Multi-Device Context
Adapt response length and format to the device context. Shorter responses for phone interactions, detailed responses for PC sessions. Respect device-specific capabilities in recommendations.

Section 8: Escalation Protocol
For issues beyond your capability, provide official support contact information. For urgent device malfunctions, recommend immediate professional service. Never attempt to guide users through hardware repairs.

Section 9: Language & Localization
Respond in the user's language. Maintain cultural sensitivity across regions. Use metric or imperial units based on user locale. Adapt formality level to cultural norms.

Section 10: Session Management
Each conversation is independent. Do not assume continuity between sessions. Clearly acknowledge when context from the current session is being referenced.

Section 11: Tool Usage Guidelines
When using web search, perform exactly ONE search query. Do not refine or repeat searches. Use search results to provide current, factual information. Always cite the source of searched information.

Section 12: Compliance & Auditing
All responses must comply with applicable laws and regulations. Interactions may be logged for quality assurance. Maintain transparency about AI nature when directly asked.
"""

SYSTEM_MSG = "You are a helpful AI assistant. Answer concisely.\n" + GUARDRAILS
SEARCH_SYSTEM_MSG = "You are a helpful AI assistant. Answer concisely. Search the web for current information.\n" + GUARDRAILS

MODELS = [
    # (display_name, deployment_name, effort_s1, effort_websearch)
    ("gpt-4o-mini",   "gpt-4o-mini",   None,      None),
    ("gpt-5-mini",    "gpt-5-mini",    "minimal", "low"),
    ("gpt-5-nano",    "gpt-5-nano",    "minimal", "low"),
    ("gpt-5.4-mini",  "gpt-5.4-mini",  "none",    "none"),
    ("gpt-5.4-nano",  "gpt-5.4-nano",  "none",    "none"),
]

QUERIES = [
    ("pricing",  "What is the latest retail price for a flagship enterprise laptop?", 300),
    ("news",     "What are the top AI news stories this week?", 300),
    ("weather",  "What is the current weather in Seattle, Washington?", 200),
]


def parse_args():
    parser = argparse.ArgumentParser(description="AI assistant web_search Benchmark — Customer Actual Architecture")
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                        help="Azure OpenAI endpoint URL")
    parser.add_argument("--api-key", dest="api_key", default=os.environ.get("AZURE_OPENAI_API_KEY", ""),
                        help="Azure OpenAI API key")
    parser.add_argument("--api-version", dest="api_version", default="2025-04-01-preview")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per query (default: 10)")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup iterations (default: 2)")
    parser.add_argument("--output-dir", dest="output_dir", default="outputs")
    parser.add_argument("--webiq-key", dest="webiq_key",
                        default=os.environ.get("WEBIQ_API_KEY", ""),
                        help="WebIQ API key. If set, runs S5 (WebIQ E2E) for comparison.")
    parser.add_argument("--webiq-max-results", dest="webiq_max_results", type=int, default=5,
                        help="WebIQ max search results (default: 5)")
    return parser.parse_args()


def run_s1(client, deploy, effort, query, max_tokens):
    """S1: Direct AOAI + GUARDRAILS prompt (no search)"""
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
        if getattr(ev, "type", "") == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - t0
            txt += ev.delta
    e2e = time.perf_counter() - t0
    if ttft is None:
        ttft = e2e
    return ttft, e2e, len(txt)


def run_s4(client, deploy, effort, query, max_tokens):
    """S4: Direct AOAI + web_search_preview + GUARDRAILS (customer path)"""
    t0 = time.perf_counter()
    ttft = None
    txt = ""
    searched = False
    kwargs = {
        "model": deploy,
        "stream": True,
        "tools": [{"type": "web_search_preview", "search_context_size": "low"}],
        "input": [
            {"role": "system", "content": SEARCH_SYSTEM_MSG},
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


WEBIQ_SYSTEM_MSG = (
    "You are a helpful AI assistant. Answer concisely using only the provided "
    "WebIQ search context. Include source URLs from the context for factual claims.\n"
    + GUARDRAILS
)


def run_s5(aoai_client, webiq_client, deploy, effort, query, max_tokens, max_results=5):
    """S5: WebIQ search + AOAI Responses API generation (explicit retrieval path)"""
    # Step 1: WebIQ search
    t0 = time.perf_counter()
    response = webiq_client.web.search(query=query, max_results=max_results)
    search_lat = time.perf_counter() - t0

    web_results = getattr(response, "webResults", []) or []
    context_parts = []
    for i, r in enumerate(web_results, 1):
        title = getattr(r, "title", "") or ""
        url = getattr(r, "url", "") or ""
        content = getattr(r, "content", "") or ""
        plain = re.sub(r"<[^>]+>", " ", content)
        plain = re.sub(r"\s+", " ", plain).strip()
        context_parts.append(f"[{i}] {title}\nURL: {url}\n{plain[:1600]}")
    context = "\n\n".join(context_parts)

    # Step 2: AOAI generation with WebIQ context
    user_msg = (
        f"Based on the following search results, answer the question.\n\n"
        f"--- SEARCH RESULTS ---\n{context}\n--- END ---\n\n"
        f"Question: {query}"
    )
    kwargs = {
        "model": deploy,
        "stream": True,
        "input": [
            {"role": "system", "content": WEBIQ_SYSTEM_MSG},
            {"role": "user", "content": user_msg},
        ],
        "max_output_tokens": max_tokens,
    }
    if effort:
        kwargs["reasoning"] = {"effort": effort}

    t1 = time.perf_counter()
    ttft = None
    txt = ""
    stream = aoai_client.responses.create(**kwargs)
    for ev in stream:
        if getattr(ev, "type", "") == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - t1
            txt += ev.delta
    model_e2e = time.perf_counter() - t1
    if ttft is None:
        ttft = model_e2e
    total_ttft = search_lat + ttft
    total_e2e = search_lat + model_e2e
    return total_ttft, total_e2e, len(txt), search_lat, ttft


def main():
    args = parse_args()
    client = AzureOpenAI(
        api_key=args.api_key,
        azure_endpoint=args.endpoint,
        api_version=args.api_version,
    )

    results = []
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    effective = (args.iterations - args.warmup) * len(QUERIES)

    print(f"Benchmark: web_search (GUARDRAILS prompt) — {len(MODELS)} models × {len(QUERIES)} queries × {args.iterations} iter")
    print(f"Warmup: {args.warmup} → {effective} effective samples/model/scenario")
    print(f"System prompt: ~1066 tokens (GUARDRAILS — prompt caching eligible)")
    print(f"Endpoint: {args.endpoint}")

    # ─── S1 ───
    print("\n" + "=" * 70)
    print("  S1: Direct AOAI + GUARDRAILS (no search)")
    print("=" * 70)
    for qname, qtext, maxtok in QUERIES:
        print(f"\n  [{qname}] max_tokens={maxtok}")
        for i in range(1, args.iterations + 1):
            is_wu = i <= args.warmup
            prefix = "WU" if is_wu else "  "
            for name, deploy, effort_s1, _ in MODELS:
                try:
                    ttft, e2e, tlen = run_s1(client, deploy, effort_s1, qtext, maxtok)
                    results.append({
                        "scenario": "S1_direct_guardrails", "model": name,
                        "query": qname, "iter": i, "warmup": is_wu,
                        "success": True,
                        "ttft": round(ttft, 3), "e2e": round(e2e, 3), "len": tlen,
                    })
                    print(f"  {prefix} i{i:2d} {name:15s} TTFT={ttft:.2f}s E2E={e2e:.2f}s len={tlen}")
                except Exception as e:
                    results.append({
                        "scenario": "S1_direct_guardrails", "model": name,
                        "query": qname, "iter": i, "warmup": is_wu,
                        "success": False, "error": str(e)[:500],
                    })
                    print(f"  {prefix} i{i:2d} {name:15s} ERROR: {str(e)[:80]}")

    # S1 summary
    print("\n" + "=" * 70)
    print("  S1 Summary (GUARDRAILS, warmup discarded)")
    print("=" * 70)
    for name, _, effort_s1, _ in MODELS:
        recs = [r for r in results if r["scenario"] == "S1_direct_guardrails" and r["model"] == name and not r["warmup"] and r.get("success", True)]
        if recs:
            arr = np.array([r["ttft"] for r in recs])
            eff = effort_s1 or "N/A"
            print(f"  {name:<16} {eff:<8} P50={np.percentile(arr,50):.2f}s σ={np.std(arr):.2f}s N={len(arr)}")

    # ─── S4 ───
    print("\n" + "=" * 70)
    print("  S4: Direct AOAI + web_search + GUARDRAILS (customer path)")
    print("=" * 70)
    for qname, qtext, maxtok in QUERIES:
        print(f"\n  [{qname}] max_tokens={maxtok}")
        for i in range(1, args.iterations + 1):
            is_wu = i <= args.warmup
            prefix = "WU" if is_wu else "  "
            for name, deploy, _, effort_ws in MODELS:
                try:
                    ttft, e2e, tlen, searched = run_s4(client, deploy, effort_ws, qtext, maxtok)
                    tag = "SEARCH" if searched else "NO_SEARCH"
                    results.append({
                        "scenario": "S4_websearch_guardrails", "model": name,
                        "query": qname, "iter": i, "warmup": is_wu,
                        "success": True,
                        "ttft": round(ttft, 3), "e2e": round(e2e, 3), "len": tlen,
                        "searched": searched,
                    })
                    print(f"  {prefix} i{i:2d} {name:15s} TTFT={ttft:.2f}s E2E={e2e:.2f}s len={tlen} {tag}")
                except Exception as e:
                    results.append({
                        "scenario": "S4_websearch_guardrails", "model": name,
                        "query": qname, "iter": i, "warmup": is_wu,
                        "success": False, "searched": False, "error": str(e)[:500],
                    })
                    print(f"  {prefix} i{i:2d} {name:15s} ERROR: {str(e)[:80]}")

    # S4 summary
    print("\n" + "=" * 70)
    print("  S4 Summary (GUARDRAILS + web_search, search verified only)")
    print("=" * 70)
    for name, _, _, effort_ws in MODELS:
        all_recs = [r for r in results if r["scenario"] == "S4_websearch_guardrails" and r["model"] == name and not r["warmup"]]
        recs = [r for r in all_recs if r.get("success", True) and r.get("searched", True)]
        skip = len(all_recs) - len(recs)
        if recs:
            arr = np.array([r["ttft"] for r in recs])
            eff = effort_ws or "N/A"
            print(f"  {name:<16} {eff:<8} P50={np.percentile(arr,50):.2f}s σ={np.std(arr):.2f}s N={len(arr)} Skip={skip}")

    # ─── S5: WebIQ E2E (optional, runs if --webiq-key is set) ───
    webiq_client = None
    if args.webiq_key:
        if not WEBIQ_AVAILABLE:
            print("\nWARNING: webiq package not installed. Skipping S5. pip install webiq")
        else:
            webiq_client = WebIQClient(auth=ApiKeyAuth(api_key=args.webiq_key))
            print("\n" + "=" * 70)
            print("  S5: WebIQ search + AOAI generation (explicit retrieval path)")
            print("=" * 70)
            for qname, qtext, maxtok in QUERIES:
                print(f"\n  [{qname}] max_tokens={maxtok}")
                for i in range(1, args.iterations + 1):
                    is_wu = i <= args.warmup
                    prefix = "WU" if is_wu else "  "
                    for name, deploy, _, effort_ws in MODELS:
                        try:
                            total_ttft, total_e2e, tlen, search_lat, model_ttft = run_s5(
                                client, webiq_client, deploy, effort_ws, qtext, maxtok, args.webiq_max_results
                            )
                            results.append({
                                "scenario": "S5_webiq_guardrails", "model": name,
                                "query": qname, "iter": i, "warmup": is_wu,
                                "success": True,
                                "ttft": round(total_ttft, 3), "e2e": round(total_e2e, 3),
                                "search_lat": round(search_lat, 3),
                                "model_ttft": round(model_ttft, 3),
                                "len": tlen,
                            })
                            print(f"  {prefix} i{i:2d} {name:15s} Search={search_lat*1000:.0f}ms Model={model_ttft*1000:.0f}ms Total={total_ttft:.2f}s len={tlen}")
                        except Exception as e:
                            results.append({
                                "scenario": "S5_webiq_guardrails", "model": name,
                                "query": qname, "iter": i, "warmup": is_wu,
                                "success": False, "error": str(e)[:500],
                            })
                            print(f"  {prefix} i{i:2d} {name:15s} ERROR: {str(e)[:80]}")

            # S5 summary
            print("\n" + "=" * 70)
            print("  S5 Summary (WebIQ + AOAI, warmup discarded)")
            print("=" * 70)
            for name, _, _, effort_ws in MODELS:
                recs = [r for r in results if r["scenario"] == "S5_webiq_guardrails" and r["model"] == name and not r["warmup"] and r.get("success", True)]
                if recs:
                    arr = np.array([r["ttft"] for r in recs])
                    search_arr = np.array([r["search_lat"] for r in recs])
                    eff = effort_ws or "N/A"
                    print(f"  {name:<16} {eff:<8} P50={np.percentile(arr,50):.2f}s Search_P50={np.percentile(search_arr,50)*1000:.0f}ms N={len(arr)}")

    # Grand summary
    print("\n" + "=" * 70)
    header = "  GRAND SUMMARY — S1 vs S4 (web_search_preview)"
    if webiq_client:
        header += " vs S5 (WebIQ)"
    print(header)
    print("=" * 70)
    if webiq_client:
        print(f"  {'Model':<16} | {'S1 P50':>8} | {'S4 P50':>8} | {'S5 P50':>8} | {'WS OH':>8} | {'WebIQ OH':>8} | {'S5 faster':>10}")
        print("  " + "-" * 90)
    else:
        print(f"  {'Model':<16} | {'S1 P50':>8} | {'S4 P50':>8} | {'WS OH':>8}")
        print("  " + "-" * 55)
    for name, _, effort_s1, effort_ws in MODELS:
        s1 = [r["ttft"] for r in results if r["scenario"] == "S1_direct_guardrails" and r["model"] == name and not r["warmup"] and r.get("success", True)]
        s4 = [r["ttft"] for r in results if r["scenario"] == "S4_websearch_guardrails" and r["model"] == name and not r["warmup"] and r.get("success", True) and r.get("searched", True)]
        s5 = [r["ttft"] for r in results if r["scenario"] == "S5_webiq_guardrails" and r["model"] == name and not r["warmup"] and r.get("success", True)] if webiq_client else []
        if s1 and s4:
            s1p = np.percentile(s1, 50)
            s4p = np.percentile(s4, 50)
            if s5:
                s5p = np.percentile(s5, 50)
                delta_pct = (s4p - s5p) / s4p * 100
                print(f"  {name:<16} | {s1p:>7.2f}s | {s4p:>7.2f}s | {s5p:>7.2f}s | {'+'+f'{s4p-s1p:.2f}s':>8} | {'+'+f'{s5p-s1p:.2f}s':>8} | {delta_pct:>9.1f}%")
            else:
                print(f"  {name:<16} | {s1p:>7.2f}s | {s4p:>7.2f}s | {'+'+f'{s4p-s1p:.2f}s':>8}")

    # Save
    outfile = os.path.join(args.output_dir, f"benchmark_websearch_guardrails_{ts}.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(outfile, "w") as f:
        json.dump({
            "benchmark": "websearch_guardrails_comprehensive",
            "timestamp": ts,
            "config": {
                "endpoint": args.endpoint,
                "api_version": args.api_version,
                "iterations": args.iterations,
                "warmup": args.warmup,
                "system_prompt_tokens": "~1066 (GUARDRAILS)",
                "search_context_size": "low",
                "tool_choice": "auto (100% trigger verified)",
                "webiq_enabled": bool(webiq_client),
                "webiq_max_results": args.webiq_max_results if webiq_client else None,
            },
            "results": results,
        }, f, indent=2)
    print(f"\nSaved: {outfile}")
    print("DONE.")


if __name__ == "__main__":
    main()
