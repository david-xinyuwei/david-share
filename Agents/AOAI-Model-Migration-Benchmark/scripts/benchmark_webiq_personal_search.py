#!/usr/bin/env python3
"""
WebIQ personal-search benchmark for AI assistant scenarios.
========================================================================
Adds Microsoft Web IQ as an explicit grounding option alongside the existing
Responses API web_search_preview and Foundry+Bing benchmarks.

Two modes:
  - search: WebIQ search only, validating retrieval latency and result quality.
  - e2e: WebIQ search + AOAI Responses API generation, measuring user-visible
    total TTFT from the start of search to the model's first output token.

The default scenarios are AI-assistant/personal-search scenarios, not generic
search smoke tests. For customer-private scenarios, pass --scenario-file with a
local JSON file and do not commit that file.

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
from urllib.parse import urlparse

import numpy as np
from webiq import ApiKeyAuth, WebIQClient

try:
    from openai import AzureOpenAI
except ImportError:  # search-only mode can run without openai installed
    AzureOpenAI = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from benchmark_websearch_guardrails import GUARDRAILS, MODELS as BASE_MODELS
except ImportError as exc:
    raise SystemExit(
        "benchmark_websearch_guardrails.py is required because this benchmark "
        "reuses its GUARDRAILS prompt and model metadata. Run from the repo root "
        "or keep both scripts in the same scripts/ directory."
    ) from exc

SEARCH_SYSTEM_MSG = (
    "You are a helpful AI assistant. Answer concisely using only the provided "
    "WebIQ search context. Include source URLs from the context for factual claims.\n"
    + GUARDRAILS
)

DEFAULT_MODELS = [
    ("gpt-4o-mini", "gpt-4o-mini", None),
    ("gpt-5.4-nano", "gpt-5.4-nano", "none"),
    ("gpt-5.4-mini", "gpt-5.4-mini", "none"),
]


@dataclass(frozen=True)
class Scenario:
    name: str
    query: str
    max_output_tokens: int
    required_terms: tuple[str, ...]
    min_results: int = 3


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WebIQ benchmark for AI assistant personal-search scenarios"
    )
    parser.add_argument(
        "--webiq-key",
        default=os.environ.get("WEBIQ_API_KEY", ""),
        help="WebIQ API key. Prefer WEBIQ_API_KEY; do not commit keys.",
    )
    parser.add_argument(
        "--mode",
        choices=("search", "e2e"),
        default="search",
        help="search=WebIQ only; e2e=WebIQ + AOAI generation",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        help="Azure OpenAI endpoint, required for --mode e2e",
    )
    parser.add_argument(
        "--api-key",
        dest="aoai_api_key",
        default=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        help="Azure OpenAI API key, required for --mode e2e",
    )
    parser.add_argument("--api-version", default="2025-04-01-preview")
    parser.add_argument(
        "--models",
        default="gpt-4o-mini,gpt-5.4-nano,gpt-5.4-mini",
        help="Comma-separated model display names to run in e2e mode",
    )
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument(
        "--scenario-file",
        default="",
        help=(
            "Optional local JSON list of scenarios. Fields: name, query, "
            "max_output_tokens, required_terms, min_results. Do not commit private files."
        ),
    )
    parser.add_argument("--output-dir", default="outputs")
    return parser.parse_args()


def load_scenarios(path: str) -> list[Scenario]:
    if not path:
        return DEFAULT_SCENARIOS
    with open(path, "r", encoding="utf-8") as scenario_file:
        raw_scenarios = json.load(scenario_file)
    scenarios: list[Scenario] = []
    for raw_scenario in raw_scenarios:
        scenarios.append(
            Scenario(
                name=raw_scenario["name"],
                query=raw_scenario["query"],
                max_output_tokens=int(raw_scenario.get("max_output_tokens", 300)),
                required_terms=tuple(raw_scenario.get("required_terms", [])),
                min_results=int(raw_scenario.get("min_results", 3)),
            )
        )
    return scenarios


def selected_models(model_names: str) -> list[tuple[str, str, str | None]]:
    requested = [model_name.strip() for model_name in model_names.split(",") if model_name.strip()]
    known_models = {
        display_name: (display_name, deployment_name, websearch_effort)
        for display_name, deployment_name, _direct_effort, websearch_effort in BASE_MODELS
    }
    for display_name, deployment_name, effort in DEFAULT_MODELS:
        known_models.setdefault(display_name, (display_name, deployment_name, effort))
    selected = []
    for model_name in requested:
        if model_name not in known_models:
            print(f"WARNING: unknown model '{model_name}', skipping")
            continue
        selected.append(known_models[model_name])
    return selected


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def webiq_search(client: WebIQClient, scenario: Scenario, max_results: int) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.web.search(query=scenario.query, max_results=max_results)
    latency = time.perf_counter() - started

    web_results = getattr(response, "webResults", []) or []
    result_records = []
    combined_text_parts = []
    for index, web_result in enumerate(web_results, 1):
        title = getattr(web_result, "title", "") or ""
        url = getattr(web_result, "url", "") or ""
        content = getattr(web_result, "content", "") or ""
        plain_content = strip_html(content)
        combined_text_parts.extend((title, plain_content, url))
        result_records.append(
            {
                "rank": index,
                "title": title,
                "url": url,
                "domain": domain_from_url(url),
                "content_chars": len(content),
                "plain_preview": plain_content[:500],
            }
        )

    combined_text = "\n".join(combined_text_parts).lower()
    matched_terms = [term for term in scenario.required_terms if term.lower() in combined_text]
    quality_pass = len(web_results) >= scenario.min_results and len(matched_terms) == len(scenario.required_terms)

    return {
        "latency": latency,
        "n_results": len(web_results),
        "matched_terms": matched_terms,
        "quality_pass": quality_pass,
        "results": result_records,
    }


def context_from_results(result_records: list[dict[str, Any]], max_chars_per_result: int = 1600) -> str:
    context_parts = []
    for result_record in result_records:
        context_parts.append(
            "[{rank}] {title}\nURL: {url}\n{preview}".format(
                rank=result_record["rank"],
                title=result_record["title"],
                url=result_record["url"],
                preview=result_record["plain_preview"][:max_chars_per_result],
            )
        )
    return "\n\n".join(context_parts)


def response_mentions_source(response_text: str, result_records: list[dict[str, Any]]) -> bool:
    lowered_response = response_text.lower()
    for result_record in result_records:
        url = result_record.get("url", "")
        domain = result_record.get("domain", "")
        if url and url.lower() in lowered_response:
            return True
        if domain and domain in lowered_response:
            return True
    return False


def run_model_with_webiq_context(
    aoai_client: Any,
    model_name: str,
    deployment_name: str,
    reasoning_effort: str | None,
    scenario: Scenario,
    search_record: dict[str, Any],
) -> dict[str, Any]:
    context = context_from_results(search_record["results"])
    user_message = (
        "Use the WebIQ search context below to answer the user question. "
        "Cite source URLs from the context. If the context is insufficient, say so.\n\n"
        f"--- WEBIQ CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
        f"Question: {scenario.query}"
    )
    kwargs: dict[str, Any] = {
        "model": deployment_name,
        "stream": True,
        "input": [
            {"role": "system", "content": SEARCH_SYSTEM_MSG},
            {"role": "user", "content": user_message},
        ],
        "max_output_tokens": scenario.max_output_tokens,
    }
    if reasoning_effort:
        kwargs["reasoning"] = {"effort": reasoning_effort}

    started = time.perf_counter()
    first_token_latency = None
    response_parts = []
    stream = aoai_client.responses.create(**kwargs)
    for event in stream:
        if getattr(event, "type", "") == "response.output_text.delta":
            if first_token_latency is None:
                first_token_latency = time.perf_counter() - started
            response_parts.append(event.delta)
    e2e_latency = time.perf_counter() - started
    if first_token_latency is None:
        first_token_latency = e2e_latency
    response_text = "".join(response_parts)
    return {
        "model": model_name,
        "model_ttft": first_token_latency,
        "model_e2e": e2e_latency,
        "response_len": len(response_text),
        "source_used": response_mentions_source(response_text, search_record["results"]),
        "response_preview": response_text[:800],
    }


def summarize(records: list[dict[str, Any]], mode: str, model_names: list[str]) -> None:
    print("\n" + "=" * 80)
    print("SUMMARY (warmup discarded)")
    print("=" * 80)
    search_latencies = [record["search_latency"] for record in records if not record["warmup"] and record["success"]]
    if search_latencies:
        search_array = np.array(search_latencies)
        quality_passes = sum(1 for record in records if not record["warmup"] and record.get("retrieval_quality_pass"))
        print(
            "WebIQ search: P50={:.0f}ms P95={:.0f}ms N={} quality_pass={}/{}".format(
                np.percentile(search_array, 50) * 1000,
                np.percentile(search_array, 95) * 1000,
                len(search_array),
                quality_passes,
                len(search_array),
            )
        )
    if mode != "e2e":
        return
    for model_name in model_names:
        model_records = [
            record
            for record in records
            if not record["warmup"] and record.get("success") and record.get("model") == model_name
        ]
        if not model_records:
            continue
        total_array = np.array([record["total_ttft"] for record in model_records])
        model_array = np.array([record["model_ttft"] for record in model_records])
        source_used = sum(1 for record in model_records if record.get("source_used"))
        print(
            "{}: total P50={:.0f}ms model P50={:.0f}ms source_used={}/{}".format(
                model_name,
                np.percentile(total_array, 50) * 1000,
                np.percentile(model_array, 50) * 1000,
                source_used,
                len(model_records),
            )
        )


def main() -> None:
    args = parse_args()
    if not args.webiq_key:
        raise SystemExit("Set WEBIQ_API_KEY or pass --webiq-key. Do not hardcode keys.")
    if args.mode == "e2e" and (not args.endpoint or not args.aoai_api_key):
        raise SystemExit("E2E mode requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")
    if args.mode == "e2e" and AzureOpenAI is None:
        raise SystemExit("E2E mode requires the openai package.")

    scenarios = load_scenarios(args.scenario_file)
    models = selected_models(args.models) if args.mode == "e2e" else []
    model_names = [model_tuple[0] for model_tuple in models]

    webiq_client = WebIQClient(auth=ApiKeyAuth(api_key=args.webiq_key))
    aoai_client = None
    if args.mode == "e2e":
        aoai_client = AzureOpenAI(
            api_key=args.aoai_api_key,
            azure_endpoint=args.endpoint,
            api_version=args.api_version,
        )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    records: list[dict[str, Any]] = []
    print("=" * 80)
    print("WebIQ personal-search benchmark")
    print(f"mode={args.mode} scenarios={len(scenarios)} iterations={args.iterations} warmup={args.warmup}")
    print(f"max_results={args.max_results}")
    if model_names:
        print(f"models={model_names}")
    print("=" * 80)

    for scenario in scenarios:
        print(f"\n[{scenario.name}] {scenario.query}")
        for iteration in range(1, args.iterations + 1):
            warmup = iteration <= args.warmup
            prefix = "WU" if warmup else "  "
            try:
                search_record = webiq_search(webiq_client, scenario, args.max_results)
                base_record = {
                    "scenario": scenario.name,
                    "query": scenario.query,
                    "iteration": iteration,
                    "warmup": warmup,
                    "success": True,
                    "search_latency": round(search_record["latency"], 4),
                    "n_results": search_record["n_results"],
                    "matched_terms": search_record["matched_terms"],
                    "retrieval_quality_pass": search_record["quality_pass"],
                    "top_results": search_record["results"][:3],
                }
                if args.mode == "search":
                    records.append(base_record)
                    print(
                        "  {} i{:02d} Search={:.0f}ms results={} quality={}".format(
                            prefix,
                            iteration,
                            search_record["latency"] * 1000,
                            search_record["n_results"],
                            "PASS" if search_record["quality_pass"] else "FAIL",
                        )
                    )
                else:
                    for model_name, deployment_name, reasoning_effort in models:
                        model_record = run_model_with_webiq_context(
                            aoai_client,
                            model_name,
                            deployment_name,
                            reasoning_effort,
                            scenario,
                            search_record,
                        )
                        total_ttft = search_record["latency"] + model_record["model_ttft"]
                        full_record = {
                            **base_record,
                            **model_record,
                            "total_ttft": round(total_ttft, 4),
                        }
                        records.append(full_record)
                        print(
                            "  {} i{:02d} {:15s} Search={:.0f}ms Model={:.0f}ms Total={:.0f}ms quality={} source={}".format(
                                prefix,
                                iteration,
                                model_name,
                                search_record["latency"] * 1000,
                                model_record["model_ttft"] * 1000,
                                total_ttft * 1000,
                                "PASS" if search_record["quality_pass"] else "FAIL",
                                "YES" if model_record["source_used"] else "NO",
                            )
                        )
                        time.sleep(args.sleep)
                time.sleep(args.sleep)
            except Exception as exc:
                records.append(
                    {
                        "scenario": scenario.name,
                        "query": scenario.query,
                        "iteration": iteration,
                        "warmup": warmup,
                        "success": False,
                        "error": str(exc)[:1000],
                    }
                )
                print(f"  {prefix} i{iteration:02d} ERROR: {str(exc)[:120]}")
                time.sleep(args.sleep)

    summarize(records, args.mode, model_names)

    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, f"benchmark_webiq_personal_search_{args.mode}_{timestamp}.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(
            {
                "benchmark": "webiq_personal_search",
                "timestamp": timestamp,
                "mode": args.mode,
                "config": {
                    "webiq_max_results": args.max_results,
                    "iterations": args.iterations,
                    "warmup": args.warmup,
                    "scenario_file": args.scenario_file or None,
                    "models": model_names,
                    "api_version": args.api_version if args.mode == "e2e" else None,
                },
                "records": records,
            },
            output_file,
            indent=2,
        )
    print(f"\nSaved: {output_path}")
    print("DONE.")


if __name__ == "__main__":
    main()
