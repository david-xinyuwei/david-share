#!/usr/bin/env python3
"""
Fair Benchmark: FlashAttention-2 Paged vs FlashInfer Paged
Both using page_size=256 for fair comparison

Author: Xinyu Wei (魏新宇)
Date: 2025-06-19
"""

import torch
import time
import gc

# =============================================================================
# Configuration
# =============================================================================
BATCH_SIZE = 32
SEQ_LEN = 512
NUM_HEADS = 32
NUM_KV_HEADS = 8  # GQA
HEAD_DIM = 128
PAGE_SIZE = 256  # FA2 requires 256, FI supports 16+
WARMUP_ITERS = 10
BENCHMARK_ITERS = 100

print(f"""
============================================================
Fair Benchmark Configuration
============================================================
batch_size:  {BATCH_SIZE}
seq_len:     {SEQ_LEN}
num_heads:   {NUM_HEADS}
num_kv_heads: {NUM_KV_HEADS}
head_dim:    {HEAD_DIM}
page_size:   {PAGE_SIZE}
warmup:      {WARMUP_ITERS}
benchmark:   {BENCHMARK_ITERS}
============================================================
""")

# Check versions
print("Package versions:")
try:
    import flash_attn
    print(f"  flash-attn: {flash_attn.__version__}")
except:
    print("  flash-attn: NOT INSTALLED")

try:
    import flashinfer
    print(f"  flashinfer: {flashinfer.__version__}")
except:
    print("  flashinfer: NOT INSTALLED")

print(f"  torch: {torch.__version__}")
print(f"  CUDA: {torch.version.cuda}")
print()

# =============================================================================
# Helper Functions
# =============================================================================
def get_gpu_memory():
    """Get current GPU memory usage in GB"""
    torch.cuda.synchronize()
    return torch.cuda.max_memory_allocated() / 1024**3

def reset_memory():
    """Reset GPU memory stats"""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()

def benchmark_fn(fn, warmup=WARMUP_ITERS, iters=BENCHMARK_ITERS):
    """Benchmark a function and return average latency in ms"""
    # Warmup
    for _ in range(warmup):
        fn()
    
    torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    end = time.perf_counter()
    
    return (end - start) / iters * 1000  # ms

# =============================================================================
# FA2 Paged Attention
# =============================================================================
def test_fa2_paged():
    """Test FlashAttention-2 with Paged KV Cache via block_table"""
    from flash_attn import flash_attn_with_kvcache
    
    reset_memory()
    
    num_pages = (SEQ_LEN + PAGE_SIZE - 1) // PAGE_SIZE
    
    # Query: [batch, 1, heads, head_dim] for decode
    q = torch.randn(BATCH_SIZE, 1, NUM_HEADS, HEAD_DIM, 
                    dtype=torch.float16, device='cuda')
    
    # Paged KV cache: [num_pages * batch, page_size, kv_heads, head_dim]
    total_pages = num_pages * BATCH_SIZE
    k_cache = torch.randn(total_pages, PAGE_SIZE, NUM_KV_HEADS, HEAD_DIM,
                          dtype=torch.float16, device='cuda')
    v_cache = torch.randn(total_pages, PAGE_SIZE, NUM_KV_HEADS, HEAD_DIM,
                          dtype=torch.float16, device='cuda')
    
    # Block table: [batch, num_pages] maps to page indices
    block_table = torch.arange(total_pages, dtype=torch.int32, device='cuda')
    block_table = block_table.reshape(BATCH_SIZE, num_pages)
    
    # Cache sequence lengths
    cache_seqlens = torch.full((BATCH_SIZE,), SEQ_LEN, dtype=torch.int32, device='cuda')
    
    def run():
        return flash_attn_with_kvcache(
            q, k_cache, v_cache,
            cache_seqlens=cache_seqlens,
            block_table=block_table,
            causal=True
        )
    
    # Verify it works
    out = run()
    
    latency = benchmark_fn(run)
    memory = get_gpu_memory()
    
    return latency, memory

