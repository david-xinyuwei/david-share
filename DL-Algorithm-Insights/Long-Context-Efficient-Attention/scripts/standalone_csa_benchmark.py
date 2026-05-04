#!/usr/bin/env python3
"""Standalone CSA/HCA Attention Benchmark
Validates compression ratio, memory savings, and speed of CSA/HCA vs standard attention.
No model weights needed — uses random initialization to test algorithm properties.

Usage:
    python3 -u standalone_csa_benchmark.py --output results.json
"""
import argparse
import json
import time
import gc
import torch
import torch.nn as nn
import torch.nn.functional as F


class StandardAttention(nn.Module):
    """Baseline: standard multi-head attention with full KV cache."""

    def __init__(self, dim=512, n_heads=8):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = dim // n_heads
        self.wq = nn.Linear(dim, dim, bias=False)
        self.wk = nn.Linear(dim, dim, bias=False)
        self.wv = nn.Linear(dim, dim, bias=False)
        self.wo = nn.Linear(dim, dim, bias=False)
        self.scale = self.head_dim ** -0.5

    def forward(self, x):
        B, N, D = x.shape
        q = self.wq(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.wk(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.wv(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        attn = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        attn = attn.transpose(1, 2).contiguous().view(B, N, D)
        return self.wo(attn), k, v  # return KV for cache size measurement

    def kv_cache_size(self, seq_len, batch_size=1):
        """KV cache size in bytes (BF16)."""
        return 2 * batch_size * self.n_heads * seq_len * self.head_dim * 2  # 2 for K+V, 2 for bf16


class CompressedSparseAttention(nn.Module):
    """CSA: block KV compression + top-k sparse selection.
    Simplified implementation following DeepSeek-V4 paper (Section 2.3.1)."""

    def __init__(self, dim=512, n_heads=8, compress_ratio=4, topk=64):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = dim // n_heads
        self.compress_ratio = compress_ratio
        self.topk = topk
        self.wq = nn.Linear(dim, dim, bias=False)
        self.wkv = nn.Linear(dim, self.head_dim, bias=False)  # shared KV (MQA style)
        self.wgate = nn.Linear(dim, self.head_dim, bias=False)
        self.wo = nn.Linear(dim, dim, bias=False)
        self.ape = nn.Parameter(torch.randn(compress_ratio, self.head_dim) * 0.02)
        self.scale = self.head_dim ** -0.5

    def compress_kv(self, x):
        """Compress every m tokens into 1 KV entry via gated pooling."""
        B, N, D = x.shape
        m = self.compress_ratio
        # Truncate to multiple of m
        n_blocks = N // m
        x_trunc = x[:, :n_blocks * m]
        kv = self.wkv(x_trunc)  # [B, n_blocks*m, head_dim]
        gate = self.wgate(x_trunc)  # [B, n_blocks*m, head_dim]
        # Reshape to blocks
        kv = kv.view(B, n_blocks, m, self.head_dim)
        gate = gate.view(B, n_blocks, m, self.head_dim)
        gate = gate + self.ape.unsqueeze(0).unsqueeze(0)  # add positional bias
        # Gated pooling: softmax over positions within block, weighted sum
        weights = F.softmax(gate, dim=2)
        compressed = (kv * weights).sum(dim=2)  # [B, n_blocks, head_dim]
        return compressed

    def forward(self, x):
        B, N, D = x.shape
        m = self.compress_ratio
        q = self.wq(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        # Compress KV
        compressed_kv = self.compress_kv(x)  # [B, n_blocks, head_dim]
        n_blocks = compressed_kv.shape[1]
        # Top-k selection (simplified: random scores, in real impl uses learned indexer)
        k_select = min(self.topk, n_blocks)
        # Use dot product between mean query and compressed KV as scores
        q_mean = q.mean(dim=2)  # [B, n_heads, head_dim]
        scores = torch.einsum("bhd,bnd->bhn", q_mean, compressed_kv)  # [B, n_heads, n_blocks]
        _, topk_idx = scores.topk(k_select, dim=-1)  # [B, n_heads, k_select]
        # Gather selected KV
        topk_idx_expanded = topk_idx.unsqueeze(-1).expand(-1, -1, -1, self.head_dim)
        compressed_kv_expanded = compressed_kv.unsqueeze(1).expand(-1, self.n_heads, -1, -1)
        selected_kv = torch.gather(compressed_kv_expanded, 2, topk_idx_expanded)  # [B, n_heads, k_select, head_dim]
        # Attention on selected KV
        attn = F.scaled_dot_product_attention(q, selected_kv, selected_kv)
        attn = attn.transpose(1, 2).contiguous().view(B, N, D)
        return self.wo(attn), compressed_kv, None

    def kv_cache_size(self, seq_len, batch_size=1):
        """Compressed KV cache size in bytes (BF16)."""
        n_blocks = seq_len // self.compress_ratio
        return batch_size * n_blocks * self.head_dim * 2  # 1 head (MQA), bf16


class HeavilyCompressedAttention(nn.Module):
    """HCA: extreme block compression + dense attention on all compressed entries.
    Simplified implementation following DeepSeek-V4 paper (Section 2.3.2)."""

    def __init__(self, dim=512, n_heads=8, compress_ratio=64):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = dim // n_heads
        self.compress_ratio = compress_ratio
        self.wq = nn.Linear(dim, dim, bias=False)
        self.wkv = nn.Linear(dim, self.head_dim, bias=False)
        self.wgate = nn.Linear(dim, self.head_dim, bias=False)
        self.wo = nn.Linear(dim, dim, bias=False)
        self.ape = nn.Parameter(torch.randn(compress_ratio, self.head_dim) * 0.02)
        self.scale = self.head_dim ** -0.5

    def compress_kv(self, x):
        """Compress every m' tokens into 1 KV entry (m' >> m)."""
        B, N, D = x.shape
        m = self.compress_ratio
        n_blocks = N // m
        if n_blocks == 0:
            return self.wkv(x).mean(dim=1, keepdim=True)
        x_trunc = x[:, :n_blocks * m]
        kv = self.wkv(x_trunc).view(B, n_blocks, m, self.head_dim)
        gate = self.wgate(x_trunc).view(B, n_blocks, m, self.head_dim)
        gate = gate + self.ape.unsqueeze(0).unsqueeze(0)
        weights = F.softmax(gate, dim=2)
        compressed = (kv * weights).sum(dim=2)
        return compressed

    def forward(self, x):
        B, N, D = x.shape
        q = self.wq(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        compressed_kv = self.compress_kv(x)  # [B, n_blocks, head_dim]
        # Dense attention on ALL compressed entries (no top-k)
        compressed_kv_expanded = compressed_kv.unsqueeze(1).expand(-1, self.n_heads, -1, -1)
        attn = F.scaled_dot_product_attention(q, compressed_kv_expanded, compressed_kv_expanded)
        attn = attn.transpose(1, 2).contiguous().view(B, N, D)
        return self.wo(attn), compressed_kv, None

    def kv_cache_size(self, seq_len, batch_size=1):
        """Heavily compressed KV cache size in bytes (BF16)."""
        n_blocks = seq_len // self.compress_ratio
        return batch_size * max(n_blocks, 1) * self.head_dim * 2


def measure_memory_and_speed(model, seq_len, dim, device, warmup=3, repeats=10):
    """Measure forward pass time and peak GPU memory."""
    x = torch.randn(1, seq_len, dim, dtype=torch.bfloat16, device=device)
    model = model.to(device=device, dtype=torch.bfloat16)
    model.eval()

    # Warmup
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(x)
    torch.cuda.synchronize()

    # Measure time
    torch.cuda.reset_peak_memory_stats()
    times = []
    with torch.no_grad():
        for _ in range(repeats):
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            _ = model(x)
            torch.cuda.synchronize()
            t1 = time.perf_counter()
            times.append(t1 - t0)

    peak_mem = torch.cuda.max_memory_allocated() / 1e9
    median_time = sorted(times)[len(times) // 2]
    return median_time, peak_mem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dim", type=int, default=512)
    parser.add_argument("--n-heads", type=int, default=8)
    parser.add_argument("--seq-lens", nargs="+", type=int,
                        default=[1024, 4096, 16384, 32768, 65536])
    parser.add_argument("--csa-ratio", type=int, default=4)
    parser.add_argument("--hca-ratio", type=int, default=64)
    parser.add_argument("--topk", type=int, default=64)
    parser.add_argument("--output", type=str, default="csa_benchmark_results.json")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name()}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    print(f"\nConfig: dim={args.dim}, heads={args.n_heads}, "
          f"CSA ratio={args.csa_ratio}, HCA ratio={args.hca_ratio}, topk={args.topk}")

    results = []

    for seq_len in args.seq_lens:
        print(f"\n{'='*60}")
        print(f"Sequence length: {seq_len:,}")

        for name, ModelClass, kwargs in [
            ("Standard MHA", StandardAttention, {"dim": args.dim, "n_heads": args.n_heads}),
            (f"CSA (m={args.csa_ratio})", CompressedSparseAttention,
             {"dim": args.dim, "n_heads": args.n_heads,
              "compress_ratio": args.csa_ratio, "topk": args.topk}),
            (f"HCA (m={args.hca_ratio})", HeavilyCompressedAttention,
             {"dim": args.dim, "n_heads": args.n_heads, "compress_ratio": args.hca_ratio}),
        ]:
            try:
                model = ModelClass(**kwargs)
                kv_bytes = model.kv_cache_size(seq_len)
                median_time, peak_mem = measure_memory_and_speed(
                    model, seq_len, args.dim, device
                )
                result = {
                    "attention": name,
                    "seq_len": seq_len,
                    "kv_cache_bytes": kv_bytes,
                    "kv_cache_mb": round(kv_bytes / 1e6, 2),
                    "forward_time_ms": round(median_time * 1000, 2),
                    "peak_gpu_memory_gb": round(peak_mem, 3),
                }
                results.append(result)
                print(f"  {name:20s} | KV cache: {kv_bytes/1e6:8.2f} MB | "
                      f"Time: {median_time*1000:8.2f} ms | Peak mem: {peak_mem:.3f} GB")
            except torch.cuda.OutOfMemoryError:
                print(f"  {name:20s} | OOM at seq_len={seq_len}")
                results.append({
                    "attention": name, "seq_len": seq_len,
                    "kv_cache_bytes": -1, "kv_cache_mb": -1,
                    "forward_time_ms": -1, "peak_gpu_memory_gb": -1,
                    "error": "OOM"
                })
            finally:
                del model
                gc.collect()
                torch.cuda.empty_cache()

    # Summary table
    print(f"\n{'='*60}")
    print("KV Cache Compression Ratio (vs Standard MHA):")
    for seq_len in args.seq_lens:
        std = [r for r in results if r["seq_len"] == seq_len and r["attention"] == "Standard MHA"]
        if not std or std[0].get("error"):
            continue
        std_kv = std[0]["kv_cache_bytes"]
        for r in results:
            if r["seq_len"] == seq_len and r["attention"] != "Standard MHA" and not r.get("error"):
                ratio = std_kv / r["kv_cache_bytes"] if r["kv_cache_bytes"] > 0 else 0
                print(f"  seq={seq_len:>6,} | {r['attention']:20s} | "
                      f"Compression: {ratio:.1f}× | "
                      f"Speedup: {std[0]['forward_time_ms']/r['forward_time_ms']:.2f}×")

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
