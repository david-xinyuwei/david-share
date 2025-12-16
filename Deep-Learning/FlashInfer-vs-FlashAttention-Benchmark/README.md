# FlashInfer vs FlashAttention Benchmark

A fair and rigorous benchmark comparing FlashInfer and FlashAttention on NVIDIA H100 GPU, focusing on **Paged KV Cache** attention performance.

## Key Findings

| Metric | FA2 Paged | FlashInfer Paged | Winner |
|--------|-----------|------------------|--------|
| **Latency** | 1.88 ms | 2.78 ms | FA2 (1.48x faster) |
| **Peak VRAM** | 1.23 GB | 1.23 GB | Tie |
| **Min page_size** | 256 | 16 | FlashInfer |

**Conclusion:** When both use Paged KV Cache with `page_size=256`, FA2 is **1.48x faster** with identical memory usage. FlashInfer's only advantage is supporting smaller page sizes (16+), which may reduce memory fragmentation in some scenarios.

## Version Trap ⚠️

**Critical:** The package `flashinfer` (v0.2.0) is outdated. Use `flashinfer-python` (v0.5.3+) for current performance:

```bash
# WRONG - installs outdated v0.2.0
pip install flashinfer

# CORRECT - installs current v0.5.3+
pip install flashinfer-python
```

## Test Environment

| Component | Version |
|-----------|---------|
| GPU | NVIDIA H100 NVL 95GB |
| CUDA | 12.4 |
| PyTorch | 2.4.0+cu124 |
| FlashAttention-2 | 2.8.3 |
| FlashAttention-3 | 3.0.0b1 (source build) |
| FlashInfer | 0.5.3 (`flashinfer-python`) |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Paged KV Cache                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐    │
│   │ Page 0  │   │ Page 1  │   │ Page 2  │   │ Page 3  │    │
│   │ 256 tok │   │ 256 tok │   │ 256 tok │   │ 256 tok │    │
│   └─────────┘   └─────────┘   └─────────┘   └─────────┘    │
│        │             │             │             │          │
│        └─────────────┴─────────────┴─────────────┘          │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │ Page Table  │                          │
│                    │ [0,1,2,3]   │                          │
│                    └─────────────┘                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    Attention Backends                       │
├──────────────────────────┬──────────────────────────────────┤
│      FlashAttention-2    │         FlashInfer               │
│  flash_attn_with_kvcache │  BatchPrefillWithPagedKVCache    │
│  + block_table param     │  + paged_kv_indices              │
│  page_size = 256 (fixed) │  page_size = 16+ (flexible)      │
└──────────────────────────┴──────────────────────────────────┘
```

## Benchmark Results

### Test Configuration
- **batch_size:** 32
- **seq_len:** 512
- **num_heads:** 32
- **head_dim:** 128
- **page_size:** 256 (both backends)
- **Warmup:** 10 iterations
- **Benchmark:** 100 iterations

### Results

```
============================================================
FA2 Paged vs FlashInfer Paged (page_size=256)
============================================================
FA2 Paged Attention:
  Average latency: 1.88 ms
  Peak VRAM: 1.23 GB

FlashInfer Paged Attention:
  Average latency: 2.78 ms
  Peak VRAM: 1.23 GB

Comparison:
  FA2 Paged is 1.48x FASTER than FlashInfer Paged
  Memory usage: SAME
============================================================
```

## Quick Start

### Installation

```bash
# Create conda environment
conda create -n flash_bench python=3.10 -y
conda activate flash_bench

# Install PyTorch
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124

# Install FlashAttention-2
pip install flash-attn==2.8.3 --no-build-isolation

# Install FlashInfer (CORRECT package name!)
pip install flashinfer-python
```

### Run Benchmark

```bash
python fair_benchmark.py
```

## Code Examples

### FA2 Paged Attention

```python
from flash_attn import flash_attn_with_kvcache

# FA2 requires page_size=256
page_size = 256
num_pages = (max_seq_len + page_size - 1) // page_size

# Paged KV cache shape: [num_pages, page_size, num_heads, head_dim]
k_cache = torch.zeros(num_pages, page_size, num_kv_heads, head_dim, 
                      dtype=torch.float16, device='cuda')
v_cache = torch.zeros(num_pages, page_size, num_kv_heads, head_dim,
                      dtype=torch.float16, device='cuda')

# Block table maps sequence positions to pages
block_table = torch.arange(num_pages, dtype=torch.int32, device='cuda')
block_table = block_table.unsqueeze(0).expand(batch_size, -1)

# Run attention with paged KV cache
output = flash_attn_with_kvcache(
    q, k_cache, v_cache,
    cache_seqlens=cache_seqlens,
    block_table=block_table,
    causal=True
)
```

### FlashInfer Paged Attention

```python
import flashinfer

# FlashInfer supports page_size >= 16
page_size = 256  # Use same as FA2 for fair comparison

# Create paged KV cache
kv_data = torch.zeros(num_pages, 2, page_size, num_kv_heads, head_dim,
                      dtype=torch.float16, device='cuda')

# Setup indices and indptr
kv_page_indices = torch.arange(num_pages, dtype=torch.int32, device='cuda')
kv_page_indptr = torch.tensor([0, num_pages], dtype=torch.int32, device='cuda')
kv_last_page_len = torch.tensor([seq_len % page_size or page_size], 
                                 dtype=torch.int32, device='cuda')

# Create wrapper
wrapper = flashinfer.BatchPrefillWithPagedKVCacheWrapper(
    torch.empty(32*1024*1024, dtype=torch.uint8, device='cuda')
)

# Plan and run
wrapper.plan(
    qo_indptr, kv_page_indptr, kv_page_indices, kv_last_page_len,
    num_heads, num_kv_heads, head_dim, page_size
)
output = wrapper.run(q, kv_data)
```

## When to Use Which?

| Scenario | Recommendation |
|----------|----------------|
| Maximum throughput | FlashAttention-2 |
| Memory-constrained with variable sequences | FlashInfer (smaller pages) |
| Hopper GPU (H100/H200) with standard attention | FlashAttention-3 |
| Production LLM serving | Both viable, benchmark your workload |

## Lessons Learned

1. **Always verify package versions** before benchmarking
2. **Check for package name changes** - `flashinfer` → `flashinfer-python`
3. **Counter-intuitive results usually indicate test errors**, not library bugs
4. **Popular libraries rarely have 2x performance gaps** - double-check methodology

## References

- [FlashAttention](https://github.com/Dao-AILab/flash-attention)
- [FlashInfer](https://github.com/flashinfer-ai/flashinfer)
- [FlashAttention-3 Paper](https://arxiv.org/abs/2407.08608)

## Author

**Xinyu Wei** (魏新宇)  
AI & Apps GBB Architect @ Microsoft

## License

MIT
