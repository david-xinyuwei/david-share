#!/usr/bin/env python3
"""
Super Detective 3-Scenario × 5-Model Benchmark (ALL Responses API + Streaming)

S1: Direct AOAI — Responses API + streaming (no agent, no Bing)
S2: Foundry Agent V2 — Responses API + streaming (no Bing)
S3: Foundry Agent V2 — Responses API + streaming (with Bing + tool_choice=required)

All scenarios:
  - stream=True
  - reasoning_effort at model minimum (none for 5.4, minimal for 5)
  - Single-search instruction for S3
  - 10 iterations, 2 warmup discarded = 24 effective samples/model/scenario

Author: Xinyu Wei
"""

import time, json, os, statistics
from datetime import datetime

from openai import AzureOpenAI
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    BingGroundingAgentTool,
    BingGroundingSearchToolParameters,
    BingGroundingSearchConfiguration,
    Reasoning,
)
from azure.identity import DefaultAzureCredential

# ── Config ──────────────────────────────────────────────────────────────
AOAI_ENDPOINT = "https://<your-endpoint>.openai.azure.com"
AOAI_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "<your-api-key>")
AOAI_API_VER = "2025-04-01-preview"

FOUNDRY_ENDPOINT = "https://admin-4171-resource.services.ai.azure.com/api/projects/admin-4171"
BING_CONN_NAME = "davibing"

# (display, direct_deploy, foundry_deploy, reasoning_effort)
MODELS = [
    ("gpt-4o-mini",   "gpt-4o-mini",  "gpt-4o-mini",  None),
    ("gpt-5-mini",    "gpt-5-mini",   "gpt-5-mini",   "minimal"),
    ("gpt-5-nano",    "gpt-5-nano",   "gpt-5-nano",   "minimal"),
    ("gpt-5.4-mini",  "gpt-5.4-mini", "gpt-54-mini",  "none"),
    ("gpt-5.4-nano",  "gpt-5.4-nano", "gpt-54-nano",  "none"),
]

SYSTEM_MSG = "You are a helpful AI assistant. Answer concisely."
BING_INSTRUCTION = """You are a helpful AI assistant. Answer concisely.
CRITICAL: Perform exactly ONE search. Do NOT refine or repeat searches. Use first results immediately. Speed > completeness."""

QUERIES = [
    ("pricing", "What is the latest retail price for a ThinkPad X1 Carbon Gen 12?", 300),
    ("news",    "What are the top AI news stories this week?", 300),
    ("weather", "What is the current weather in Seattle, Washington?", 200),
]

ITERATIONS = 10      # per query per model
WARMUP = 2           # first N iterations discarded
SLEEP = 0.3          # seconds between calls

# ── Helpers ─────────────────────────────────────────────────────────────

