#!/usr/bin/env python3
"""
Robustness test for FlashInfer vs FlashAttention benchmark.
Runs multiple iterations to verify result consistency.
"""

import os
import time
import json
import gc
import argparse


def run_benchmark(model: str, batch_size: int, max_tokens: int, 
                  enforce_eager: bool, backend: str, runs: int):
    """Run benchmark with specified configuration."""
    os.environ["VLLM_ATTENTION_BACKEND"] = backend
    
    from vllm import LLM, SamplingParams
    
    throughputs = []
    for run in range(runs):
        llm = LLM(
            model=model,
            gpu_memory_utilization=0.7,
            enforce_eager=enforce_eager,
            trust_remote_code=True
        )
        prompts = ["Explain quantum computing in detail:"] * batch_size
        params = SamplingParams(max_tokens=max_tokens, temperature=0.8)
        
        start = time.time()
        outputs = llm.generate(prompts, params)
        elapsed = time.time() - start
        
        total_tokens = sum(len(o.outputs[0].token_ids) for o in outputs)
        throughput = total_tokens / elapsed
        throughputs.append(throughput)
        print(f"    Run {run+1}: {throughput:.1f} tok/s")
        
        del llm
        gc.collect()
        import torch
        torch.cuda.empty_cache()
    
    return throughputs


def main():
    parser = argparse.ArgumentParser(
        description="Robustness test: FlashInfer vs FlashAttention (multiple runs)"
    )
    parser.add_argument(
        "--model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct",
        help="Model to benchmark (default: Qwen/Qwen2.5-0.5B-Instruct)"
    )
    parser.add_argument(
        "--runs", type=int, default=3,
        help="Number of runs per configuration (default: 3)"
    )
    parser.add_argument(
        "--output", type=str, default="robust_results.json",
        help="Output JSON file (default: robust_results.json)"
    )
    args = parser.parse_args()
    
    # Test configurations: (batch_size, max_tokens, enforce_eager, description)
    configs = [
        (8, 256, False, "Short_CUDAGraph"),
        (8, 1024, False, "Long_CUDAGraph"),
        (32, 512, False, "Medium_CUDAGraph"),
    ]
    
    results = {}
    
    for batch, max_tok, eager, desc in configs:
        print(f"\n===== {desc} (batch={batch}, max_tok={max_tok}) =====")
        results[desc] = {"FLASHINFER": [], "FLASH_ATTN": []}
        
        for backend in ["FLASHINFER", "FLASH_ATTN"]:
            print(f"  Backend: {backend}")
            throughputs = run_benchmark(
                args.model, batch, max_tok, eager, backend, args.runs
            )
            results[desc][backend] = throughputs
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY ({}-run average)".format(args.runs))
    print("=" * 70)
    
    for desc in results:
        fi_avg = sum(results[desc]["FLASHINFER"]) / args.runs
        fa_avg = sum(results[desc]["FLASH_ATTN"]) / args.runs
        diff = (fi_avg - fa_avg) / fa_avg * 100
        winner = "FI" if diff > 0 else "FA"
        print(f"{desc:25s} FI={fi_avg:7.1f}  FA={fa_avg:7.1f}  {winner} {abs(diff):.1f}%")
    
    # Save results
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
