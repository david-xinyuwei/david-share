# 🛰️ 星链搜索结果

> **Query**: Flash Attention vs GQA vs Paged Attention difference layer implementation architecture memory optimization 2024
> **Mode**: DEEP
> **Time**: 2026-01-12 22:22:19

---

## 📝 Answer

[  
FlashAttention, GQA, and PagedAttention operate at different layers of the stack and solve different memory problems, so they are mostly complementary rather than competing:

- **FlashAttention** = *kernel-level implementation of the attention op* (how a single attention layer is computed on GPU).
- **GQA (Grouped Query Attention)** = *architectural change to the attention module* (how many K/V heads exist and how they’re shared).
- **PagedAttention (vLLM)** = *system-level KV‑cache memory manager and attention kernel* (how KV states for many sequences are laid out and accessed during serving).

---

### 1. FlashAttention (v1–v3)

**What it changes**

- Keeps the *same mathematical attention* as standard multi‑head (or GQA/MQA/etc.), but changes **how it’s computed on GPU**.  
- Uses **tiling + on‑chip SRAM + online softmax** so it never materializes the full N×N attention matrix; instead, it processes Q/K/V in blocks and accumulates outputs.   

**Layer implementation / architecture**

- Implemented as **custom CUDA kernels** (now widely used via `flash-attn`, PyTorch scaled_dot_product_attention, etc.).   
- Does **not change the model architecture**: number of heads, hidden size, and KV cache layout can remain exactly as in standard MHA or GQA; the forward pass for each attention head just calls a different low‑level kernel.

**Memory optimization**

- Reduces activation memory from **O(N²)** (storing attention scores) to **O(N)** by recomputing needed pieces and avoiding the full score matrix in HBM.   
- Greatly cuts **HBM traffic**, turning attention from memory‑bound into closer to compute‑bound, giving 2–4× speedups and enabling long contexts.   
- Later versions (FlashAttention‑2, ‑3) further optimize GPU utilization and add **low‑precision (e.g., FP8) and Hopper‑specific tricks**; still fundamentally a kernel/implementation optimization, not an architectural one.   

**Scope**

- Applies to **training and inference**.
- Works *inside* whatever attention variant you use (MHA, GQA, MQA, etc.).

---

### 2. GQA (Grouped Query Attention)

**What it changes**

- GQA is an **architectural modification of the attention layer**:  
  - You keep many query heads, but **group them**, so each group shares a single K/V head.  
  - This interpolates between:
    - **MHA:** each query head has its own K/V head (max quality, max memory).
    - **MQA:** all query heads share one K/V head (min memory, some quality loss).   

**Layer implementation / architecture**

- In code: you choose **num_query_heads ≫ num_kv_heads**, e.g. 32 Q‑heads but 4 KV‑heads. The projections and KV cache are sized accordingly.  
- The attention computation itself can still use any kernel (naïve, FlashAttention, xFormers, etc.); GQA just changes **how many K/V tensors exist and how they’re shared**.

**Memory optimization**

- During **autoregressive inference**, the dominant memory is the **KV cache**. Standard MHA stores K and V per head; GQA stores them per KV‑head group: [FlashAttention-2: Faster Attention with Better Parallelism and Work ...](https://hazyresearch.stanford.edu/blog/2023-07-17-flash2) memory ~ `num_kv_heads` instead of `num_query_heads`.   
- This typically reduces **KV cache memory by ~4–16×**, depending on the ratio, and yields ~30–40% faster inference vs full MHA at near‑MHA quality, far better than MQA’s quality tradeoff.   

**Scope**

- Changes the **model’s [The Evolution of FlashAttention | ICLR Blogposts 2026](https://iclr-blogposts.github.io/2026/blog/2026/the-evolution-of-flashattention/)architecture and checkpoints** (you train or uptrain a GQA model).  
- Orthogonal to kernel choice: you can have **“GQA + FlashAttention”** inside each layer and serve it with **PagedAttention**.

---

### 3. PagedAttention (vLLM)

**What it changes**

- PagedAttention is primarily a **serving‑time memory management and attention kernel design** for the **KV cache** in multi‑request batching.  
- It is inspired by **virtual memory paging**: KV cache is stored in fixed‑size “pages” (blocks), and sequences are mapped onto these pages dynamically.   

**Layer implementation / architecture**

- The model’s attention *formula* (MHA, GQA, MQA, etc.) is unchanged; PagedAttention instead defines a **KV cache layout + CUDA kernels** that know how to read from this paged layout.   
- Implemented as part of **vLLM**, an inference engine; today it uses its own optimized multi‑head attention kernels tailored to paged KV caches.   

**Memory optimization**

- Focuses on **GPU memory fragmentation and waste** when many concurrent requests with variable lengths and sampling algorithms are batched together.  
- By paging KV cache and reusing pages, vLLM:
  - Reduces **KV cache waste to <~4%** vs 60–80% in naïve systems.   
  - Enables much larger effective batch sizes → **2–4× (up to ~24× vs basic HF) higher throughput** at similar latency.   

**Scope**

- Strictly an **inference/serving** optimization at the system level.
- Compatible with GQA, MQA, MHA, and (conceptually) with FlashAttention‑style kernels, though current vLLM kernels are custom for paged KV.

---

### 4. How they differ conceptually

| Aspect                        | FlashAttention                  | GQA                               | PagedAttention (vLLM)                     |
|------------------------------|---------------------------------|------------------------------------|-------------------------------------------|
| Level                        | CUDA kernel / op implementation | Model architecture (attention)     | Serving system / KV cache manager         |
| Changes math of attention?   | No (exact attention)            | Yes (head sharing pattern)         | No (same math, different KV layout)       |
| Memory focus                 | Activation & HBM traffic per layer | Size of KV cache per token      | Fragmentation & sharing of KV cache across requests |
| Training vs inference        | Both                            | Both (but helps inference most)    | Inference only                            |
| Requires new checkpoints?    | No                              | Yes (GQA‑trained / uptrained)      | No (works with existing models)           |

In practice for 2024+ LLMs, you [[2307.08691] FlashAttention-2: Faster Attention with Better Parallelism ...](https://arxiv.org/abs/2307.08691)often see **all three combined**:  
a **GQA** architecture to shrink KV cache, **FlashAttention‑style kernels** inside each attention layer for speed and activation savings, and **PagedAttention/vLLM** at serving time for high‑throughput, low‑waste KV cache management.

]

关键信息：  
- FlashAttention 是在 **算子/内核层** 重写注意力计算（分块 + 在线 softmax），不改网络结构，能把注意力的显存复杂度从 O(N²) 降到 O(N)，主要优化单层计算的激活与带宽。  
- GQA 是在 **注意力层结构** 上减少独立 K/V 头数（Query 头分组共享 K/V），在几乎不损失精度的前提下大幅减少 KV cache 大小并加速自回归推理。  
- PagedAttention 是在 **推理系统层** 管理 KV cache 内存（分页 + 共享），减少碎片与浪费，在多请求批处理场景下显著提升吞吐；不改注意力公式，只改 KV 布局与 kernel。  
- 三者互补：同一个模型可以同时用 GQA（结构）、FlashAttention（核实现）、PagedAttention（服务端内存管理），叠加获得显存和吞吐优化。  

来源：已在回答中标注[Oneflow-Inc/flash-attention-v2 - GitHub](https://github.com/Oneflow-Inc/flash-attention-v2)[FlashAttention-2 Faster Attention with Better Parallelism and Work ...](https://tridao.me/publications/flash2/flash2.pdf)

---

## 📚 Sources

1. [FlashAttention-2: Faster Attention with Better Parallelism and Work ...](https://hazyresearch.stanford.edu/blog/2023-07-17-flash2)
2. [The Evolution of FlashAttention | ICLR Blogposts 2026](https://iclr-blogposts.github.io/2026/blog/2026/the-evolution-of-flashattention/)
3. [[2307.08691] FlashAttention-2: Faster Attention with Better Parallelism ...](https://arxiv.org/abs/2307.08691)
4. [Oneflow-Inc/flash-attention-v2 - GitHub](https://github.com/Oneflow-Inc/flash-attention-v2)
5. [FlashAttention-2 Faster Attention with Better Parallelism and Work ...](https://tridao.me/publications/flash2/flash2.pdf)