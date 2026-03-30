#!/usr/bin/env python3
"""
3-Scenario × 5-Model AOAI Benchmark (all streaming)

S1: Direct AOAI endpoint — Chat Completions API + streaming
S2: Foundry Agent V2 without Bing — Responses API + streaming
S3: Foundry Agent V2 with Bing — Responses API + streaming + BingGroundingTool

5 Models: gpt-4o-mini, gpt-5-mini, gpt-5-nano, gpt-5.4-mini, gpt-5.4-nano

Author: Xinyu Wei
"""

import time, json, os, sys
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

# Model definitions: (display_name, direct_deploy, foundry_deploy, reasoning_effort)
MODELS = [
    ("gpt-4o-mini",   "gpt-4o-mini",  "gpt-4o-mini",  None),
    ("gpt-5-mini",    "gpt-5-mini",   "gpt-5-mini",   "minimal"),
    ("gpt-5-nano",    "gpt-5-nano",   "gpt-5-nano",   "minimal"),
    ("gpt-5.4-mini",  "gpt-5.4-mini", "gpt-54-mini",  "none"),
    ("gpt-5.4-nano",  "gpt-5.4-nano", "gpt-54-nano",  "none"),
]

SYSTEM_MSG = "You are Qira, a helpful AI assistant. Answer concisely."
BING_INSTRUCTION = """You are Qira, a helpful AI assistant. Answer concisely.
CRITICAL: Perform exactly ONE search. Do NOT refine or repeat searches. Use first results immediately. Speed > completeness."""

QUERIES = [
    ("pricing", "What is the latest retail price for a ThinkPad X1 Carbon Gen 12?", 300),
    ("news",    "What are the top AI news stories this week?", 300),
    ("weather", "What is the current weather in Seattle, Washington?", 200),
]

ITERATIONS = 8       # per query per model
WARMUP = 2           # first N iterations discarded
SLEEP_BETWEEN = 0.3  # seconds between calls

# ── Helpers ─────────────────────────────────────────────────────────────

