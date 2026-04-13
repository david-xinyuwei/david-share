#!/usr/bin/env python3
"""
Fireworks vs Native Inference Benchmark v2 (De-noised)
Fixes: captures reasoning_content, warmup, outlier removal, per-prompt stats.

Author: Xinyu Wei
Usage:
    python3 fw_vs_native_benchmark_v2.py \
        --endpoint "https://your-resource.cognitiveservices.azure.com/" \
        --api-key "YOUR_API_KEY" \
        --iterations 10 \
        --output results_v3.json
"""

import argparse
import json
import os
import time
import statistics
from openai import AzureOpenAI


TEST_PROMPTS = [
    {"role": "user", "content": "Explain the concept of attention mechanism in transformers in 3 sentences."},
    {"role": "user", "content": "What are the key differences between TCP and UDP protocols?"},
    {"role": "user", "content": "Summarize the main ideas of reinforcement learning in 5 bullet points."},
    {"role": "user", "content": "Explain how a database index works and when to use composite indexes."},
    {"role": "user", "content": "What is the difference between L1 and L2 regularization in machine learning?"},
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
    """Run a single streaming inference. Captures both content and reasoning_content."""
    start = time.perf_counter()
    first_token_time = None
    content_tokens = 0
    reasoning_tokens = 0

    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    )

    content_chunks = []
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        # Capture content tokens
        if delta.content:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            content_chunks.append(delta.content)
            content_tokens += 1

        # Capture reasoning_content (thinking tokens)
        rc = getattr(delta, "reasoning_content", None)
        if rc:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            reasoning_tokens += 1

    end = time.perf_counter()
    total_tokens = content_tokens + reasoning_tokens
    ttft = (first_token_time - start) if first_token_time else None
    total_time = end - start
    tps = total_tokens / total_time if total_time > 0 and total_tokens > 0 else 0

    return {
        "ttft_s": round(ttft, 4) if ttft else None,
        "total_time_s": round(total_time, 4),
        "content_tokens": content_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "tokens_per_second": round(tps, 2),
        "output_length": len("".join(content_chunks)),
    }


