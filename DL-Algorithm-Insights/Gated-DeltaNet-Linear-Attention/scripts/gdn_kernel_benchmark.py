#!/usr/bin/env python3
"""
Gated DeltaNet Kernel vs FlashAttention Benchmark
==================================================
Level 1: Pure kernel-level comparison on H100 80GB

Measures forward pass latency and peak memory at different sequence lengths.
Answers: "At what sequence length does GDN's O(n) beat FlashAttention's optimized O(n²)?"

Author: Xinyu Wei
"""

import torch
import time
import json
import argparse
import gc
import os
from datetime import datetime

# ============================================================
# Configuration
# ============================================================
SEQ_LENS = [1024, 4096, 16384, 32768, 65536, 131072]
NUM_HEADS = 16
HEAD_DIM = 128
BATCH_SIZE = 1
WARMUP_ITERS = 5
BENCH_ITERS = 20
DEVICE = "cuda"
DTYPE = torch.bfloat16


def get_gpu_info():
    """Collect GPU hardware info for reproducibility."""
    props = torch.cuda.get_device_properties(0)
    mem = getattr(props, 'total_memory', None) or getattr(props, 'total_mem', 0)
    return {
        "gpu_name": props.name,
        "gpu_memory_gb": round(mem / 1024**3, 1),
        "cuda_version": torch.version.cuda,
        "pytorch_version": torch.__version__,
    }


def clear_gpu():
    """Clear GPU memory between benchmarks."""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()


