#!/usr/bin/env python3
"""
Batch Size Sweep Benchmark: FlashInfer vs FlashAttention
Usage:
    python benchmark_batch_sweep.py --quick  # [1,8,32,128]
    python benchmark_batch_sweep.py          # [1,2,4,8,16,32,64,128]
"""

import argparse, json, subprocess, time, os, gc
from datetime import datetime
from typing import Dict, List, Any

BATCH_SIZES = [1, 2, 4, 8, 16, 32, 64, 128]
RUNS_PER_CONFIG = 3
MAX_TOKENS = 256
GPU_MEMORY_UTIL = 0.6

def get_gpu_info():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            p = r.stdout.strip().split(", ")
            return {"name": p[0], "memory": p[1], "driver": p[2]}
    except: pass
    return {"name": "Unknown", "memory": "Unknown", "driver": "Unknown"}

def get_package_versions():
    versions = {}
    for pkg in ["vllm", "flashinfer", "torch", "flash_attn"]:
        try:
            if pkg == "flash_attn": import flash_attn; versions[pkg] = flash_attn.__version__
            elif pkg == "flashinfer": import flashinfer; versions[pkg] = getattr(flashinfer, "__version__", "installed")
            elif pkg == "vllm": import vllm; versions[pkg] = vllm.__version__
            elif pkg == "torch": import torch; versions[pkg] = torch.__version__
        except: versions[pkg] = "not installed"
    return versions

def run_single_benchmark(model: str, batch_size: int, backend: str):
    from vllm import LLM, SamplingParams
    import torch
    
    os.environ["VLLM_ATTENTION_BACKEND"] = backend
    prompts = [f"Write a short story about adventure number {i}." for i in range(batch_size)]
    
    llm = LLM(model=model, gpu_memory_utilization=GPU_MEMORY_UTIL, enforce_eager=True, trust_remote_code=True)
    sampling_params = SamplingParams(max_tokens=MAX_TOKENS, temperature=0.8, top_p=0.95)
    
    _ = llm.generate(prompts[:min(2, batch_size)], sampling_params)  # Warmup
    
    start = time.perf_counter()
    outputs = llm.generate(prompts, sampling_params)
    total_time = time.perf_counter() - start
    
    total_tokens = sum(len(out.outputs[0].token_ids) for out in outputs)
    throughput = total_tokens / total_time
    
    del llm; torch.cuda.empty_cache(); gc.collect(); time.sleep(2)
    
    return {"batch_size": batch_size, "backend": backend, "total_time_s": round(total_time, 3),
            "total_output_tokens": total_tokens, "throughput_tokens_per_s": round(throughput, 2),
            "latency_per_request_s": round(total_time / batch_size, 4)}

def run_batch_sweep(model: str, batch_sizes: List[int], runs: int):
    results = {"metadata": {"model": model, "timestamp": datetime.now().isoformat(),
               "gpu": get_gpu_info(), "packages": get_package_versions(),
               "config": {"batch_sizes": batch_sizes, "runs": runs, "max_tokens": MAX_TOKENS}}, "benchmarks": []}
    
    backends = ["FLASHINFER", "FLASH_ATTN"]
    total = len(batch_sizes) * len(backends) * runs
    cur = 0
    
    print(f"\n{'='*60}\nBatch Sweep: {model}\nBatches: {batch_sizes}, Runs: {runs}, Total: {total}\n{'='*60}\n")
    
    for bs in batch_sizes:
        br = {"batch_size": bs, "FLASHINFER": {"runs": [], "avg": 0}, "FLASH_ATTN": {"runs": [], "avg": 0}}
        
        for be in backends:
            print(f"\n[Batch={bs}, {be}]")
            for r in range(runs):
                cur += 1
                print(f"  Run {r+1}/{runs} ({cur}/{total})...", end=" ", flush=True)
                try:
                    res = run_single_benchmark(model, bs, be)
                    br[be]["runs"].append(res)
                    print(f"✓ {res['throughput_tokens_per_s']:.1f} tok/s")
                except Exception as e:
                    print(f"✗ {e}")
                    br[be]["runs"].append({"error": str(e)})
            
            valid = [x for x in br[be]["runs"] if "error" not in x]
            if valid: br[be]["avg"] = round(sum(x["throughput_tokens_per_s"] for x in valid) / len(valid), 2)
        
        fi, fa = br["FLASHINFER"]["avg"], br["FLASH_ATTN"]["avg"]
        if fi > 0 and fa > 0:
            diff = ((fi - fa) / fa) * 100
            br["comparison"] = {"diff_percent": round(diff, 2), "winner": "FI" if diff > 0 else "FA", "margin": f"{abs(diff):.1f}%"}
            print(f"\n  → Batch {bs}: {br['comparison']['winner']} +{br['comparison']['margin']}")
        
        results["benchmarks"].append(br)
    return results

def print_summary(results):
    print(f"\n{'='*70}\nSUMMARY: FlashInfer vs FlashAttention\n{'='*70}")
    print(f"{'Batch':<8} {'FI (tok/s)':<12} {'FA (tok/s)':<12} {'Winner':<8} {'Margin':<10}")
    print("-"*70)
    prev = None
    for b in results["benchmarks"]:
        fi, fa = b["FLASHINFER"]["avg"], b["FLASH_ATTN"]["avg"]
        if "comparison" in b:
            w, m = b["comparison"]["winner"], b["comparison"]["margin"]
            mark = " ← CROSSOVER" if prev and prev != w else ""
            prev = w
            print(f"{b['batch_size']:<8} {fi:<12.1f} {fa:<12.1f} {w:<8} {m:<10}{mark}")
    print("="*70 + "\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--output", default="batch_sweep_results.json")
    p.add_argument("--batch-sizes", default=None)
    p.add_argument("--runs", type=int, default=RUNS_PER_CONFIG)
    p.add_argument("--quick", action="store_true")
    args = p.parse_args()
    
    bs = [int(x) for x in args.batch_sizes.split(",")] if args.batch_sizes else ([1,8,32,128] if args.quick else BATCH_SIZES)
    results = run_batch_sweep(args.model, bs, args.runs)
    
    with open(args.output, "w") as f: json.dump(results, f, indent=2)
    print(f"\nSaved: {args.output}")
    print_summary(results)

if __name__ == "__main__": main()
