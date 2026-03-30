#!/usr/bin/env python3
"""
Qira Model Migration: Bing Grounding (Web Search) Benchmark
============================================================
Uses Azure OpenAI Responses API with built-in web_search tool
to measure real Bing Grounding E2E latency across candidate models.

API: openai.responses.create() with tools=[{"type": "web_search"}]
Endpoint: /openai/v1/responses (Responses API, not Chat Completions)

Author: Xinyu Wei (魏新宇)
Date: 2026-03-23
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

from openai import OpenAI


# --- Configuration ---
AOAI_ENDPOINTS = {
    "eastus2": {
        "base_url": "https://<your-endpoint>.openai.azure.com/openai/v1/",
        "api_key_env": "AOAI_EASTUS2_KEY",
    },
}

MODELS = [
    {"deployment": "gpt-4o-mini",  "display": "gpt-4o-mini"},
    {"deployment": "gpt-5.4-mini", "display": "gpt-5.4-mini"},
    {"deployment": "gpt-5.4-nano", "display": "gpt-5.4-nano"},
]

# Qira Bing Grounding test scenarios
SCENARIOS = [
    {
        "id": "bing-1",
        "name": "Product Pricing (Lenovo ThinkPad)",
        "feature": "Pay Attention + Bing",
        "input": "What's the current price and availability of the Lenovo ThinkPad X1 Carbon Gen 13 in the US? Include any ongoing deals.",
        "max_tokens": 200,
    },
    {
        "id": "bing-2",
        "name": "Real-time News",
        "feature": "Catch Me Up + Bing",
        "input": "What are the top 3 technology news stories today? Give a brief summary of each.",
        "max_tokens": 300,
    },
    {
        "id": "bing-3",
        "name": "Weather Query",
        "feature": "Next Move + Bing",
        "input": "What's the current weather in Seattle and should I bring an umbrella today?",
        "max_tokens": 150,
    },
]


def run_single_test(client, model_deployment, scenario, stream=True):
    """Run a single Bing Grounding test and measure latency."""
    result = {
        "model": model_deployment,
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "stream": stream,
        "ttft_s": None,
        "e2e_s": None,
        "web_search_calls": 0,
        "citations": 0,
        "output_text": "",
        "search_queries": [],
        "citation_urls": [],
        "error": None,
    }

    try:
        t_start = time.perf_counter()

        if stream:
            response = client.responses.create(
                model=model_deployment,
                tools=[{"type": "web_search"}],
                input=scenario["input"],
                stream=True,
            )

            first_text = False
            full_text = ""
            for event in response:
                if not first_text and hasattr(event, 'type'):
                    if event.type == "response.output_text.delta":
                        result["ttft_s"] = round(time.perf_counter() - t_start, 3)
                        first_text = True
                        full_text += event.delta

                    elif event.type == "response.output_text.delta" and first_text:
                        full_text += event.delta

                    elif event.type == "response.output_item.done":
                        if hasattr(event, 'item'):
                            item = event.item
                            if hasattr(item, 'type'):
                                if item.type == "web_search_call":
                                    result["web_search_calls"] += 1
                                    if hasattr(item, 'action') and hasattr(item.action, 'query'):
                                        result["search_queries"].append(item.action.query)
                                elif item.type == "message":
                                    if hasattr(item, 'content') and item.content:
                                        for c in item.content:
                                            if hasattr(c, 'annotations'):
                                                for ann in c.annotations:
                                                    if hasattr(ann, 'type') and ann.type == "url_citation":
                                                        result["citations"] += 1
                                                        if hasattr(ann, 'url'):
                                                            result["citation_urls"].append(ann.url)

                    elif event.type == "response.completed":
                        if hasattr(event, 'response') and hasattr(event.response, 'output_text'):
                            full_text = event.response.output_text

            result["e2e_s"] = round(time.perf_counter() - t_start, 3)
            result["output_text"] = full_text[:500]  # Truncate for storage

        else:
            # Non-streaming mode
            response = client.responses.create(
                model=model_deployment,
                tools=[{"type": "web_search"}],
                input=scenario["input"],
            )
            result["e2e_s"] = round(time.perf_counter() - t_start, 3)

            # Parse response output
            if hasattr(response, 'output'):
                for item in response.output:
                    if hasattr(item, 'type'):
                        if item.type == "web_search_call":
                            result["web_search_calls"] += 1
                            if hasattr(item, 'action') and hasattr(item.action, 'query'):
                                result["search_queries"].append(item.action.query)
                        elif item.type == "message":
                            if hasattr(item, 'content'):
                                for c in item.content:
                                    if hasattr(c, 'text'):
                                        result["output_text"] = c.text[:500]
                                    if hasattr(c, 'annotations'):
                                        for ann in c.annotations:
                                            if hasattr(ann, 'type') and ann.type == "url_citation":
                                                result["citations"] += 1
                                                if hasattr(ann, 'url'):
                                                    result["citation_urls"].append(ann.url)

            if hasattr(response, 'output_text'):
                result["output_text"] = response.output_text[:500]

    except Exception as e:
        result["error"] = str(e)
        result["e2e_s"] = round(time.perf_counter() - t_start, 3)

    return result


def main():
    parser = argparse.ArgumentParser(description="Qira Bing Grounding Benchmark")
    parser.add_argument("--region", default="eastus2", help="Azure region")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations per scenario")
    parser.add_argument("--models", nargs="+", help="Model deployments to test")
    parser.add_argument("--stream", action="store_true", default=True, help="Use streaming")
    parser.add_argument("--no-stream", dest="stream", action="store_false", help="Disable streaming")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    args = parser.parse_args()

    region_config = AOAI_ENDPOINTS.get(args.region)
    if not region_config:
        print(f"ERROR: Unknown region '{args.region}'")
        sys.exit(1)

    # Get API key
    api_key = os.environ.get(region_config["api_key_env"])
    if not api_key:
        # Try hardcoded key for convenience (personal subscription only)
        api_key = os.environ.get("AOAI_KEY")
    if not api_key:
        print(f"ERROR: Set {region_config['api_key_env']} or AOAI_KEY environment variable")
        sys.exit(1)

    client = OpenAI(
        api_key=api_key,
        base_url=region_config["base_url"],
    )

    models_to_test = args.models or [m["deployment"] for m in MODELS]

    print(f"{'='*70}")
    print(f"Qira Bing Grounding Benchmark (Responses API + web_search)")
    print(f"{'='*70}")
    print(f"Region:     {args.region}")
    print(f"Endpoint:   {region_config['base_url']}")
    print(f"Models:     {', '.join(models_to_test)}")
    print(f"Scenarios:  {len(SCENARIOS)}")
    print(f"Iterations: {args.iterations}")
    print(f"Streaming:  {args.stream}")
    print(f"Timestamp:  {datetime.now().isoformat()}")
    print(f"{'='*70}\n")

    all_results = []

    for model_dep in models_to_test:
        display = next((m["display"] for m in MODELS if m["deployment"] == model_dep), model_dep)
        print(f"\n--- Model: {display} ({model_dep}) ---")

        for scenario in SCENARIOS:
            for i in range(args.iterations):
                print(f"  [{scenario['id']}] {scenario['name']} (iter {i+1}/{args.iterations})...", end=" ", flush=True)

                result = run_single_test(client, model_dep, scenario, stream=args.stream)
                result["iteration"] = i + 1
                result["region"] = args.region
                result["timestamp"] = datetime.now().isoformat()
                all_results.append(result)

                if result["error"]:
                    print(f"ERROR: {result['error'][:80]}")
                else:
                    ttft_str = f"TTFT={result['ttft_s']:.2f}s" if result["ttft_s"] else "TTFT=N/A"
                    print(f"{ttft_str} | E2E={result['e2e_s']:.2f}s | "
                          f"searches={result['web_search_calls']} | "
                          f"citations={result['citations']}")

                # Brief pause between requests
                time.sleep(1)

    # --- Summary ---
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Model':<16} {'Scenario':<30} {'Avg TTFT':>10} {'Avg E2E':>10} {'Searches':>10} {'Citations':>10}")
    print("-" * 86)

    for model_dep in models_to_test:
        display = next((m["display"] for m in MODELS if m["deployment"] == model_dep), model_dep)
        for scenario in SCENARIOS:
            runs = [r for r in all_results
                    if r["model"] == model_dep
                    and r["scenario_id"] == scenario["id"]
                    and r["error"] is None]
            if runs:
                avg_ttft = sum(r["ttft_s"] for r in runs if r["ttft_s"]) / max(1, len([r for r in runs if r["ttft_s"]]))
                avg_e2e = sum(r["e2e_s"] for r in runs) / len(runs)
                avg_searches = sum(r["web_search_calls"] for r in runs) / len(runs)
                avg_citations = sum(r["citations"] for r in runs) / len(runs)
                print(f"{display:<16} {scenario['name']:<30} {avg_ttft:>9.2f}s {avg_e2e:>9.2f}s {avg_searches:>10.1f} {avg_citations:>10.1f}")

    # --- Overall model averages ---
    print(f"\n{'Model':<16} {'Avg TTFT':>10} {'Avg E2E':>10} {'Avg Searches':>13} {'Avg Citations':>14}")
    print("-" * 63)
    for model_dep in models_to_test:
        display = next((m["display"] for m in MODELS if m["deployment"] == model_dep), model_dep)
        runs = [r for r in all_results if r["model"] == model_dep and r["error"] is None]
        if runs:
            ttft_runs = [r for r in runs if r["ttft_s"]]
            avg_ttft = sum(r["ttft_s"] for r in ttft_runs) / max(1, len(ttft_runs))
            avg_e2e = sum(r["e2e_s"] for r in runs) / len(runs)
            avg_searches = sum(r["web_search_calls"] for r in runs) / len(runs)
            avg_citations = sum(r["citations"] for r in runs) / len(runs)
            print(f"{display:<16} {avg_ttft:>9.2f}s {avg_e2e:>9.2f}s {avg_searches:>13.1f} {avg_citations:>14.1f}")

    # Save results
    output_data = {
        "benchmark": "Qira Bing Grounding (Responses API + web_search)",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "region": args.region,
            "endpoint": region_config["base_url"],
            "iterations": args.iterations,
            "streaming": args.stream,
            "models": models_to_test,
        },
        "results": all_results,
    }

    output_path = args.output or f"outputs/benchmark_bing_grounding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