# =============================================================================
# FlashInfer Paged Attention
# =============================================================================
def test_flashinfer_paged():
    """Test FlashInfer with Paged KV Cache"""
    import flashinfer
    
    reset_memory()
    
    num_pages_per_seq = (SEQ_LEN + PAGE_SIZE - 1) // PAGE_SIZE
    total_pages = num_pages_per_seq * BATCH_SIZE
    
    # Query: [total_tokens, heads, head_dim]
    q = torch.randn(BATCH_SIZE, NUM_HEADS, HEAD_DIM,
                    dtype=torch.float16, device='cuda')
    
    # Paged KV data: [total_pages, 2, page_size, kv_heads, head_dim]
    kv_data = torch.randn(total_pages, 2, PAGE_SIZE, NUM_KV_HEADS, HEAD_DIM,
                          dtype=torch.float16, device='cuda')
    
    # Page indices for all sequences
    kv_page_indices = torch.arange(total_pages, dtype=torch.int32, device='cuda')
    
    # Page indptr: boundaries for each sequence
    kv_page_indptr = torch.arange(0, BATCH_SIZE + 1, dtype=torch.int32, device='cuda') * num_pages_per_seq
    
    # Last page lengths
    last_page_len = SEQ_LEN % PAGE_SIZE
    if last_page_len == 0:
        last_page_len = PAGE_SIZE
    kv_last_page_len = torch.full((BATCH_SIZE,), last_page_len, dtype=torch.int32, device='cuda')
    
    # Query indptr for decode (1 token per sequence)
    qo_indptr = torch.arange(0, BATCH_SIZE + 1, dtype=torch.int32, device='cuda')
    
    # Workspace
    workspace = torch.empty(128 * 1024 * 1024, dtype=torch.uint8, device='cuda')
    
    # Create wrapper
    wrapper = flashinfer.BatchPrefillWithPagedKVCacheWrapper(workspace, "NHD")
    
    # Plan
    wrapper.plan(
        qo_indptr,
        kv_page_indptr,
        kv_page_indices,
        kv_last_page_len,
        NUM_HEADS,
        NUM_KV_HEADS,
        HEAD_DIM,
        PAGE_SIZE,
        causal=True,
        q_data_type=torch.float16,
    )
    
    def run():
        return wrapper.run(q, kv_data)
    
    # Verify it works
    out = run()
    
    latency = benchmark_fn(run)
    memory = get_gpu_memory()
    
    return latency, memory

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    print("Running FA2 Paged Attention...")
    fa2_latency, fa2_memory = test_fa2_paged()
    print(f"  Latency: {fa2_latency:.2f} ms")
    print(f"  Peak VRAM: {fa2_memory:.2f} GB")
    print()
    
    print("Running FlashInfer Paged Attention...")
    fi_latency, fi_memory = test_flashinfer_paged()
    print(f"  Latency: {fi_latency:.2f} ms")
    print(f"  Peak VRAM: {fi_memory:.2f} GB")
    print()
    
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"FA2 Paged:       {fa2_latency:.2f} ms, {fa2_memory:.2f} GB")
    print(f"FlashInfer Paged: {fi_latency:.2f} ms, {fi_memory:.2f} GB")
    print()
    
    speedup = fi_latency / fa2_latency
    if speedup > 1:
        print(f"FA2 Paged is {speedup:.2f}x FASTER than FlashInfer Paged")
    else:
        print(f"FlashInfer Paged is {1/speedup:.2f}x FASTER than FA2 Paged")
    
    if abs(fa2_memory - fi_memory) < 0.1:
        print("Memory usage: SAME")
    elif fa2_memory < fi_memory:
        print(f"FA2 uses {fi_memory - fa2_memory:.2f} GB LESS memory")
    else:
        print(f"FlashInfer uses {fa2_memory - fi_memory:.2f} GB LESS memory")
    
    print("=" * 60)