def run_s1_chat_completions(client, deploy, effort, query, max_tokens):
    """Scenario 1: Direct AOAI Chat Completions + Streaming"""
    extra = {}
    if effort:
        extra["extra_body"] = {"reasoning_effort": effort}

    t0 = time.perf_counter()
    ttft = None
    txt = ""

    stream = client.chat.completions.create(
        model=deploy,
        messages=[
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": query},
        ],
        max_completion_tokens=max_tokens,
        stream=True,
        **extra,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            if ttft is None:
                ttft = time.perf_counter() - t0
            txt += chunk.choices[0].delta.content
    e2e = time.perf_counter() - t0
    return ttft, e2e, len(txt)


def run_s2s3_foundry_agent(openai_client, agent_name, query, max_tokens, use_tool_choice=False):
    """Scenario 2 & 3: Foundry Agent V2 Responses API + Streaming"""
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
    for event in stream:
        if hasattr(event, "type") and event.type == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - t0
            txt += event.delta
    e2e = time.perf_counter() - t0
    return ttft, e2e, len(txt)


def print_summary(results, scenario_label):
    """Print aggregated summary for a scenario"""
    print(f"\n{'='*70}")
    print(f"  {scenario_label} — Summary (warmup={WARMUP} discarded)")
    print(f"{'='*70}")
    hdr = f"{'Model':14s} {'effort':>8} {'Avg TTFT':>9} {'P50':>7} {'Avg E2E':>9} {'N':>4}"
    print(hdr)
    print("-" * 55)

    for disp, _, _, eff in MODELS:
        rows = [r for r in results
                if r["model"] == disp and r.get("ttft") is not None and r["iter"] > WARMUP]
        if not rows:
            print(f"{disp:14s} {'N/A':>8} {'ERR':>9}")
            continue
        ts = sorted([r["ttft"] for r in rows])
        es = [r["e2e"] for r in rows]
        p50 = ts[len(ts) // 2]
        print(f"{disp:14s} {(eff or 'N/A'):>8} {sum(ts)/len(ts):>8.2f}s {p50:>6.2f}s {sum(es)/len(es):>8.2f}s {len(rows):>4}")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    all_results = []

    # ─── S1: Direct AOAI Chat Completions ───────────────────────────────
    print("\n" + "=" * 70)
    print("  S1: Direct AOAI Endpoint — Chat Completions + Streaming")
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
                    ttft, e2e, tlen = run_s1_chat_completions(direct_client, deploy, eff, query, maxt)
                    tag = "WU" if i <= WARMUP else "  "
                    tf = f"{ttft:.2f}" if ttft else "N/A"
                    print(f"  {tag} i{i} {disp:14s} TTFT={tf}s E2E={e2e:.2f}s len={tlen}")
                    rec = {"scenario": "S1_direct", "model": disp, "query": qid, "iter": i,
                           "ttft": round(ttft, 3) if ttft else None, "e2e": round(e2e, 3), "len": tlen}
                except Exception as ex:
                    print(f"  i{i} {disp:14s} ERR: {str(ex)[:80]}")
                    rec = {"scenario": "S1_direct", "model": disp, "query": qid, "iter": i,
                           "error": str(ex)[:200]}
                s1_results.append(rec)
                time.sleep(SLEEP_BETWEEN)

    print_summary(s1_results, "S1: Direct AOAI (no Bing)")
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

    # Create agents for all 5 models (no Bing tools)
    s2_agents = {}
    for disp, _, fdeploy, eff in MODELS:
        short = fdeploy.replace('gpt-', 'g')
        agent_name = f"s2-{short}-{ts}"
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
        print(f"  Created S2 agent: {agent.name} (model={fdeploy}, effort={eff})")

    s2_results = []
    for qid, query, maxt in QUERIES:
        print(f"\n  [{qid}] max_tokens={maxt}")
        for i in range(1, ITERATIONS + 1):
            for disp, _, _, eff in MODELS:
                agent = s2_agents[disp]
                try:
                    ttft, e2e, tlen = run_s2s3_foundry_agent(openai_client, agent.name, query, maxt)
                    tag = "WU" if i <= WARMUP else "  "
                    tf = f"{ttft:.2f}" if ttft else "N/A"
                    print(f"  {tag} i{i} {disp:14s} TTFT={tf}s E2E={e2e:.2f}s len={tlen}")
                    rec = {"scenario": "S2_foundry_no_bing", "model": disp, "query": qid, "iter": i,
                           "ttft": round(ttft, 3) if ttft else None, "e2e": round(e2e, 3), "len": tlen}
                except Exception as ex:
                    print(f"  i{i} {disp:14s} ERR: {str(ex)[:80]}")
                    rec = {"scenario": "S2_foundry_no_bing", "model": disp, "query": qid, "iter": i,
                           "error": str(ex)[:200]}
                s2_results.append(rec)
                time.sleep(SLEEP_BETWEEN)

    print_summary(s2_results, "S2: Foundry Agent V2 (no Bing)")
    all_results.extend(s2_results)

    # Cleanup S2 agents
    for disp, agent in s2_agents.items():
        try:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        except Exception:
            pass

    # ─── S3: Foundry Agent V2, WITH Bing ────────────────────────────────
    print("\n" + "=" * 70)
    print("  S3: Foundry Agent V2 — WITH Bing — Responses API + Streaming")
    print("=" * 70)

    # Create agents for all 5 models (with Bing tool)
    s3_agents = {}
    for disp, _, fdeploy, eff in MODELS:
        short = fdeploy.replace('gpt-', 'g')
        agent_name = f"s3-{short}-{ts}"
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
        print(f"  Created S3 agent: {agent.name} (model={fdeploy}, effort={eff})")

    s3_results = []
    for qid, query, maxt in QUERIES:
        print(f"\n  [{qid}] max_tokens={maxt}")
        for i in range(1, ITERATIONS + 1):
            for disp, _, _, eff in MODELS:
                agent = s3_agents[disp]
                try:
                    ttft, e2e, tlen = run_s2s3_foundry_agent(openai_client, agent.name, query, maxt, use_tool_choice=True)
                    tag = "WU" if i <= WARMUP else "  "
                    tf = f"{ttft:.2f}" if ttft else "N/A"
                    print(f"  {tag} i{i} {disp:14s} TTFT={tf}s E2E={e2e:.2f}s len={tlen}")
                    rec = {"scenario": "S3_foundry_bing", "model": disp, "query": qid, "iter": i,
                           "ttft": round(ttft, 3) if ttft else None, "e2e": round(e2e, 3), "len": tlen}
                except Exception as ex:
                    print(f"  i{i} {disp:14s} ERR: {str(ex)[:80]}")
                    rec = {"scenario": "S3_foundry_bing", "model": disp, "query": qid, "iter": i,
                           "error": str(ex)[:200]}
                s3_results.append(rec)
                time.sleep(SLEEP_BETWEEN)

    print_summary(s3_results, "S3: Foundry Agent V2 (with Bing)")
    all_results.extend(s3_results)

    # Cleanup S3 agents
    for disp, agent in s3_agents.items():
        try:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        except Exception:
            pass

    # ─── Grand Summary ──────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("  GRAND SUMMARY — 3 Scenarios × 5 Models (warmup discarded)")
    print("=" * 80)
    hdr = f"{'Model':14s} {'S1 TTFT':>9} {'S1 E2E':>9} {'S2 TTFT':>9} {'S2 E2E':>9} {'S3 TTFT':>9} {'S3 E2E':>9}"
    print(hdr)
    print("-" * 80)

    for disp, _, _, eff in MODELS:
        vals = []
        for sc in ["S1_direct", "S2_foundry_no_bing", "S3_foundry_bing"]:
            rows = [r for r in all_results
                    if r["scenario"] == sc and r["model"] == disp
                    and r.get("ttft") is not None and r["iter"] > WARMUP]
            if rows:
                avg_ttft = sum(r["ttft"] for r in rows) / len(rows)
                avg_e2e = sum(r["e2e"] for r in rows) / len(rows)
                vals.append(f"{avg_ttft:.2f}s")
                vals.append(f"{avg_e2e:.2f}s")
            else:
                vals.append("ERR")
                vals.append("ERR")
        print(f"{disp:14s} {vals[0]:>9} {vals[1]:>9} {vals[2]:>9} {vals[3]:>9} {vals[4]:>9} {vals[5]:>9}")

    # ─── Save ───────────────────────────────────────────────────────────
    outfile = f"outputs/benchmark_3scenarios_{ts.replace('-','_')}.json"
    json.dump({
        "benchmark": "3-scenario × 5-model comparison",
        "timestamp": ts,
        "scenarios": {
            "S1": "Direct AOAI Chat Completions + Streaming",
            "S2": "Foundry Agent V2 (no Bing) + Streaming",
            "S3": "Foundry Agent V2 (with Bing) + Streaming",
        },
        "config": {
            "iterations": ITERATIONS,
            "warmup": WARMUP,
            "queries": [q[0] for q in QUERIES],
            "direct_endpoint": AOAI_ENDPOINT,
            "foundry_endpoint": FOUNDRY_ENDPOINT,
        },
        "results": all_results,
    }, open(outfile, "w"), indent=2)
    print(f"\nSaved: {outfile}")
    print("DONE.")


if __name__ == "__main__":
    main()