def benchmark_flash_attention(seq_len, num_heads, head_dim, batch_size, warmup, iters):
    """Benchmark FlashAttention v2 forward pass."""
    try:
        from flash_attn import flash_attn_func
    except ImportError:
        print("  [SKIP] flash-attn not installed")
        return None

    clear_gpu()

    # Create QKV tensors: (batch, seq_len, num_heads, head_dim)
    q = torch.randn(batch_size, seq_len, num_heads, head_dim, device=DEVICE, dtype=DTYPE)
    k = torch.randn(batch_size, seq_len, num_heads, head_dim, device=DEVICE, dtype=DTYPE)
    v = torch.randn(batch_size, seq_len, num_heads, head_dim, device=DEVICE, dtype=DTYPE)

    # Warmup
    for _ in range(warmup):
        _ = flash_attn_func(q, k, v, causal=True)
    torch.cuda.synchronize()

    # Benchmark
    torch.cuda.reset_peak_memory_stats()
    start_mem = torch.cuda.memory_allocated()

    latencies = []
    for _ in range(iters):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        _ = flash_attn_func(q, k, v, causal=True)
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)  # ms

    peak_mem = torch.cuda.max_memory_allocated()
    input_mem = q.nelement() * q.element_size() * 3  # Q+K+V

    del q, k, v
    clear_gpu()

    return {
        "method": "FlashAttention",
        "seq_len": seq_len,
        "latency_ms_median": round(sorted(latencies)[len(latencies)//2], 3),
        "latency_ms_mean": round(sum(latencies)/len(latencies), 3),
        "latency_ms_min": round(min(latencies), 3),
        "latency_ms_max": round(max(latencies), 3),
        "peak_memory_mb": round(peak_mem / 1024**2, 1),
        "input_memory_mb": round(input_mem / 1024**2, 1),
        "runs": [round(x, 3) for x in latencies],
    }


def benchmark_gdn_chunk(seq_len, num_heads, head_dim, batch_size, warmup, iters):
    """Benchmark Gated DeltaNet chunk-wise forward pass using fla library."""
    try:
        from fla.ops.gated_delta_rule import chunk_gated_delta_rule
    except ImportError:
        try:
            from fla.ops.gated_delta_rule.chunk import chunk_gated_delta_rule_fwd
            chunk_gated_delta_rule = None  # Will use fwd directly
        except ImportError:
            print("  [SKIP] fla library not installed or API changed")
            return None

    clear_gpu()

    # GDN inputs: q, k, v, beta (learning rate), gate (forgetting factor)
    q = torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE)
    k = torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE)
    v = torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE)
    beta = torch.sigmoid(torch.randn(batch_size, num_heads, seq_len, device=DEVICE, dtype=DTYPE))
    # Gate: log-space for numerical stability
    gate = -torch.nn.functional.softplus(torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE))

    # Normalize k to unit norm (required for Householder)
    k = torch.nn.functional.normalize(k, p=2, dim=-1)

    # Warmup
    for _ in range(warmup):
        try:
            if chunk_gated_delta_rule is not None:
                _ = chunk_gated_delta_rule(q, k, v, beta, gate)
            else:
                _ = chunk_gated_delta_rule_fwd(q, k, v, beta, gate)
        except Exception as e:
            print(f"  [ERROR] GDN kernel call failed: {e}")
            del q, k, v, beta, gate
            clear_gpu()
            return None
    torch.cuda.synchronize()

    # Benchmark
    torch.cuda.reset_peak_memory_stats()

    latencies = []
    for _ in range(iters):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        if chunk_gated_delta_rule is not None:
            _ = chunk_gated_delta_rule(q, k, v, beta, gate)
        else:
            _ = chunk_gated_delta_rule_fwd(q, k, v, beta, gate)
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    peak_mem = torch.cuda.max_memory_allocated()
    input_mem = (q.nelement() + k.nelement() + v.nelement() + beta.nelement() + gate.nelement()) * q.element_size()

    del q, k, v, beta, gate
    clear_gpu()

    return {
        "method": "GatedDeltaNet",
        "seq_len": seq_len,
        "latency_ms_median": round(sorted(latencies)[len(latencies)//2], 3),
        "latency_ms_mean": round(sum(latencies)/len(latencies), 3),
        "latency_ms_min": round(min(latencies), 3),
        "latency_ms_max": round(max(latencies), 3),
        "peak_memory_mb": round(peak_mem / 1024**2, 1),
        "input_memory_mb": round(input_mem / 1024**2, 1),
        "runs": [round(x, 3) for x in latencies],
    }


def benchmark_gdn_fused_recurrent(seq_len, num_heads, head_dim, batch_size, warmup, iters):
    """Benchmark Gated DeltaNet fused recurrent mode (inference style)."""
    try:
        from fla.ops.gated_delta_rule import fused_recurrent_gated_delta_rule
    except ImportError:
        try:
            from fla.ops.gated_delta_rule.fused_recurrent import fused_recurrent_gated_delta_rule_fwd
            fused_recurrent_gated_delta_rule = None
        except ImportError:
            print("  [SKIP] fla fused_recurrent not available")
            return None

    clear_gpu()

    q = torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE)
    k = torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE)
    v = torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE)
    beta = torch.sigmoid(torch.randn(batch_size, num_heads, seq_len, device=DEVICE, dtype=DTYPE))
    gate = -torch.nn.functional.softplus(torch.randn(batch_size, num_heads, seq_len, head_dim, device=DEVICE, dtype=DTYPE))
    k = torch.nn.functional.normalize(k, p=2, dim=-1)

    for _ in range(warmup):
        try:
            if fused_recurrent_gated_delta_rule is not None:
                _ = fused_recurrent_gated_delta_rule(q, k, v, beta, gate)
            else:
                _ = fused_recurrent_gated_delta_rule_fwd(q, k, v, beta, gate)
        except Exception as e:
            print(f"  [ERROR] GDN fused_recurrent failed: {e}")
            del q, k, v, beta, gate
            clear_gpu()
            return None
    torch.cuda.synchronize()

    torch.cuda.reset_peak_memory_stats()
    latencies = []
    for _ in range(iters):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        if fused_recurrent_gated_delta_rule is not None:
            _ = fused_recurrent_gated_delta_rule(q, k, v, beta, gate)
        else:
            _ = fused_recurrent_gated_delta_rule_fwd(q, k, v, beta, gate)
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    peak_mem = torch.cuda.max_memory_allocated()
    input_mem = (q.nelement() + k.nelement() + v.nelement() + beta.nelement() + gate.nelement()) * q.element_size()

    del q, k, v, beta, gate
    clear_gpu()

    return {
        "method": "GDN_FusedRecurrent",
        "seq_len": seq_len,
        "latency_ms_median": round(sorted(latencies)[len(latencies)//2], 3),
        "latency_ms_mean": round(sum(latencies)/len(latencies), 3),
        "latency_ms_min": round(min(latencies), 3),
        "latency_ms_max": round(max(latencies), 3),
        "peak_memory_mb": round(peak_mem / 1024**2, 1),
        "input_memory_mb": round(input_mem / 1024**2, 1),
        "runs": [round(x, 3) for x in latencies],
    }


def print_summary(results):
    """Print a comparison table of results."""
    print("\n" + "="*100)
    print("BENCHMARK SUMMARY")
    print("="*100)
    print(f"{'Seq Len':>10} | {'FlashAttn (ms)':>15} | {'GDN Chunk (ms)':>15} | {'GDN Recur (ms)':>15} | {'GDN/FA Ratio':>12} | {'Winner':>10}")
    print("-"*100)

    seq_lens = sorted(set(r["seq_len"] for r in results))
    for sl in seq_lens:
        fa = next((r for r in results if r["method"] == "FlashAttention" and r["seq_len"] == sl), None)
        gdn_c = next((r for r in results if r["method"] == "GatedDeltaNet" and r["seq_len"] == sl), None)
        gdn_r = next((r for r in results if r["method"] == "GDN_FusedRecurrent" and r["seq_len"] == sl), None)

        fa_ms = f"{fa['latency_ms_median']:.3f}" if fa else "N/A"
        gdn_c_ms = f"{gdn_c['latency_ms_median']:.3f}" if gdn_c else "N/A"
        gdn_r_ms = f"{gdn_r['latency_ms_median']:.3f}" if gdn_r else "N/A"

        if fa and gdn_c:
            ratio = gdn_c["latency_ms_median"] / fa["latency_ms_median"]
            ratio_str = f"{ratio:.2f}x"
            winner = "GDN" if ratio < 1.0 else "FA"
        else:
            ratio_str = "N/A"
            winner = "N/A"

        print(f"{sl:>10,} | {fa_ms:>15} | {gdn_c_ms:>15} | {gdn_r_ms:>15} | {ratio_str:>12} | {winner:>10}")

    # Memory comparison
    print("\n" + "="*100)
    print("MEMORY COMPARISON (Peak MB)")
    print("="*100)
    print(f"{'Seq Len':>10} | {'FlashAttn (MB)':>15} | {'GDN Chunk (MB)':>15} | {'GDN Recur (MB)':>15}")
    print("-"*75)
    for sl in seq_lens:
        fa = next((r for r in results if r["method"] == "FlashAttention" and r["seq_len"] == sl), None)
        gdn_c = next((r for r in results if r["method"] == "GatedDeltaNet" and r["seq_len"] == sl), None)
        gdn_r = next((r for r in results if r["method"] == "GDN_FusedRecurrent" and r["seq_len"] == sl), None)

        fa_mem = f"{fa['peak_memory_mb']:.1f}" if fa else "N/A"
        gdn_c_mem = f"{gdn_c['peak_memory_mb']:.1f}" if gdn_c else "N/A"
        gdn_r_mem = f"{gdn_r['peak_memory_mb']:.1f}" if gdn_r else "N/A"

        print(f"{sl:>10,} | {fa_mem:>15} | {gdn_c_mem:>15} | {gdn_r_mem:>15}")


def main():
    parser = argparse.ArgumentParser(description="GDN vs FlashAttention Kernel Benchmark")
    parser.add_argument("--seq-lens", nargs="+", type=int, default=SEQ_LENS,
                        help="Sequence lengths to benchmark")
    parser.add_argument("--num-heads", type=int, default=NUM_HEADS)
    parser.add_argument("--head-dim", type=int, default=HEAD_DIM)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--warmup", type=int, default=WARMUP_ITERS)
    parser.add_argument("--iters", type=int, default=BENCH_ITERS)
    parser.add_argument("--output", type=str, default="/root/gdn-benchmark/results/benchmark_results.json")
    parser.add_argument("--skip-fa", action="store_true", help="Skip FlashAttention benchmark")
    parser.add_argument("--skip-gdn", action="store_true", help="Skip GDN benchmark")
    args = parser.parse_args()

    print("="*60)
    print("GDN vs FlashAttention Kernel Benchmark")
    print("="*60)

    gpu_info = get_gpu_info()
    print(f"GPU: {gpu_info['gpu_name']} ({gpu_info['gpu_memory_gb']} GB)")
    print(f"CUDA: {gpu_info['cuda_version']}, PyTorch: {gpu_info['pytorch_version']}")
    print(f"Config: batch={args.batch_size}, heads={args.num_heads}, head_dim={args.head_dim}")
    print(f"Sequence lengths: {args.seq_lens}")
    print(f"Benchmark: {args.warmup} warmup + {args.iters} timed iterations")
    print()

    # Check library versions
    lib_versions = {}
    try:
        import flash_attn
        lib_versions["flash_attn"] = flash_attn.__version__
        print(f"flash-attn: {flash_attn.__version__}")
    except ImportError:
        print("flash-attn: NOT INSTALLED")

    try:
        import fla
        lib_versions["fla"] = getattr(fla, "__version__", "unknown")
        print(f"fla: {lib_versions['fla']}")
    except ImportError:
        print("fla: NOT INSTALLED")

    try:
        import triton
        lib_versions["triton"] = triton.__version__
        print(f"triton: {triton.__version__}")
    except ImportError:
        print("triton: NOT INSTALLED")

    print()

    results = []
    for seq_len in args.seq_lens:
        print(f"\n--- seq_len = {seq_len:,} ---")

        # FlashAttention
        if not args.skip_fa:
            print(f"  Running FlashAttention...", end=" ", flush=True)
            r = benchmark_flash_attention(seq_len, args.num_heads, args.head_dim, args.batch_size, args.warmup, args.iters)
            if r:
                results.append(r)
                print(f"median={r['latency_ms_median']:.3f} ms, peak_mem={r['peak_memory_mb']:.1f} MB")
            else:
                print("SKIPPED")

        # GDN Chunk
        if not args.skip_gdn:
            print(f"  Running GDN Chunk...", end=" ", flush=True)
            r = benchmark_gdn_chunk(seq_len, args.num_heads, args.head_dim, args.batch_size, args.warmup, args.iters)
            if r:
                results.append(r)
                print(f"median={r['latency_ms_median']:.3f} ms, peak_mem={r['peak_memory_mb']:.1f} MB")
            else:
                print("SKIPPED")

        # GDN Fused Recurrent
        if not args.skip_gdn:
            print(f"  Running GDN FusedRecurrent...", end=" ", flush=True)
            r = benchmark_gdn_fused_recurrent(seq_len, args.num_heads, args.head_dim, args.batch_size, args.warmup, args.iters)
            if r:
                results.append(r)
                print(f"median={r['latency_ms_median']:.3f} ms, peak_mem={r['peak_memory_mb']:.1f} MB")
            else:
                print("SKIPPED")

    # Print summary table
    if results:
        print_summary(results)

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "gpu_info": gpu_info,
        "lib_versions": lib_versions,
        "config": {
            "batch_size": args.batch_size,
            "num_heads": args.num_heads,
            "head_dim": args.head_dim,
            "warmup_iters": args.warmup,
            "bench_iters": args.iters,
            "dtype": str(DTYPE),
        },
        "results": results,
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
