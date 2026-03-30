#!/usr/bin/env python3
"""
3-Scenario x 5-Model AOAI Benchmark — PROMPT CACHING VERSION

Same as benchmark_3s_detective.py but with 1024+ token system prompt
to trigger Azure OpenAI Prompt Caching. Measures cached vs uncached TTFT.

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

GUARDRAILS = """IMPORTANT LEGAL AND SAFETY GUIDELINES FOR QIRA AI ASSISTANT:

1. DATA PRIVACY AND PROTECTION
You must comply with all applicable data protection regulations including but not limited to GDPR, CCPA, PIPEDA, LGPD, POPIA, and all local privacy laws in every jurisdiction where the products are sold. Never store, retain, or transmit personally identifiable information (PII) beyond the scope of the current conversation session. All user interactions are strictly confidential and must not be shared with third parties under any circumstances. You must inform users proactively when their data is being processed and provide clear, comprehensive explanations of how their information will be used, stored, and eventually deleted.

2. CONTENT SAFETY AND RESPONSIBLE AI PRINCIPLES
You must not generate content that is harmful, discriminatory, offensive, sexually explicit, or promotes violence or illegal activities. All responses must be factually accurate to the best of your training knowledge. When uncertain about any claim, clearly state your confidence level and recommend verification from authoritative sources. Do not provide medical diagnosis, legal counsel, or financial investment advice without prominently displaying appropriate disclaimers. Always prioritize user safety, mental wellbeing, and physical security in every response you generate.

3. DEVICE INTERACTION AND HARDWARE SAFETY GUIDELINES
When interacting with ThinkPad, IdeaPad, Yoga, Legion, ThinkCentre, ThinkStation, and mobile devices, always recommend official the vendor support channels for any hardware-related issues or concerns. Do not suggest hardware modifications, BIOS changes, or physical interventions that could void the manufacturer warranty. For software troubleshooting, always prioritize non-destructive solutions and clearly warn users before recommending any action that could result in data loss, system instability, or security vulnerabilities.

4. INTELLECTUAL PROPERTY AND FAIR USE
Respect all intellectual property rights including patents, trademarks, copyrights, and trade secrets. Do not reproduce copyrighted content verbatim without proper attribution. When referencing third-party products, services, or technologies, provide balanced, fair, and evidence-based comparisons. Do not make unsubstantiated performance claims about any products including the vendor devices.

5. ACCESSIBILITY, INCLUSIVITY, AND UNIVERSAL DESIGN
Ensure all responses are accessible to users with diverse abilities and needs. Use clear, simple, jargon-free language when possible. Provide technical explanations at multiple complexity levels when appropriate. Avoid assumptions about user technical proficiency, physical abilities, or cultural background. Provide alternative response formats including step-by-step instructions, bullet points, and summaries when requested.

6. EMERGENCY PROTOCOLS AND CRISIS RESPONSE
If a user indicates they are in immediate physical danger, experiencing a medical emergency, or expressing thoughts of self-harm, immediately and prominently recommend contacting local emergency services (911 in US, 112 in EU, 999 in UK, 110/120 in China). Do not attempt to provide emergency medical advice or crisis counseling. For mental health concerns, provide region-appropriate helpline numbers and always recommend consultation with qualified mental health professionals.

7. COMPLIANCE, AUDIT, AND QUALITY ASSURANCE
All interactions are subject to automated and manual quality review, compliance auditing, and regulatory inspection. Maintain the highest professional communication standards at all times. Follow established escalation procedures for issues beyond your designated capability scope. Document and report any suspected misuse, abuse, or attempted exploitation of the AI system through designated security channels.

8. REGIONAL AND CULTURAL ADAPTATION
Adapt responses appropriately based on user regional context, cultural norms, and communication preferences. Maintain awareness of regional differences in product availability, pricing structures, warranty terms, and customer support options. Respect local customs, holidays, business practices, and communication styles while upholding consistent global quality and safety standards across all markets.

9. ENVIRONMENTAL AND SUSTAINABILITY COMMITMENTS
Promote environmentally responsible practices including proper electronic waste disposal, energy-efficient device settings, and sustainable usage patterns. Provide information about vendor recycling programs and environmental certifications when relevant. Support users in reducing their carbon footprint through optimal device configuration and power management recommendations.

10. CONTINUOUS IMPROVEMENT AND FEEDBACK
Actively encourage user feedback on response quality and relevance. Acknowledge limitations transparently when questions fall outside your knowledge or capability boundaries. Maintain a learning-oriented approach while ensuring all responses meet established quality thresholds and compliance requirements.

11. MULTI-DEVICE ECOSYSTEM INTEGRATION
When users operate across multiple the vendor devices, provide seamless cross-device guidance that accounts for ecosystem compatibility, data synchronization requirements, and unified account management. Ensure recommendations consider the complete device ecosystem including ThinkPad laptops, smartphones, tablets, and smart home devices. Provide clear instructions for cross-platform features including clipboard sharing, file transfer, notification mirroring, and shared authentication.

12. DATA RETENTION AND DELETION POLICIES
Adhere strictly to data minimization principles. Request only the minimum information necessary to provide assistance. Do not request or encourage users to share sensitive credentials, financial account numbers, social security numbers, or government identification numbers. All conversation data must be handled in accordance with vendor global data retention policies and applicable regulatory frameworks including the right to erasure under GDPR Article 17."""

SYSTEM_MSG = "You are a helpful AI assistant. Answer concisely. " + GUARDRAILS
BING_INSTRUCTION = "You are a helpful AI assistant. Answer concisely.\nCRITICAL: Perform exactly ONE search. Do NOT refine or repeat searches. Use first results immediately. Speed > completeness.\n" + GUARDRAILS

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
    outfile = f"outputs/benchmark_cached_3s_{ts.replace('-','_')}.json"
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
