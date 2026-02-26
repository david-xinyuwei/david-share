#!/usr/bin/env python3
"""
Compare FP8 Benchmark Results
Author: Xinyu Wei (Microsoft GBB AI Architect)
Date: 2026-01-03

Compare BF16 vs FP8 results from benchmark_fair.py

Usage:
    python compare_results.py results_bf16.json results_fp8.json
    python compare_results.py h100_bf16.json h100_fp8.json a100_bf16.json a100_fp8.json --labels H100 A100
"""

import json
import argparse
import sys
from typing import Dict, List


def load_results(filepath: str) -> Dict:
    """Load results from JSON file."""
    with open(filepath) as f:
        return json.load(f)


def compare_two(bf16_file: str, fp8_file: str, label: str = "") -> Dict:
    """Compare BF16 vs FP8 results."""
    bf16 = load_results(bf16_file)
    fp8 = load_results(fp8_file)
    
    prefix = f"[{label}] " if label else ""
    
    print(f"\n{'='*70}")
    print(f"{prefix}BF16 vs FP8 Comparison")
    print(f"{'='*70}")
    print(f"BF16 file: {bf16_file}")
    print(f"FP8 file:  {fp8_file}")
    
    # Table header
    print(f"\n| {'Scenario':<25} | {'BF16 (tok/s)':>12} | {'FP8 (tok/s)':>12} | {'Speedup':>10} |")
    print(f"|{'-'*27}|{'-'*14}|{'-'*14}|{'-'*12}|")
    
    comparison = {}
    scenarios = ["prefill_single", "prefill_concurrent", "decode_single", "decode_concurrent"]
    
    for scenario in scenarios:
        bf16_result = bf16.get("results", {}).get(scenario, {})
        fp8_result = fp8.get("results", {}).get(scenario, {})
        
        bf16_throughput = bf16_result.get("avg_throughput", 0)
        fp8_throughput = fp8_result.get("avg_throughput", 0)
        
        if bf16_throughput > 0:
            speedup = fp8_throughput / bf16_throughput
            speedup_str = f"{speedup:.2f}x"
            if speedup > 1:
                speedup_str = f"✅ {speedup_str}"
            elif speedup < 1:
                speedup_str = f"❌ {speedup_str}"
        else:
            speedup = 0
            speedup_str = "N/A"
        
        comparison[scenario] = {
            "bf16": bf16_throughput,
            "fp8": fp8_throughput,
            "speedup": speedup,
        }
        
        print(f"| {scenario:<25} | {bf16_throughput:>12.0f} | {fp8_throughput:>12.0f} | {speedup_str:>10} |")
    
    return comparison


def compare_gpus(results: List[Dict], labels: List[str]):
    """Compare results across GPUs."""
    
    print(f"\n{'='*80}")
    print("Cross-GPU Comparison")
    print(f"{'='*80}")
    
    scenarios = ["prefill_single", "prefill_concurrent", "decode_single", "decode_concurrent"]
    
    for scenario in scenarios:
        print(f"\n📊 {scenario}:")
        print(f"| {'GPU':<15} | {'BF16 (tok/s)':>12} | {'FP8 (tok/s)':>12} | {'FP8 Speedup':>12} |")
        print(f"|{'-'*17}|{'-'*14}|{'-'*14}|{'-'*14}|")
        
        for result, label in zip(results, labels):
            bf16 = result.get(scenario, {}).get("bf16", 0)
            fp8 = result.get(scenario, {}).get("fp8", 0)
            speedup = result.get(scenario, {}).get("speedup", 0)
            
            speedup_str = f"{speedup:.2f}x" if speedup > 0 else "N/A"
            print(f"| {label:<15} | {bf16:>12.0f} | {fp8:>12.0f} | {speedup_str:>12} |")


def main():
    parser = argparse.ArgumentParser(
        description="Compare FP8 Benchmark Results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Compare single GPU:
    python compare_results.py results_bf16.json results_fp8.json
    
    # Compare multiple GPUs:
    python compare_results.py h100_bf16.json h100_fp8.json a100_bf16.json a100_fp8.json --labels H100 A100
        """
    )
    parser.add_argument("files", nargs="+", help="Result JSON files (pairs of BF16, FP8)")
    parser.add_argument("--labels", nargs="+", help="Labels for each GPU (e.g., H100 A100)")
    
    args = parser.parse_args()
    
    if len(args.files) < 2 or len(args.files) % 2 != 0:
        print("Error: Please provide pairs of (BF16, FP8) result files")
        sys.exit(1)
    
    num_gpus = len(args.files) // 2
    labels = args.labels if args.labels else [f"GPU{i+1}" for i in range(num_gpus)]
    
    if len(labels) < num_gpus:
        labels.extend([f"GPU{i+1}" for i in range(len(labels), num_gpus)])
    
    all_comparisons = []
    
    for i in range(num_gpus):
        bf16_file = args.files[i * 2]
        fp8_file = args.files[i * 2 + 1]
        label = labels[i]
        
        comparison = compare_two(bf16_file, fp8_file, label)
        all_comparisons.append(comparison)
    
    if num_gpus > 1:
        compare_gpus(all_comparisons, labels)
    
    print(f"\n{'='*70}")
    print("Key Insights")
    print(f"{'='*70}")
    print("""
Technical Background:
- Prefill = Compute-bound (large matrix multiplication on entire prompt)
- Decode (single) = Memory-bound (small computation, KV cache read bottleneck)
- Decode (concurrent) = Compute-bound (batched, large matrix multiplication)

Expected FP8 Speedup:
- H100 (native FP8 Tensor Core): Better speedup in compute-bound scenarios
- A100 (Marlin dequant): Better speedup in memory-bound scenarios (bandwidth saving)
    """)


if __name__ == "__main__":
    main()
