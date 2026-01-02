#!/usr/bin/env python3
"""
Advanced Benchmark: FlashInfer vs FlashAttention
Test: CUDAGraph enabled + Long sequences
"""

import argparse, json, subprocess, time, os, gc
from datetime import datetime
from typing import Dict, List, Any

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

def run_benchmark(model: str, batch_size: int, backend: str, max_tokens: int, enforce_eager: bool):
    from vllm import LLM, SamplingParams
    import torch
    
    os.environ["VLLM_ATTENTION_BACKEND"] = backend
    
    # Longer prompts for long sequence test
    base_prompt = "Write a comprehensive and detailed analysis about the following topic. Include multiple perspectives, historical context, and future implications. Topic: The impact of artificial intelligence on "
    prompts = [f"{base_prompt} area number {i} of human society." for i in range(batch_size)]
    
    llm = LLM(
        model=model,
        gpu_memory_utilization=0.8,  # Higher for long sequences
        enforce_eager=enforce_eager,
        trust_remote_code=True,
    )
    
    sampling_params = SamplingParams(max_tokens=max_tokens, temperature=0.8, top_p=0.95)
    
    # Warmup
    _ = llm.generate(prompts[:min(2, batch_size)], sampling_params)
    
    # Timed run
    start = time.perf_counter()
    outputs = llm.generate(prompts, sampling_params)
    total_time = time.perf_counter() - start
    
    total_tokens = sum(len(out.outputs[0].token_ids) for out in outputs)
    throughput = total_tokens / total_time
    
    del llm; torch.cuda.empty_cache(); gc.collect(); time.sleep(2)
    
    return {
        "batch_size": batch_size,
        "backend": backend,
        "max_tokens": max_tokens,
        "enforce_eager": enforce_eager,
        "total_time_s": round(total_time, 3),
        "total_output_tokens": total_tokens,
        "throughput_tokens_per_s": round(throughput, 2),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--output", default="advanced_benchmark.json")
    args = parser.parse_args()
    
    results = {
        "metadata": {
            "model": args.model,
            "timestamp": datetime.now().isoformat(),
            "gpu": get_gpu_info(),
            "packages": get_package_versions(),
            "test_type": "advanced (CUDAGraph + long sequences)"
        },
        "benchmarks": []
    }
    
    # Test configurations
    configs = [
        # (batch_size, max_tokens, enforce_eager, description)
        (8, 256, True, "Short seq, eager (baseline)"),
        (8, 256, False, "Short seq, CUDAGraph"),
        (8, 1024, True, "Long seq, eager"),
        (8, 1024, False, "Long seq, CUDAGraph"),
        (32, 512, False, "Medium batch, CUDAGraph"),
    ]
    
    backends = ["FLASHINFER", "FLASH_ATTN"]
    total = len(configs) * len(backends)
    cur = 0
    
    print(f"\n{'='*70}")
    print(f"Advanced Benchmark: {args.model}")
    print(f"Testing CUDAGraph and Long Sequences")
    print(f"{'='*70}\n")
    
    for batch_size, max_tokens, enforce_eager, desc in configs:
        config_results = {
            "config": desc,
            "batch_size": batch_size,
            "max_tokens": max_tokens,
            "enforce_eager": enforce_eager,
            "results": {}
        }
        
        print(f"\n[{desc}] batch={batch_size}, max_tokens={max_tokens}, eager={enforce_eager}")
        
        for backend in backends:
            cur += 1
            print(f"  {backend} ({cur}/{total})...", end=" ", flush=True)
            
            try:
                result = run_benchmark(args.model, batch_size, backend, max_tokens, enforce_eager)
                config_results["results"][backend] = result
                print(f"✓ {result['throughput_tokens_per_s']:.1f} tok/s")
            except Exception as e:
                print(f"✗ {e}")
                config_results["results"][backend] = {"error": str(e)}
        
        # Compare
        fi = config_results["results"].get("FLASHINFER", {}).get("throughput_tokens_per_s", 0)
        fa = config_results["results"].get("FLASH_ATTN", {}).get("throughput_tokens_per_s", 0)
        
        if fi > 0 and fa > 0:
            diff = ((fi - fa) / fa) * 100
            config_results["comparison"] = {
                "diff_percent": round(diff, 2),
                "winner": "FI" if diff > 0 else "FA",
                "margin": f"{abs(diff):.1f}%"
            }
            print(f"  → {config_results['comparison']['winner']} +{config_results['comparison']['margin']}")
        
        results["benchmarks"].append(config_results)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Config':<35} {'FI':<12} {'FA':<12} {'Winner':<8}")
    print("-"*70)
    
    for b in results["benchmarks"]:
        fi = b["results"].get("FLASHINFER", {}).get("throughput_tokens_per_s", 0)
        fa = b["results"].get("FLASH_ATTN", {}).get("throughput_tokens_per_s", 0)
        winner = b.get("comparison", {}).get("winner", "N/A")
        margin = b.get("comparison", {}).get("margin", "")
        print(f"{b['config']:<35} {fi:<12.1f} {fa:<12.1f} {winner} {margin}")
    
    print("="*70)
    
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {args.output}")

if __name__ == "__main__":
    main()
