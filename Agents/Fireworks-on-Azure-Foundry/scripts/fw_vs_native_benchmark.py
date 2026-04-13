#!/usr/bin/env python3
"""
Fireworks vs Native Inference Benchmark on Azure Foundry
Compare FW-Kimi-K2.5 (Fireworks engine) vs Kimi-K2.5 (Azure native) performance.

Author: Xinyu Wei
Usage:
    python3 fw_vs_native_benchmark.py \
        --endpoint "https://your-resource.cognitiveservices.azure.com/" \
        --api-key "YOUR_API_KEY" \
        --iterations 5 \
        --output results.json
"""

import argparse
import json
import os
import time
import statistics
from openai import AzureOpenAI


TEST_PROMPTS = [
    {"role": "user", "content": "Explain the concept of attention mechanism in transformers in 3 sentences."},
    {"role": "user", "content": "Write a Python function to calculate fibonacci numbers using dynamic programming."},
    {"role": "user", "content": "What are the key differences between TCP and UDP protocols?"},
    {"role": "user", "content": "Summarize the main ideas of reinforcement learning in 5 bullet points."},
    {"role": "user", "content": "Explain how a database index works and when to use composite indexes."},
]

DEPLOYMENTS = {
    # Fireworks models (DataZoneStandard)
    "fw-kimi-k25": "FW-Kimi-K2.5 (Fireworks Engine)",
    "fw-deepseek-v32": "FW-DeepSeek-V3.2 (Fireworks Engine)",
    "fw-gpt-oss-120b": "FW-GPT-OSS-120B (Fireworks Engine)",
    "fw-glm-5": "FW-GLM-5 (Fireworks Engine)",
    "fw-minimax-m25": "FW-MiniMax-M2.5 (Fireworks Engine)",
    # Azure Native models (GlobalStandard)
    "kimi-k25-native": "Kimi-K2.5 (Azure Native)",
    "deepseek-v32-native": "DeepSeek-V3.2 (Azure Native)",
    "gpt-oss-120b-native": "gpt-oss-120b (Azure Native)",
}


def benchmark_single(client, deployment_name, messages, max_tokens=512):
    """Run a single inference and measure TTFT and total time."""
    start = time.perf_counter()
    first_token_time = None
    total_tokens = 0

    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    )

    chunks = []
    for chunk in response:
        if first_token_time is None and chunk.choices and chunk.choices[0].delta.content:
            first_token_time = time.perf_counter()
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
            total_tokens += 1

    end = time.perf_counter()
    ttft = (first_token_time - start) if first_token_time else None
    total_time = end - start
    output_text = "".join(chunks)
    tps = total_tokens / total_time if total_time > 0 else 0

    return {
        "ttft_s": round(ttft, 4) if ttft else None,
        "total_time_s": round(total_time, 4),
        "output_tokens": total_tokens,
        "tokens_per_second": round(tps, 2),
        "output_length": len(output_text),
    }


