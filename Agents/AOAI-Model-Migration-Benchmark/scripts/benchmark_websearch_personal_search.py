#!/usr/bin/env python3
"""
web_search_preview benchmark with personal-search scenarios & quality oracle.
========================================================================
Fair-comparison counterpart to benchmark_webiq_personal_search.py.

Uses the Responses API built-in `web_search_preview` tool (same architecture
as benchmark_websearch_guardrails.py) but:
  - Accepts the same scenario file / default scenarios as the WebIQ script
  - Records quality_pass (required_terms in response) and source_used (URL citation)
  - Selectable model list via --models
  - Same iteration/warmup/output structure for direct JSON merge

Author: Xinyu Wei (魏新宇)
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from openai import AzureOpenAI

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from benchmark_websearch_guardrails import GUARDRAILS
except ImportError as exc:
    raise SystemExit(
        "benchmark_websearch_guardrails.py is required because this benchmark "
        "reuses its GUARDRAILS prompt. Run from the repo root or keep both "
        "scripts in the same scripts/ directory."
    ) from exc

SEARCH_SYSTEM_MSG = (
    "You are a helpful AI assistant. Answer concisely. "
    "Search the web for current information. Cite source URLs.\n" + GUARDRAILS
)


@dataclass(frozen=True)
class Scenario:
    name: str
    query: str
    max_output_tokens: int
    required_terms: tuple[str, ...]
    min_results: int = 1  # web_search_preview doesn't expose result count


DEFAULT_SCENARIOS = [
    Scenario(
        name="ai_pc_product_search",
        query=(
            "Find current public information about Lenovo AI PC flagship products, "
            "including product names, availability, and source links."
        ),
        max_output_tokens=300,
        required_terms=("lenovo", "ai", "pc"),
    ),
    Scenario(
        name="agent_framework_research",
        query=(
            "Find recent public information about AI agent frameworks for personal "
            "assistants, including LangGraph, OpenAI Agents SDK, and Microsoft "
            "Foundry Agent Service."
        ),
        max_output_tokens=350,
        required_terms=("agent", "framework"),
    ),
    Scenario(
        name="web_grounding_comparison",
        query=(
            "Find public information about Microsoft Web IQ, Grounding with Bing, "
            "and web search grounding for AI agents."
        ),
        max_output_tokens=350,
        required_terms=("web", "grounding"),
    ),
    Scenario(
        name="current_weather_personal_assistant",
        query="What is the current weather in Seattle, Washington? Include source links.",
        max_output_tokens=200,
        required_terms=("seattle", "weather"),
    ),
]

DEFAULT_MODELS = [
    # (display_name, deployment_name, reasoning_effort)
    ("gpt-4o-mini", "gpt-4o-mini", None),
    ("gpt-5.4-nano", "gpt-5.4-nano", "none"),
    ("gpt-5.4-mini", "gpt-5.4-mini", "none"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="web_search_preview benchmark with personal-search scenarios"
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        help="Azure OpenAI endpoint URL",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        help="Azure OpenAI API key",
    )
    parser.add_argument("--api-version", default="2025-04-01-preview")
    parser.add_argument(
        "--models",
        default="gpt-4o-mini,gpt-5.4-nano,gpt-5.4-mini",
        help="Comma-separated model display names",
    )
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument(
        "--scenario-file",
        default="",
        help="Optional JSON scenario list (same format as WebIQ script).",
    )
    parser.add_argument("--output-dir", default="outputs")
    return parser.parse_args()


def load_scenarios(path: str) -> list[Scenario]:
    if not path:
        return DEFAULT_SCENARIOS
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [
        Scenario(
            name=s["name"],
            query=s["query"],
            max_output_tokens=int(s.get("max_output_tokens", 300)),
            required_terms=tuple(s.get("required_terms", [])),
            min_results=int(s.get("min_results", 1)),
        )
        for s in raw
    ]


def selected_models(model_names: str) -> list[tuple[str, str, str | None]]:
    known = {m[0]: m for m in DEFAULT_MODELS}
    selected = []
    for name in model_names.split(","):
        name = name.strip()
        if name in known:
            selected.append(known[name])
        else:
            print(f"WARNING: unknown model '{name}', skipping")
    return selected


def run_websearch(client: AzureOpenAI, deploy: str, effort: str | None,
                  scenario: Scenario) -> dict[str, Any]:
    """Run Responses API with web_search_preview, measure TTFT and quality."""
    t0 = time.perf_counter()
    ttft = None
    txt = ""
    searched = False

    kwargs: dict[str, Any] = {
        "model": deploy,
        "stream": True,
        "tools": [{"type": "web_search_preview", "search_context_size": "low"}],
        "input": [
            {"role": "system", "content": SEARCH_SYSTEM_MSG},
            {"role": "user", "content": scenario.query},
        ],
        "max_output_tokens": scenario.max_output_tokens,
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

    # Quality checks
    lowered = txt.lower()
    matched_terms = [t for t in scenario.required_terms if t.lower() in lowered]
    quality_pass = len(matched_terms) == len(scenario.required_terms) and searched

    # Source/citation check: look for URLs in the response
    url_pattern = re.compile(r"https?://[^\s\)\]\"']+")
    urls_found = url_pattern.findall(txt)
    source_used = len(urls_found) > 0

    return {
        "ttft": round(ttft, 4),
        "e2e": round(e2e, 4),
        "searched": searched,
        "response_len": len(txt),
        "matched_terms": matched_terms,
        "quality_pass": quality_pass,
        "source_used": source_used,
        "citation_count": len(urls_found),
        "response_preview": txt[:800],
    }


def main() -> None:
    args = parse_args()
    if not args.endpoint or not args.api_key:
        raise SystemExit("Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")

    scenarios = load_scenarios(args.scenario_file)
    models = selected_models(args.models)

    client = AzureOpenAI(
        api_key=args.api_key,
        azure_endpoint=args.endpoint,
        api_version=args.api_version,
    )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    records: list[dict[str, Any]] = []

    print("=" * 80)
    print("web_search_preview benchmark (personal-search scenarios)")
    print(f"scenarios={len(scenarios)} models={[m[0] for m in models]}")
    print(f"iterations={args.iterations} warmup={args.warmup}")
    print(f"endpoint={args.endpoint}")
    print("=" * 80)

    for scenario in scenarios:
        print(f"\n[{scenario.name}] {scenario.query[:60]}...")
        for iteration in range(1, args.iterations + 1):
            warmup = iteration <= args.warmup
            prefix = "WU" if warmup else "  "

            for name, deploy, effort in models:
                try:
                    r = run_websearch(client, deploy, effort, scenario)
                    records.append({
                        "scenario": scenario.name,
                        "model": name,
                        "query": scenario.query,
                        "iteration": iteration,
                        "warmup": warmup,
                        "success": True,
                        "total_ttft": r["ttft"],
                        "e2e": r["e2e"],
                        "searched": r["searched"],
                        "response_len": r["response_len"],
                        "matched_terms": r["matched_terms"],
                        "quality_pass": r["quality_pass"],
                        "source_used": r["source_used"],
                        "citation_count": r["citation_count"],
                        "response_preview": r["response_preview"],
                    })
                    q_tag = "PASS" if r["quality_pass"] else "FAIL"
                    s_tag = "YES" if r["source_used"] else "NO"
                    print(
                        f"  {prefix} i{iteration:02d} {name:15s} "
                        f"TTFT={r['ttft']*1000:.0f}ms "
                        f"quality={q_tag} source={s_tag} "
                        f"{'🔍' if r['searched'] else '⚠️NS'}"
                    )
                except Exception as exc:
                    records.append({
                        "scenario": scenario.name,
                        "model": name,
                        "query": scenario.query,
                        "iteration": iteration,
                        "warmup": warmup,
                        "success": False,
                        "error": str(exc)[:1000],
                    })
                    print(f"  {prefix} i{iteration:02d} {name:15s} ERROR: {str(exc)[:100]}")
                time.sleep(args.sleep)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY — web_search_preview (warmup discarded)")
    print("=" * 80)
    model_names = [m[0] for m in models]
    for name in model_names:
        recs = [r for r in records if r["model"] == name and not r["warmup"] and r.get("success")]
        if not recs:
            continue
        arr = np.array([r["total_ttft"] for r in recs])
        quality_count = sum(1 for r in recs if r["quality_pass"])
        source_count = sum(1 for r in recs if r["source_used"])
        print(
            f"  {name:15s}: P50={np.percentile(arr,50)*1000:.0f}ms "
            f"P95={np.percentile(arr,95)*1000:.0f}ms "
            f"σ={np.std(arr)*1000:.0f}ms N={len(arr)} "
            f"quality={quality_count}/{len(arr)} source={source_count}/{len(arr)}"
        )

    # Save
    os.makedirs(args.output_dir, exist_ok=True)
    outfile = os.path.join(args.output_dir, f"benchmark_websearch_personal_search_{timestamp}.json")
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump({
            "benchmark": "websearch_preview_personal_search",
            "timestamp": timestamp,
            "config": {
                "endpoint": args.endpoint,
                "api_version": args.api_version,
                "tool": "web_search_preview",
                "search_context_size": "low",
                "system_prompt": "GUARDRAILS (~1066 tokens)",
                "iterations": args.iterations,
                "warmup": args.warmup,
                "models": model_names,
                "scenario_file": args.scenario_file or None,
            },
            "records": records,
        }, f, indent=2)
    print(f"\nSaved: {outfile}")
    print("DONE.")


if __name__ == "__main__":
    main()