def run_responses_direct(client, deploy, effort, query, max_tokens):
    """S1: Direct AOAI Responses API + Streaming"""
    t0 = time.perf_counter()
    ttft = None
    txt = ""
    kwargs = {
        "model": deploy,
        "stream": True,
        "input": query,
        "max_output_tokens": max_tokens,
        "instructions": SYSTEM_MSG,
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
    return ttft, e2e, len(txt)


def run_foundry_agent(openai_client, agent_name, query, max_tokens, use_tool_choice=False):
    """S2/S3: Foundry Agent V2 Responses API + Streaming"""
    t0 = time.perf_counter()
    ttft = None
    txt = ""
    kwargs = {
        "stream": True,
        "input": query,
        "max_output_tokens": max_tokens,
        "extra_body": {
            "agent_reference": {"name": agent_name, "type": "agent_reference"}
        },
    }
    if use_tool_choice:
        kwargs["tool_choice"] = "required"

    stream = openai_client.responses.create(**kwargs)
    for ev in stream:
        if hasattr(ev, "type") and ev.type == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - t0
            txt += ev.delta
    e2e = time.perf_counter() - t0
    return ttft, e2e, len(txt)


def stats(results, scenario, model):
    rows = [r for r in results
            if r["scenario"] == scenario and r["model"] == model
            and r.get("ttft") is not None and r["iter"] > WARMUP]
    if not rows:
        return None
    ts = sorted([r["ttft"] for r in rows])
    es = [r["e2e"] for r in rows]
    return {
        "n": len(rows),
        "avg_ttft": round(sum(ts) / len(ts), 2),
        "p50_ttft": round(ts[len(ts) // 2], 2),
        "p95_ttft": round(ts[int(len(ts) * 0.95)], 2) if len(ts) >= 5 else None,
        "std_ttft": round(statistics.stdev(ts), 2) if len(ts) > 1 else 0,
        "avg_e2e": round(sum(es) / len(es), 2),
        "max_ttft": round(max(ts), 2),
    }


def print_scenario_summary(results, scenario, label):
    print(f"\n{'=' * 70}")
    print(f"  {label} — Summary (warmup={WARMUP} discarded)")
    print(f"{'=' * 70}")
    print(f"{'Model':14s} {'effort':>8} {'Avg TTFT':>9} {'P50':>7} {'P95':>7} {'σ':>6} {'Avg E2E':>9} {'N':>4}")
    print("-" * 65)
    for disp, _, _, eff in MODELS:
        s = stats(results, scenario, disp)
        if s:
            p95 = f"{s['p95_ttft']}s" if s['p95_ttft'] else "N/A"
            print(f"{disp:14s} {(eff or 'N/A'):>8} {s['avg_ttft']:>8.2f}s {s['p50_ttft']:>6.2f}s {p95:>7} {s['std_ttft']:>5.2f}s {s['avg_e2e']:>8.2f}s {s['n']:>4}")
        else:
            print(f"{disp:14s} {'N/A':>8} {'ERR':>9}")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    all_results = []
    total_calls = 3 * len(MODELS) * len(QUERIES) * ITERATIONS
    effective = 3 * len(MODELS) * len(QUERIES) * (ITERATIONS - WARMUP)
    print(f"Super Detective: {total_calls} total calls, {effective} effective samples")
    print(f"5 models × 3 queries × {ITERATIONS} iter × 3 scenarios = {total_calls}")
    print(f"Warmup: {WARMUP} → {effective} effective")

    # ─── S1: Direct AOAI Responses API ──────────────────────────────────
    print("\n" + "=" * 70)
    print("  S1: Direct AOAI — Responses API + Streaming")
    print("  Endpoint:", AOAI_ENDPOINT)
    print("=" * 70)

    direct_client = AzureOpenAI(
        api_key=AOAI_KEY,
        azure_endpoint=AOAI_ENDPOINT,
        api_version=AOAI_API_VER,
    )

    s1_results = []
    for qid, query, maxt in QUERIES:
        print(f"\n  [{qid}] max_tokens={maxt}")
        for i in range(1, ITERATIONS + 1):
            for disp, deploy, _, eff in MODELS:
                try:
                    ttft, e2e, tlen = run_responses_direct(direct_client, deploy, eff, query, maxt)
                    tag = "WU" if i <= WARMUP else "  "
                    tf = f"{ttft:.2f}" if ttft else "N/A"
                    print(f"  {tag} i{i:>2} {disp:14s} TTFT={tf}s E2E={e2e:.2f}s len={tlen}")
                    rec = {"scenario": "S1_direct_responses", "model": disp, "query": qid, "iter": i,
                           "ttft": round(ttft, 3) if ttft else None, "e2e": round(e2e, 3), "len": tlen}
                except Exception as ex:
                    print(f"  i{i:>2} {disp:14s} ERR: {str(ex)[:80]}")
                    rec = {"scenario": "S1_direct_responses", "model": disp, "query": qid, "iter": i,
                           "error": str(ex)[:200]}
                s1_results.append(rec)
                time.sleep(SLEEP)

    print_scenario_summary(s1_results, "S1_direct_responses", "S1: Direct AOAI (Responses API)")
    all_results.extend(s1_results)

    # ─── Setup Foundry ──────────────────────────────────────────────────
    print("\n\nSetting up Foundry Agent Service V2 ...")
    project = AIProjectClient(
        endpoint=FOUNDRY_ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    openai_client = project.get_openai_client()
    bing_conn = project.connections.get(BING_CONN_NAME)

    # ─── S2: Foundry Agent V2, NO Bing ─────────────────────────────────
    print("\n" + "=" * 70)
    print("  S2: Foundry Agent V2 — NO Bing — Responses API + Streaming")
    print("=" * 70)

    s2_agents = {}
    for disp, _, fdeploy, eff in MODELS:
        short = fdeploy.replace("gpt-", "g").replace(".", "")
        agent_name = f"d2-{short}-{ts}"
        kwargs = {}
        if eff:
            kwargs["reasoning"] = Reasoning(effort=eff)
        agent = project.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=fdeploy,
                instructions=SYSTEM_MSG,
                tools=[],
                **kwargs,
            ),
        )
        s2_agents[disp] = agent
        print(f"  Agent: {agent.name} (model={fdeploy}, effort={eff})")

    s2_results = []
    for qid, query, maxt in QUERIES:
        print(f"\n  [{qid}] max_tokens={maxt}")
        for i in range(1, ITERATIONS + 1):
            for disp, _, _, eff in MODELS:
                agent = s2_agents[disp]
                try:
                    ttft, e2e, tlen = run_foundry_agent(openai_client, agent.name, query, maxt)
                    tag = "WU" if i <= WARMUP else "  "
                    tf = f"{ttft:.2f}" if ttft else "N/A"
                    print(f"  {tag} i{i:>2} {disp:14s} TTFT={tf}s E2E={e2e:.2f}s len={tlen}")
                    rec = {"scenario": "S2_foundry_no_bing", "model": disp, "query": qid, "iter": i,
                           "ttft": round(ttft, 3) if ttft else None, "e2e": round(e2e, 3), "len": tlen}
                except Exception as ex:
                    print(f"  i{i:>2} {disp:14s} ERR: {str(ex)[:80]}")
                    rec = {"scenario": "S2_foundry_no_bing", "model": disp, "query": qid, "iter": i,
                           "error": str(ex)[:200]}
                s2_results.append(rec)
                time.sleep(SLEEP)

    print_scenario_summary(s2_results, "S2_foundry_no_bing", "S2: Foundry Agent V2 (no Bing)")
    all_results.extend(s2_results)

    for _, agent in s2_agents.items():
        try:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        except Exception:
            pass

    # ─── S3: Foundry Agent V2, WITH Bing ────────────────────────────────
    print("\n" + "=" * 70)
    print("  S3: Foundry Agent V2 — WITH Bing — Responses API + Streaming")
    print("  tool_choice=required, single-search instruction")
    print("=" * 70)

    s3_agents = {}
    for disp, _, fdeploy, eff in MODELS:
        short = fdeploy.replace("gpt-", "g").replace(".", "")
        agent_name = f"d3-{short}-{ts}"
        kwargs = {}
        if eff:
            kwargs["reasoning"] = Reasoning(effort=eff)
        agent = project.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=fdeploy,
                instructions=BING_INSTRUCTION,
                tools=[
                    BingGroundingAgentTool(
                        bing_grounding=BingGroundingSearchToolParameters(
                            search_configurations=[
                                BingGroundingSearchConfiguration(
                                    project_connection_id=bing_conn.id
                                )
                            ]
                        )
                    )
                ],
                **kwargs,
            ),
        )
        s3_agents[disp] = agent
        print(f"  Agent: {agent.name} (model={fdeploy}, effort={eff})")

    s3_results = []
    for qid, query, maxt in QUERIES:
        print(f"\n  [{qid}] max_tokens={maxt}")
        for i in range(1, ITERATIONS + 1):
            for disp, _, _, eff in MODELS:
                agent = s3_agents[disp]
                try:
                    ttft, e2e, tlen = run_foundry_agent(openai_client, agent.name, query, maxt, use_tool_choice=True)
                    tag = "WU" if i <= WARMUP else "  "
                    tf = f"{ttft:.2f}" if ttft else "N/A"
                    print(f"  {tag} i{i:>2} {disp:14s} TTFT={tf}s E2E={e2e:.2f}s len={tlen}")
                    rec = {"scenario": "S3_foundry_bing", "model": disp, "query": qid, "iter": i,
                           "ttft": round(ttft, 3) if ttft else None, "e2e": round(e2e, 3), "len": tlen}
                except Exception as ex:
                    print(f"  i{i:>2} {disp:14s} ERR: {str(ex)[:80]}")
                    rec = {"scenario": "S3_foundry_bing", "model": disp, "query": qid, "iter": i,
                           "error": str(ex)[:200]}
                s3_results.append(rec)
                time.sleep(SLEEP)

    print_scenario_summary(s3_results, "S3_foundry_bing", "S3: Foundry Agent V2 (with Bing)")
    all_results.extend(s3_results)

    for _, agent in s3_agents.items():
        try:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        except Exception:
            pass

    # ─── Grand Summary ──────────────────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("  GRAND SUMMARY — Super Detective — 3 Scenarios × 5 Models (all Responses API)")
    print("  Effective samples per model per scenario:", len(QUERIES) * (ITERATIONS - WARMUP))
    print("=" * 100)

    scenarios = [
        ("S1_direct_responses", "S1 Direct"),
        ("S2_foundry_no_bing", "S2 Foundry"),
        ("S3_foundry_bing", "S3 +Bing"),
    ]

    hdr = f"{'Model':14s} {'eff':>7}"
    for _, label in scenarios:
        hdr += f" | {label+' TTFT':>14} {label+' E2E':>13}"
    hdr += " | {'Bing OH':>8}"
    print(hdr)
    print("-" * 100)

    for disp, _, _, eff in MODELS:
        line = f"{disp:14s} {(eff or 'N/A'):>7}"
        s_vals = {}
        for sc_key, sc_label in scenarios:
            s = stats(all_results, sc_key, disp)
            s_vals[sc_key] = s
            if s:
                line += f" | {s['avg_ttft']:>7.2f}s(p50={s['p50_ttft']:.2f}) {s['avg_e2e']:>6.2f}s"
            else:
                line += f" | {'ERR':>14} {'ERR':>13}"

        # Bing overhead = S3 - S2
        s2 = s_vals.get("S2_foundry_no_bing")
        s3 = s_vals.get("S3_foundry_bing")
        if s2 and s3:
            oh = s3["avg_ttft"] - s2["avg_ttft"]
            line += f" | {oh:>+7.2f}s"
        else:
            line += f" | {'N/A':>8}"

        print(line)

    # Foundry overhead = S2 - S1
    print()
    print("Foundry overhead (S2 - S1 TTFT):")
    for disp, _, _, eff in MODELS:
        s1 = stats(all_results, "S1_direct_responses", disp)
        s2 = stats(all_results, "S2_foundry_no_bing", disp)
        if s1 and s2:
            oh = s2["avg_ttft"] - s1["avg_ttft"]
            print(f"  {disp:14s}: {oh:>+.2f}s")

    # ─── Save ───────────────────────────────────────────────────────────
    outfile = f"outputs/benchmark_detective_3s_{ts.replace('-','_')}.json"
    json.dump({
        "benchmark": "Super Detective: 3-scenario × 5-model (all Responses API)",
        "timestamp": ts,
        "config": {
            "iterations": ITERATIONS, "warmup": WARMUP,
            "effective_per_model_per_scenario": len(QUERIES) * (ITERATIONS - WARMUP),
            "queries": [q[0] for q in QUERIES],
            "api": "Responses API for ALL scenarios",
            "s1": "Direct AOAI Responses API + streaming",
            "s2": "Foundry Agent V2 (no Bing) + Responses API + streaming",
            "s3": "Foundry Agent V2 + Bing + tool_choice=required + single-search instruction",
        },
        "results": all_results,
    }, open(outfile, "w"), indent=2)
    print(f"\nSaved: {outfile}")
    print("DONE.")


if __name__ == "__main__":
    main()
