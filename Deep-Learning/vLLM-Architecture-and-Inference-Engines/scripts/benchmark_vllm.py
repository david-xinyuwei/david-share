#!/usr/bin/env python3
"""
FlashInfer vs FlashAttention Benchmark for vLLM

Compares end-to-end throughput of FlashInfer and FlashAttention attention backends.

Usage:
    python benchmark_vllm.py --model Qwen/Qwen2.5-0.5B-Instruct --runs 3
    python benchmark_vllm.py --model meta-llama/Llama-3.2-1B-Instruct --runs 3 --requests 64

Author: Xinyu Wei (Microsoft AI GBB)
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import torch


def get_env_info() -> Dict[str, Any]:
    """Collect environment information."""
    info = {
        "timestamp": datetime.now().isoformat(),
        "cuda_available": torch.cuda.is_available(),
    }
    
    if torch.cuda.is_available():
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["gpu_count"] = torch.cuda.device_count()
        info["cuda_version"] = torch.version.cuda
    
    try:
        import vllm
        info["vllm_version"] = vllm.__version__
    except ImportError:
        info["vllm_version"] = "not installed"
    
    try:
        import flashinfer
        info["flashinfer_version"] = flashinfer.__version__
    except ImportError:
        info["flashinfer_version"] = "not installed"
    
    return info


def run_benchmark(
    model: str,
    backend: str,
    num_requests: int = 128,
    max_tokens: int = 256,
    num_runs: int = 3,
    gpu_memory_utilization: float = 0.6,
) -> Dict[str, Any]:
    """Run throughput benchmark with specified attention backend."""
    
    # Set environment variable before importing vLLM
    os.environ["VLLM_ATTENTION_BACKEND"] = backend
    
    # Import vLLM after setting env var
    from vllm import LLM, SamplingParams
    
    print(f"\n=== {backend} Test ===")
    print(f"vLLM Attention Backend: {backend}")
    print(f"Model: {model}")
    print(f"Total requests: {num_requests}")
    
    # Initialize model
    llm = LLM(
        model=model,
        trust_remote_code=True,
        gpu_memory_utilization=gpu_memory_utilization,
        disable_log_stats=True,
        enforce_eager=True,  # Disable CUDA Graph for fair comparison
    )
    
    sampling_params = SamplingParams(
        temperature=0.0,
        max_tokens=max_tokens,
    )
    
    # Prepare prompts
    prompts = [
        f"Please write a short story about a robot. Story number {i}."
        for i in range(num_requests)
    ]
    
    # Warmup
    print("Warming up...")
    warmup_prompts = prompts[:4]
    _ = llm.generate(warmup_prompts, sampling_params)
    
    # Benchmark runs
    print("Benchmarking...")
    results: List[Dict[str, Any]] = []
    
    for run_idx in range(num_runs):
        torch.cuda.synchronize()
        start_time = time.perf_counter()
        
        outputs = llm.generate(prompts, sampling_params)
        
        torch.cuda.synchronize()
        end_time = time.perf_counter()
        
        elapsed = end_time - start_time
        total_tokens = sum(len(o.outputs[0].token_ids) for o in outputs)
        throughput = total_tokens / elapsed
        
        results.append({
            "run": run_idx + 1,
            "elapsed_s": round(elapsed, 2),
            "total_tokens": total_tokens,
            "throughput_tok_s": round(throughput, 0),
        })
        
        print(f"  Run {run_idx + 1}: {elapsed:.2f}s, {total_tokens} tokens, {throughput:.0f} tok/s")
    
    # Calculate average
    avg_throughput = sum(r["throughput_tok_s"] for r in results) / len(results)
    avg_time = sum(r["elapsed_s"] for r in results) / len(results)
    
    print(f"\n=== Result ({backend}) ===")
    print(f"Average time: {avg_time:.2f}s")
    print(f"Average throughput: {avg_throughput:.0f} tok/s")
    
    # Cleanup to free GPU memory
    del llm
    torch.cuda.empty_cache()
    
    return {
        "backend": backend,
        "runs": results,
        "average_throughput_tok_s": round(avg_throughput, 0),
        "average_time_s": round(avg_time, 2),
    }


def main():
    parser = argparse.ArgumentParser(
        description="FlashInfer vs FlashAttention Benchmark"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="Model to benchmark (default: Qwen/Qwen2.5-0.5B-Instruct)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=128,
        help="Number of requests per run (default: 128)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Max tokens per request (default: 256)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per backend (default: 3)",
    )
    parser.add_argument(
        "--gpu-mem",
        type=float,
        default=0.6,
        help="GPU memory utilization (default: 0.6)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file (optional)",
    )
    
    args = parser.parse_args()
    
    # Print environment info
    print("=== Environment ===")
    env_info = get_env_info()
    print(f"vLLM: {env_info.get('vllm_version', 'N/A')}")
    print(f"FlashInfer: {env_info.get('flashinfer_version', 'N/A')}")
    print(f"GPU: {env_info.get('gpu_name', 'N/A')}")
    print(f"CUDA: {env_info.get('cuda_version', 'N/A')}")
    
    # Run FlashInfer benchmark
    fi_results = run_benchmark(
        model=args.model,
        backend="FLASHINFER",
        num_requests=args.requests,
        max_tokens=args.max_tokens,
        num_runs=args.runs,
        gpu_memory_utilization=args.gpu_mem,
    )
    
    # Run FlashAttention benchmark
    fa_results = run_benchmark(
        model=args.model,
        backend="FLASH_ATTN",
        num_requests=args.requests,
        max_tokens=args.max_tokens,
        num_runs=args.runs,
        gpu_memory_utilization=args.gpu_mem,
    )
    
    # Summary
    print("\n" + "=" * 50)
    print("=== Summary ===")
    print(f"FlashInfer:     {fi_results['average_throughput_tok_s']:.0f} tok/s")
    print(f"FlashAttention: {fa_results['average_throughput_tok_s']:.0f} tok/s")
    
    fi_tps = fi_results["average_throughput_tok_s"]
    fa_tps = fa_results["average_throughput_tok_s"]
    
    if fa_tps > fi_tps:
        diff = (fa_tps - fi_tps) / fi_tps * 100
        print(f"Winner: FlashAttention (+{diff:.1f}%)")
    else:
        diff = (fi_tps - fa_tps) / fa_tps * 100
        print(f"Winner: FlashInfer (+{diff:.1f}%)")
    
    # Save results if output specified
    if args.output:
        full_results = {
            "environment": env_info,
            "config": {
                "model": args.model,
                "requests": args.requests,
                "max_tokens": args.max_tokens,
                "runs": args.runs,
                "gpu_memory_utilization": args.gpu_mem,
            },
            "results": {
                "flashinfer": fi_results,
                "flashattention": fa_results,
            },
            "summary": {
                "winner": "flashattention" if fa_tps > fi_tps else "flashinfer",
                "difference_percent": round(abs(fa_tps - fi_tps) / min(fa_tps, fi_tps) * 100, 1),
            },
        }
        
        with open(args.output, "w") as f:
            json.dump(full_results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