def run_benchmark(client, deployment_name, label, iterations, prompts):
    """Run benchmark for one deployment across all prompts and iterations."""
    print(f"\n{'='*60}")
    print(f"Benchmarking: {label}")
    print(f"Deployment:   {deployment_name}")
    print(f"Iterations:   {iterations}")
    print(f"Prompts:      {len(prompts)}")
    print(f"{'='*60}")

    all_results = []

    for i, prompt in enumerate(prompts):
        prompt_results = []
        for j in range(iterations):
            try:
                result = benchmark_single(client, deployment_name, [prompt])
                prompt_results.append(result)
                ttft_str = f"{result['ttft_s']:.3f}" if result['ttft_s'] is not None else "N/A"
                print(f"  Prompt {i+1}/{len(prompts)} | Iter {j+1}/{iterations} | "
                      f"TTFT: {ttft_str}s | "
                      f"Total: {result['total_time_s']:.3f}s | "
                      f"TPS: {result['tokens_per_second']:.1f}")
            except Exception as e:
                print(f"  Prompt {i+1}/{len(prompts)} | Iter {j+1}/{iterations} | ERROR: {e}")
                prompt_results.append({"error": str(e)})

        all_results.append({
            "prompt_index": i,
            "prompt_text": prompt["content"][:80],
            "runs": prompt_results,
        })

    # Aggregate statistics
    valid_ttfts = [r["ttft_s"] for pr in all_results for r in pr["runs"] if isinstance(r.get("ttft_s"), (int, float))]
    valid_totals = [r["total_time_s"] for pr in all_results for r in pr["runs"] if isinstance(r.get("total_time_s"), (int, float))]
    valid_tps = [r["tokens_per_second"] for pr in all_results for r in pr["runs"] if isinstance(r.get("tokens_per_second"), (int, float))]

    summary = {
        "deployment": deployment_name,
        "label": label,
        "total_runs": len(valid_ttfts),
        "ttft_p50": round(statistics.median(valid_ttfts), 4) if valid_ttfts else None,
        "ttft_mean": round(statistics.mean(valid_ttfts), 4) if valid_ttfts else None,
        "ttft_stdev": round(statistics.stdev(valid_ttfts), 4) if len(valid_ttfts) > 1 else None,
        "total_time_p50": round(statistics.median(valid_totals), 4) if valid_totals else None,
        "total_time_mean": round(statistics.mean(valid_totals), 4) if valid_totals else None,
        "tps_p50": round(statistics.median(valid_tps), 2) if valid_tps else None,
        "tps_mean": round(statistics.mean(valid_tps), 2) if valid_tps else None,
    }

    print(f"\n--- Summary: {label} ---")
    print(f"  TTFT P50:       {summary['ttft_p50']}s")
    print(f"  TTFT Mean:      {summary['ttft_mean']}s (σ={summary['ttft_stdev']})")
    print(f"  Total Time P50: {summary['total_time_p50']}s")
    print(f"  TPS P50:        {summary['tps_p50']} tok/s")

    return {"summary": summary, "details": all_results}


def main():
    parser = argparse.ArgumentParser(description="Fireworks vs Native Inference Benchmark")
    parser.add_argument("--endpoint", required=True, help="Azure Foundry endpoint URL")
    parser.add_argument("--api-key", default=None, help="API key (or set AZURE_API_KEY env var)")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations per prompt (default: 5)")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max output tokens (default: 512)")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON file")
    parser.add_argument("--deployments", nargs="+", default=list(DEPLOYMENTS.keys()),
                        help="Deployment names to benchmark")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("AZURE_API_KEY")
    if not api_key:
        print("ERROR: Provide --api-key or set AZURE_API_KEY environment variable")
        return

    client = AzureOpenAI(
        azure_endpoint=args.endpoint,
        api_key=api_key,
        api_version="2024-10-21",
    )

    results = {}
    for dep in args.deployments:
        label = DEPLOYMENTS.get(dep, dep)
        results[dep] = run_benchmark(client, dep, label, args.iterations, TEST_PROMPTS)

    # Comparison table
    if len(results) >= 2:
        print(f"\n{'='*60}")
        print("COMPARISON TABLE")
        print(f"{'='*60}")
        print(f"{'Metric':<20} | ", end="")
        for dep in results:
            print(f"{results[dep]['summary']['label'][:25]:<28} | ", end="")
        print()
        print("-" * 80)
        for metric in ["ttft_p50", "ttft_mean", "total_time_p50", "tps_p50", "tps_mean"]:
            print(f"{metric:<20} | ", end="")
            for dep in results:
                val = results[dep]["summary"].get(metric, "N/A")
                print(f"{str(val):<28} | ", end="")
            print()

    # Save results
    output_data = {
        "test_config": {
            "endpoint": args.endpoint,
            "iterations": args.iterations,
            "max_tokens": args.max_tokens,
            "num_prompts": len(TEST_PROMPTS),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "results": {dep: results[dep] for dep in results},
    }

    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