def remove_outliers_iqr(data, factor=1.5):
    """Remove outliers using IQR method."""
    if len(data) < 4:
        return data
    sorted_data = sorted(data)
    q1 = sorted_data[len(sorted_data) // 4]
    q3 = sorted_data[3 * len(sorted_data) // 4]
    iqr = q3 - q1
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr
    return [x for x in data if lower <= x <= upper]


def warmup(client, deployment_name, n=2):
    """Send warmup requests to avoid cold start bias."""
    print(f"  Warming up ({n} requests)...", end="", flush=True)
    for _ in range(n):
        try:
            client.chat.completions.create(
                model=deployment_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
        except Exception:
            pass
    print(" done")


def run_benchmark(client, deployment_name, label, iterations, prompts):
    """Run benchmark for one deployment."""
    print(f"\n{'='*70}")
    print(f"Benchmarking: {label}")
    print(f"Deployment:   {deployment_name}")
    print(f"Iterations:   {iterations}")
    print(f"Prompts:      {len(prompts)}")
    print(f"{'='*70}")

    warmup(client, deployment_name)

    all_results = []

    for i, prompt in enumerate(prompts):
        prompt_results = []
        for j in range(iterations):
            try:
                result = benchmark_single(client, deployment_name, [prompt])
                prompt_results.append(result)
                ttft_str = f"{result['ttft_s']:.3f}" if result['ttft_s'] is not None else "N/A"
                print(f"  P{i+1} I{j+1} | TTFT:{ttft_str:>7}s | "
                      f"Total:{result['total_time_s']:>7.3f}s | "
                      f"TPS:{result['tokens_per_second']:>6.1f} | "
                      f"C:{result['content_tokens']:>3} R:{result['reasoning_tokens']:>3}")
            except Exception as e:
                print(f"  P{i+1} I{j+1} | ERROR: {e}")
                prompt_results.append({"error": str(e)})

        all_results.append({
            "prompt_index": i,
            "prompt_text": prompt["content"][:80],
            "runs": prompt_results,
        })

    # Aggregate with outlier removal
    raw_ttfts = [r["ttft_s"] for pr in all_results for r in pr["runs"]
                 if isinstance(r.get("ttft_s"), (int, float))]
    raw_totals = [r["total_time_s"] for pr in all_results for r in pr["runs"]
                  if isinstance(r.get("total_time_s"), (int, float)) and r.get("total_tokens", 0) > 0]
    raw_tps = [r["tokens_per_second"] for pr in all_results for r in pr["runs"]
               if isinstance(r.get("tokens_per_second"), (int, float)) and r["tokens_per_second"] > 0]
    raw_content_tps = []
    for pr in all_results:
        for r in pr["runs"]:
            if isinstance(r.get("total_time_s"), (int, float)) and r.get("content_tokens", 0) > 0:
                raw_content_tps.append(round(r["content_tokens"] / r["total_time_s"], 2))

    # After IQR outlier removal
    clean_ttfts = remove_outliers_iqr(raw_ttfts)
    clean_totals = remove_outliers_iqr(raw_totals)
    clean_tps = remove_outliers_iqr(raw_tps)
    clean_content_tps = remove_outliers_iqr(raw_content_tps)

    def safe_stats(data):
        if not data:
            return {"p50": None, "mean": None, "stdev": None, "n": 0}
        return {
            "p50": round(statistics.median(data), 4),
            "mean": round(statistics.mean(data), 4),
            "stdev": round(statistics.stdev(data), 4) if len(data) > 1 else 0,
            "n": len(data),
        }

    summary = {
        "deployment": deployment_name,
        "label": label,
        "ttft": safe_stats(clean_ttfts),
        "total_time": safe_stats(clean_totals),
        "tps_all_tokens": safe_stats(clean_tps),
        "tps_content_only": safe_stats(clean_content_tps),
        "raw_samples": {
            "ttft": len(raw_ttfts),
            "tps": len(raw_tps),
            "total_runs": sum(len(pr["runs"]) for pr in all_results),
        },
        "outliers_removed": {
            "ttft": len(raw_ttfts) - len(clean_ttfts),
            "tps": len(raw_tps) - len(clean_tps),
        },
    }

    print(f"\n--- Summary: {label} (after outlier removal) ---")
    print(f"  TTFT P50:            {summary['ttft']['p50']}s  (N={summary['ttft']['n']}, σ={summary['ttft']['stdev']})")
    print(f"  Total Time P50:      {summary['total_time']['p50']}s  (N={summary['total_time']['n']})")
    print(f"  TPS P50 (all):       {summary['tps_all_tokens']['p50']} tok/s  (N={summary['tps_all_tokens']['n']})")
    print(f"  TPS P50 (content):   {summary['tps_content_only']['p50']} tok/s  (N={summary['tps_content_only']['n']})")
    print(f"  Outliers removed:    TTFT={summary['outliers_removed']['ttft']}, TPS={summary['outliers_removed']['tps']}")

    return {"summary": summary, "details": all_results}


def main():
    parser = argparse.ArgumentParser(description="Fireworks vs Native Benchmark v2 (De-noised)")
    parser.add_argument("--endpoint", required=True, help="Azure Foundry endpoint URL")
    parser.add_argument("--api-key", default=None, help="API key (or set AZURE_API_KEY env var)")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per prompt (default: 10)")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max output tokens (default: 512)")
    parser.add_argument("--output", default="benchmark_results_v3.json", help="Output JSON file")
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
        print(f"\n{'='*70}")
        print("COMPARISON TABLE (after outlier removal)")
        print(f"{'='*70}")
        header = f"{'Metric':<25}"
        for dep in results:
            header += f" | {results[dep]['summary']['label'][:30]:<32}"
        print(header)
        print("-" * 95)

        metrics = [
            ("TTFT P50 (s)", lambda s: s["ttft"]["p50"]),
            ("TTFT Mean (s)", lambda s: s["ttft"]["mean"]),
            ("TTFT σ (s)", lambda s: s["ttft"]["stdev"]),
            ("TTFT N", lambda s: s["ttft"]["n"]),
            ("Total Time P50 (s)", lambda s: s["total_time"]["p50"]),
            ("TPS P50 (all)", lambda s: s["tps_all_tokens"]["p50"]),
            ("TPS Mean (all)", lambda s: s["tps_all_tokens"]["mean"]),
            ("TPS P50 (content)", lambda s: s["tps_content_only"]["p50"]),
            ("TPS Mean (content)", lambda s: s["tps_content_only"]["mean"]),
        ]
        for name, fn in metrics:
            row = f"{name:<25}"
            for dep in results:
                val = fn(results[dep]["summary"])
                row += f" | {str(val):<32}"
            print(row)

    # Save
    output_data = {
        "test_config": {
            "endpoint": args.endpoint,
            "iterations": args.iterations,
            "max_tokens": args.max_tokens,
            "num_prompts": len(TEST_PROMPTS),
            "denoising": "IQR outlier removal + warmup + reasoning_content capture",
            "api_version": "2024-10-21",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "results": {dep: results[dep] for dep in results},
    }

    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
