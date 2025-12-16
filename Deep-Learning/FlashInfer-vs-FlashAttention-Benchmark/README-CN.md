# FlashInfer vs FlashAttention 性能对比测试

在 NVIDIA H100 GPU 上对 FlashInfer 和 FlashAttention 进行公平、严谨的基准测试，重点关注 **Paged KV Cache** 注意力性能。

## 核心结论

| 指标 | FA2 Paged | FlashInfer Paged | 胜出 |
|------|-----------|------------------|------|
| **延迟** | 1.88 ms | 2.78 ms | FA2 (快 1.48 倍) |
| **峰值显存** | 1.23 GB | 1.23 GB | 持平 |
| **最小 page_size** | 256 | 16 | FlashInfer |

**结论：** 当两者都使用 `page_size=256` 的 Paged KV Cache 时，FA2 **快 1.48 倍**，内存使用完全相同。FlashInfer 的唯一优势是支持更小的 page size（16+），在某些场景下可减少内存碎片。

## 版本陷阱 ⚠️

**关键：** 包名 `flashinfer`（v0.2.0）已过时。请使用 `flashinfer-python`（v0.5.3+）：

```bash
# 错误 - 安装过时的 v0.2.0
pip install flashinfer

# 正确 - 安装最新的 v0.5.3+
pip install flashinfer-python
```

## 测试环境

| 组件 | 版本 |
|------|------|
| GPU | NVIDIA H100 NVL 95GB |
| CUDA | 12.4 |
| PyTorch | 2.4.0+cu124 |
| FlashAttention-2 | 2.8.3 |
| FlashAttention-3 | 3.0.0b1（源码编译）|
| FlashInfer | 0.5.3（`flashinfer-python`）|

## 架构图

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
│                       注意力后端                             │
├──────────────────────────┬──────────────────────────────────┤
│      FlashAttention-2    │         FlashInfer               │
│  flash_attn_with_kvcache │  BatchPrefillWithPagedKVCache    │
│  + block_table 参数      │  + paged_kv_indices              │
│  page_size = 256 (固定)  │  page_size = 16+ (灵活)          │
└──────────────────────────┴──────────────────────────────────┘
```

## 测试结果

### 测试配置
- **batch_size:** 32
- **seq_len:** 512
- **num_heads:** 32
- **head_dim:** 128
- **page_size:** 256（两个后端相同）
- **预热:** 10 次迭代
- **测试:** 100 次迭代

### 结果

```
============================================================
FA2 Paged vs FlashInfer Paged (page_size=256)
============================================================
FA2 Paged Attention:
  平均延迟: 1.88 ms
  峰值显存: 1.23 GB

FlashInfer Paged Attention:
  平均延迟: 2.78 ms
  峰值显存: 1.23 GB

对比:
  FA2 Paged 比 FlashInfer Paged 快 1.48 倍
  内存使用: 相同
============================================================
```

## 快速开始

### 安装

```bash
# 创建 conda 环境
conda create -n flash_bench python=3.10 -y
conda activate flash_bench

# 安装 PyTorch
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124

# 安装 FlashAttention-2
pip install flash-attn==2.8.3 --no-build-isolation

# 安装 FlashInfer（注意正确的包名！）
pip install flashinfer-python
```

### 运行测试

```bash
python fair_benchmark.py
```

## 代码示例

### FA2 Paged Attention

```python
from flash_attn import flash_attn_with_kvcache

# FA2 要求 page_size=256
page_size = 256
num_pages = (max_seq_len + page_size - 1) // page_size

# Paged KV cache 形状: [num_pages, page_size, num_heads, head_dim]
k_cache = torch.zeros(num_pages, page_size, num_kv_heads, head_dim, 
                      dtype=torch.float16, device='cuda')
v_cache = torch.zeros(num_pages, page_size, num_kv_heads, head_dim,
                      dtype=torch.float16, device='cuda')

# Block table 将序列位置映射到页面
block_table = torch.arange(num_pages, dtype=torch.int32, device='cuda')
block_table = block_table.unsqueeze(0).expand(batch_size, -1)

# 使用 paged KV cache 运行注意力
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

# FlashInfer 支持 page_size >= 16
page_size = 256  # 与 FA2 相同以确保公平比较

# 创建 paged KV cache
kv_data = torch.zeros(num_pages, 2, page_size, num_kv_heads, head_dim,
                      dtype=torch.float16, device='cuda')

# 设置索引和指针
kv_page_indices = torch.arange(num_pages, dtype=torch.int32, device='cuda')
kv_page_indptr = torch.tensor([0, num_pages], dtype=torch.int32, device='cuda')
kv_last_page_len = torch.tensor([seq_len % page_size or page_size], 
                                 dtype=torch.int32, device='cuda')

# 创建 wrapper
wrapper = flashinfer.BatchPrefillWithPagedKVCacheWrapper(
    torch.empty(32*1024*1024, dtype=torch.uint8, device='cuda')
)

# 规划并运行
wrapper.plan(
    qo_indptr, kv_page_indptr, kv_page_indices, kv_last_page_len,
    num_heads, num_kv_heads, head_dim, page_size
)
output = wrapper.run(q, kv_data)
```

## 使用场景建议

| 场景 | 建议 |
|------|------|
| 追求最大吞吐量 | FlashAttention-2 |
| 内存受限 + 变长序列 | FlashInfer（更小的 page size）|
| Hopper GPU（H100/H200）标准注意力 | FlashAttention-3 |
| 生产环境 LLM 服务 | 两者皆可，需针对具体负载测试 |

## 经验教训

1. **基准测试前必须验证包版本**
2. **检查包名是否变更** - `flashinfer` → `flashinfer-python`
3. **反直觉的结果通常意味着测试错误**，而非库的 bug
4. **广泛使用的库不太可能有 2 倍性能差距** - 需要仔细检查方法论

## 参考资料

- [FlashAttention](https://github.com/Dao-AILab/flash-attention)
- [FlashInfer](https://github.com/flashinfer-ai/flashinfer)
- [FlashAttention-3 论文](https://arxiv.org/abs/2407.08608)

## 作者

**魏新宇** (Xinyu Wei)  
AI & Apps GBB Architect @ Microsoft

## 许可证

MIT
