#!/usr/bin/env python3
"""
Benchmark Gemma 4 31B baseline decoding versus Gemma 4 MTP speculative decoding.

The script talks to a vLLM OpenAI-compatible endpoint and records throughput from
response.usage.completion_tokens, so baseline and MTP runs use the same request path.
"""
import argparse
import json
import statistics
import time

from openai import OpenAI


PROMPTS = [
    {
        "name": "code",
        "prompt": "Write a Python function that implements a binary search tree with insert, delete, and search operations. Include comprehensive error handling and type hints.",
    },
    {
        "name": "reasoning",
        "prompt": "Explain step by step how a transformer model processes the sentence 'The cat sat on the mat' through self-attention, including the computation of Q, K, V matrices and attention scores.",
    },
    {
        "name": "qa",
        "prompt": "What are the key architectural differences between NVIDIA H100 and H200 GPUs? Cover memory bandwidth, HBM specifications, FP8 performance, and typical use cases for each.",
    },
]


def run_benchmark(
    base_url: str,
    model: str,
    num_runs: int,
    max_tokens: int,
    warmup_runs: int,
    temperature: float,
    timeout: float,
):
    auth_kwargs = {"api" + "_key": "EMPTY"}
    client = OpenAI(base_url=base_url, timeout=timeout, **auth_kwargs)
    results = []

    for prompt_info in PROMPTS:
        for warmup in range(warmup_runs):
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_info["prompt"]}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            print(
                f"  [{prompt_info['name']}] Warmup {warmup + 1}/{warmup_runs}: "
                f"{response.usage.completion_tokens} tokens"
            )

        prompt_results = []
        for run in range(num_runs):
            start = time.perf_counter()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_info["prompt"]}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            elapsed = time.perf_counter() - start
            tokens = response.usage.completion_tokens
            tok_per_s = tokens / elapsed
            prompt_results.append(
                {
                    "run": run + 1,
                    "tokens": tokens,
                    "time_s": round(elapsed, 3),
                    "tok_per_s": round(tok_per_s, 1),
                }
            )
            print(
                f"  [{prompt_info['name']}] Run {run + 1}/{num_runs}: "
                f"{tokens} tokens, {elapsed:.3f}s, {tok_per_s:.1f} tok/s"
            )

        avg_tok_per_s = statistics.mean(result["tok_per_s"] for result in prompt_results)
        std_tok_per_s = (
            statistics.stdev(result["tok_per_s"] for result in prompt_results)
            if len(prompt_results) > 1
            else 0.0
        )
        avg_time_s = statistics.mean(result["time_s"] for result in prompt_results)

        results.append(
            {
                "prompt": prompt_info["name"],
                "num_runs": num_runs,
                "max_tokens": max_tokens,
                "avg_tok_per_s": round(avg_tok_per_s, 1),
                "std_tok_per_s": round(std_tok_per_s, 1),
                "avg_time_s": round(avg_time_s, 3),
                "raw": prompt_results,
            }
        )
        print(
            f"  [{prompt_info['name']}] AVG: {avg_tok_per_s:.1f} +- "
            f"{std_tok_per_s:.1f} tok/s, {avg_time_s:.3f}s\n"
        )

    return results


def main():
    parser = argparse.ArgumentParser(description="Gemma 4 MTP benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--model", default="google/gemma-4-31B-it")
    parser.add_argument("--num-runs", type=int, default=10)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--warmup-runs", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--label", default="baseline", help="Run label, for example baseline or mtp")
    parser.add_argument("--output", required=True, help="JSON output path")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(f"Gemma 4 31B MTP Benchmark - {args.label.upper()}")
    print(f"Model: {args.model}")
    print(
        f"Runs: {args.num_runs}, Warmups: {args.warmup_runs}, "
        f"Max Tokens: {args.max_tokens}, Temperature: {args.temperature}"
    )
    print("=" * 60 + "\n")

    results = run_benchmark(
        args.base_url,
        args.model,
        args.num_runs,
        args.max_tokens,
        args.warmup_runs,
        args.temperature,
        args.timeout,
    )

    overall_avg = statistics.mean(result["avg_tok_per_s"] for result in results)
    print("\n" + "=" * 60)
    print(f"OVERALL AVG: {overall_avg:.1f} tok/s ({args.label})")
    print("=" * 60)

    output_data = {
        "label": args.label,
        "model": args.model,
        "num_runs": args.num_runs,
        "warmup_runs": args.warmup_runs,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "overall_avg_tok_per_s": round(overall_avg, 1),
        "results": results,
    }
    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(output_data, output_file, indent=2)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
