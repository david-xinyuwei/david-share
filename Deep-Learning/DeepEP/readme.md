# 深入解析 DeepSeek DeepEP：如何用极致通信优化加速现代 MoE 模型







**DeepEP = 精确分桶 + 多路 P2P 并发 + 后台 DMA**
在 H100-NVLink3 + IB-NDR400 环境下，只需一行

```
recv, hdl, _ = deep_ep.Buffer.dispatch(...)
```

即可把原本阻塞的 NCCL All-to-All 换成异步 P2P 传输，并与计算深度重叠：
– 训练主路径几乎不再受 NIC 吞吐限制
– 自回归推理（batch = 1，≤2 k ctx）单 token 延迟可低至 **0.4 ms**



也就是说：DeepEP 把一次同步 **NCCL All-to-All** 通信拆成 **同一 kernel 内并发触发的多条 GPU-to-GPU DMA**：
Router 先把 *必须跨卡* 的 token 按目的 GPU **分桶**并 **FP8 压缩**成小包，然后通过 NVLink 或 RDMA 后台直写。

- 传输数据量 60–70 %

- 纯通信往返开销 **< 0.15 ms**

- 单 token 完整推理延迟降至 **0.38–0.45 ms**
  通信几乎不再是 MoE 瓶颈。

  

1. 什么是 bucket？

在 Dispatch 之前，Router 会把「要发往同一目标 GPU 的 token」先收集到一个临时的小袋子里。
这个装同一目的地数据的小袋子，就俗称 **bucket（桶）**。
换句话说：
• bucket→G1 = “准备发给 GPU-1 的那一批 token”
• bucket→G2 = “准备发给 GPU-2 的那一批 token”
……

举例场景中一共有 4 块 GPU（GPU-0 … GPU-3）。
Router-0 把自己手里的所有 token 逐个查看后，发现它们需要的专家分布在 4 块 GPU 上，于是就分出了 4 个桶：

```
bucket→G0  bucket→G1  bucket→G2  bucket→G3
```

这样做的好处：一旦进入通信层（all-to-all / nvshmem_put），发送方只需把每个桶整体丢给对应的 GPU，对端就能一次性收下属于自己的部分，减少拆包组包开销。



下面是一段**纯举例**的路由结果（方便说明概念，真实数字每个 batch 都会变）：

| token ID | Router 选中的第一专家编号 | 该专家所在 GPU |
| -------- | ------------------------- | -------------- |
| 0        | #12                       | GPU-0 (本地)   |
| 1        | #78                       | GPU-1          |
| 2        | #130                      | GPU-1          |
| …        | …                         | …              |

统计下来也许得到：

- 有 **60 个 token** 选中的专家都在本地 GPU-0
  → 放进 `bucket→G0`，其实留在本地不用真发，图里就写 “(本地60tok)”。
- 有 **20 个 token** 需要去 GPU-1
  → 放进 `bucket→G1 (20tok)`。
- 有 **15 个 token** 需要去 GPU-2
  → 放进 `bucket→G2 (15tok)`。
- 有 **5 个 token** 需要去 GPU-3
  → 放进 `bucket→G3 (5tok)`。

不同 bucket 里的 token 数完全取决于路由打分的结果，所以它们大小不一样很正常。

**小结**

“bucket→G0 (本地60tok)” 这一行只是在示例里告诉你：
Router-0 决定有 60 个 token 要交给 **本机** 的专家，所以放进属于自己 GPU 的 bucket；其余 40 个 token（20+15+5）要发到别的 GPU，于是分成三个小桶分别寄出。

实际运行时，每个 batch、每个 GPU 的 bucket 数量都会动态变化，但流程完全一样。



技术术语：

| 缩写               | 全称                       | 本文语义                              |
| ------------------ | -------------------------- | ------------------------------------- |
| MoE                | Mixture-of-Experts         | 稀疏激活的大模型结构                  |
| Expert             | —                          | 通常是一段两层 MLP (FFN)              |
| Dispatch / Combine | —                          | token→Expert / Expert→token 的通信    |
| FP8                | 8-bit float                | E4M3 或 E5M2，DeepEP 只在链路上传输用 |
| NVLink             | NVIDIA GPU 互连            | ≈ 150 GB/s（Hopper 单向理论）         |
| RDMA               | Remote DMA over InfiniBand | ≈ 35–38 GB/s（400 GbE CX-7 实测）     |
| SM                 | Streaming Multiprocessor   | GPU 里的“核心簇”                      |
| QP                 | Queue Pair                 | RDMA 中的“通信通道”                   |



**DeepSeek的数据类型**

“正向用 FP8、反向梯度用 FP16”是当下几家大模型框架（DeepSpeed、Megatron-LM、NVIDIA Transformer Engine 等）常见的一种 **混合精度训练策略**，核心目的是在**不牺牲精度的前提下进一步压缩显存与带宽**。下面把几件容易混淆的事拆开说明：

1. FP8 是算什么的？
   • 目前工业界主流的 FP8 有两种格式：`E4M3` 和 `E5M2`（分别 4 位或 5 位指数，3/2 位尾数）。
   • 典型使用：
   – **正向权重、激活张量** → FP8 存储 + FP8 TensorCore 计算
   – **梯度张量** → 仍保留 FP16/BF16
   – **优化器状态** → 通常 FP32（Adam m/v）或 8-bit 量化（Adafactor 也有 16-bit 方案）
2. 为什么反向不用 FP8？
   • 梯度分布更尖锐、更容易在极低位宽下溢出 / 欠精度。
   • 业界实测在 GPT-3 / GPT-NeoX 规模上：
   – 正向 FP8 + 反向 FP16 → 收敛曲线与全 FP16/BF16 几乎重合
   – 正反都 FP8 → 需要复杂的 loss-scaling、分段 re-casting 才能收敛，收益不大
3. 硬件要求
   • **A100（Ampere）**：TensorCore 支持 FP16/BF16/TF32/INT8，但不支持原生 FP8；想用 FP8 只能在 CUDA 里做软件 emulation，几乎没加速效果。
   • **H100（Hopper）/GH200**：原生 FP8 TensorCore，峰值 4 PFLOPS（FP8, 2:1）；所以大多数“FP8 正向”案例默认你手里是 H100。
   • **其他加速器**：例如 AMD MI300A 支持 FP8 (E4M3)，但生态仍在补。所以如果你用的是 **“FP16 加速器”**（如 A100），就算代码里写了 FP8，最终也会 fallback 到 FP16 路径，既得不到速度，也得不到显存节省。
4. DeepSeek / DeepSpeed / Transformer Engine 的差异
   • 如果你指的是 **DeepSpeed**（微软开源框架），它的 **FP8 training** 模块就是“正向 FP8 / 反向 FP16”。
   • **DeepSeek**（非微软、做检索/模型开源的那个团队）目前公开 repo 里并没有 FP8 训练代码，多数还是 FP16/BF16 混合精度。
   • **NVIDIA Transformer Engine** 则提供了 E4M3/E5M2 的 kernel，实现方式与 DeepSpeed FP8 基本一致。
5. 总结对应关系
   | 流程阶段 | 张量类型 | 建议位宽 | 硬件依赖 |
   | -------- | -------- | -------- | -------- |
   | 正向 | 权重 / 激活 | **FP8** (E4M3/E5M2) | H100/Hopper 必须 |
   | 反向 | 梯度 | **FP16** 或 BF16 | A100 及以上都 OK |
   | 优化器 | m/v, 统计 | FP32 或 8-bit 量化 | 与显卡无关 |

若你正在用 A100 或其他仅支持 FP16 的 GPU，想尝试 FP8，基本只能获得“学术实验”价值；真正的显存/带宽/速度收益须等到手上有 Hopper 级硬件。

## DeepSeek V3/R1推理示意图

我们先看V3/R1 整体架构如下：

``` 
Input Token IDs
      │
      ▼
┌────────────────────────────────────────────────────────┐
│                    Embedding Layer                     │
│  • Token Lookup (vocab → 7168)                         │
│  • Rotary Positional Encoding (RoPE)                   │
└────────────────────────────────────────────────────────┘
      │   (hidden size d = 7168)
      ▼
══════════════════════  Dense Block 1  ══════════════════════
│   Pre-LayerNorm Transformer – “warm-up” layer ①            │
│   Purpose: stabilize features before sparse MoE part       │
│  1. LN-1                                                   │
│  2. Multi-Head Attention   (128 heads)                     │
│  3. Residual Add                                            │
│  4. LN-2                                                   │
│  5. Feed-Forward  Linear → GELU → Linear (dense FFN)       │
│  6. Residual Add                                           │
═════════════════════════════════════════════════════════════
      │
══════════════════════  Dense Block 2  ══════════════════════
│   Same structure as Block 1 – “warm-up” layer ②            │
═════════════════════════════════════════════════════════════
      │
══════════════════════  Dense Block 3  ══════════════════════
│   Same structure as Block 1 – “warm-up” layer ③            │
═════════════════════════════════════════════════════════════
      │
══════════════════════  MoE Block 4  ════════════════════════
│  1. LN-1                                                  │
│  2. Multi-Head Attention  (128 heads)                     │
│  3. Residual Add                                          │
│  4. LN-2                                                  │
│  5. Router / Gate  (Top-8 selection)                      │
│     ├─ Dispatch  →  send token buckets across GPUs        │
│     ├─ Expert Compute:                                    │
│     │    • 1  Shared Expert                               │
│     │    • 256 Routed Experts  (Linear-GELU-Linear)       │
│     └─ Combine  ←  gather outputs back to source GPU      │
│  6. Residual Add                                          │
═════════════════════════════════════════════════════════════
      │
      ▼
……  MoE Block 5  …  MoE Block 61   (58 identical MoE blocks) ……
      │
      ▼
┌────────────────────────────────────────────────────────┐
│                   Final LayerNorm (global)             │
└────────────────────────────────────────────────────────┘
      │
┌────────────────────────────────────────────────────────┐
│     LM Head   (7168 → 129 280 logits, weight-tied)     │
└────────────────────────────────────────────────────────┘
      │
Softmax / Sampling  →  next-token prediction
```

**Key notes:**

1. Dense Block 1-3 are **dense “warm-up” layers**: identical pre-LN Transformer blocks that run full FFN to align features before MoE routing starts.
2. MoE Block 4-61 replace the dense FFN with **Router + 1 shared + 256 routed experts**, and add two cross-GPU communications (Dispatch / Combine).
3. Final LayerNorm normalizes the last hidden state; LM Head projects it to vocabulary logits (weights tied with the token embedding).



需要注意的是，模型中两类Head的区别。

1. Multi-Head Attention 里的 “head”

• 出现在 **每一个 Transformer 层的 Attention 子模块** 中。
• 举例：DeepSeek-V3 的自注意力有 128 个 head，它们并行计算不同的注意力子空间，然后再拼在一起。
• 作用：帮助模型从多角度捕捉 token 之间的关系。
• 属于“层内部结构”，每一层都有。

2. LM Head（Language-Model Head）

• 只在 **整条网络的最末端出现一次**。
• 本质就是一个线性投影矩阵：`W ∈ ℝ^{d_model × vocab_size}`
– 把隐藏维度 d=7168 的向量，映射成词表大小 V=129 280 的 logits。
• 作用：把最后得到的语义表示转成“下一个词是谁”的概率分布。
• 通常与 Embedding 权重共享（weight tying），所以天然放在最尾。

简单对照

| 名称           | 位置                      | 数量            | 主要作用                        |
| -------------- | ------------------------- | --------------- | ------------------------------- |
| Attention head | 每层的 Attention 子模块内 | 每层几十~上百个 | 计算多视角注意力                |
| LM Head        | 整个网络结束后            | 仅 1 个         | 把最终隐藏向量投影成词表 logits |

因此：

• “每一层都有 head” 指的是 **Attention head**；
• **LM Head 只有最后一层才需要**，因为只有那时才要输出词概率。
把 LM Head 提前放到中间层既不符合语义，也会破坏模型的梯度与残差结构。

一句话记住

> Attention head ≠ LM Head——前者是层内并行小通道，后者是全网唯一的输出投影。



1个 **MoE Transformer** **Block**的内部实现示意：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepEP/images/1.png)

1. 图里的 T1 / T2 / T3 / T4
   • T1 (Attention) → 这一层的自注意力子模块
   • T2 (Dispatch) → Router + 跨 GPU 发送 token bucket
   • T3 (Expert)  → 被选中专家执行 Linear-GELU-Linear
   • T4 (Combine) → 跨 GPU 把专家输出拉回原 GPU

###### Note:

```
*在 DeepSeek-V3 中*
*• 第 1–3 层是纯 Dense Block，没有 T2/T3/T4。*
*• **从第 4 层开始的 58 个 MoE Block**（4 ~ 61）内部，都可以套用这张 NVIDIA 图的 T1–T4 流水。*
*• 所以这张图“起点”相当于模型进入 **第 4 层** 之后的 任一 MoE 层，并一直重复到第 61 层结束。*
```

DeepEP 把重点火力全部集中在 **T2 Dispatch** 和 **T4 Combine** 这两段跨 GPU 通信环节，围绕“更少数据、更快路径、更好重叠”做了系统级改造；T1（Attention）与 T3（专家 MLP）几乎不改动，仅通过流重叠顺带获益。

下面分三栏把DeepEP优化点对照列清楚：

| T-段            | 传统做法 (NCCL All-to-All)                                   | DeepEP 的做法                                                | 收益                                                    |
| --------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------- |
| T1 Attention    | 本地稠密计算                                                 | **不改**，但通信后台化后 → 计算可与 T2/T4 真正并行           | GPU SM 利用率↑                                          |
| **T2 Dispatch** | • 每层一次 NCCL all_to_all<br>• 先单独 AllGather 头信息<br>• 统一 FP16/BF16 传输 | ① **精确分桶**：Router 只挑“跨卡 token”<br>② **FP8 压缩**：链路带宽占用 ↓ 60-70 %<br>③ **单核多流 DMA**：在同一 kernel 内并行发 NVLink / RDMA P2P<br>④ **Piggy-back header**：把路由头塞进 payload 首 64 B，省掉一次 AllGather | • NVLink/RDMA 实测带宽跑满<br>• 纯发送延迟 < 0.07 ms    |
| T3 Expert MLP   | GPU 本地计算，与通信串行                                     | **不改算法**，但：<br>• 通信核放低优先级 stream → Expert GEMM 与 T2/T4 完全重叠<br>• 可选 SM 配额：通信核仅占 0-24 SM，其余留给 GEMM | Expert 计算时间≈原来，但被前后通信完全掩蔽              |
| **T4 Combine**  | 再跑一次 all_to_all 回收输出                                 | ① **RDMA / NVLink 后台直写**：对端 HCA doorbell 立即 DMA<br>② **Low-lat kernel（解码）**：单 token 即发包，零批量聚合<br>③ **Handle Hook**：只在需要结果前才真正读显存 | • 纯回收延迟 < 0.08 ms<br>• 单 token P99 延迟 ↓ 40-60 % |

**DeepEP 做了什么？**

1. **通信路径改造**：All-to-All → 同步内核里并发触发多条 **P2P DMA**（NVLink + RDMA）。
2. **数据量削减**：只发送跨卡 token，且链路压成 **FP8**；头部随包携带，省一次 AllGather。
3. **极致重叠**：通信核放到低优先级 CUDA stream，配合 Hook + SM 配额，让 T2/T4 完全隐藏在 T1/T3 计算后面。
4. **两套内核**：
   • **normal** —— Prefill & 训练批量大，聚合发包，极限带宽；
   • **low-latency** —— 单 token 解码，即时 doorbell，极限时延。

**结果就是：**
• T2+T4 原本占 60% 以上的瓶颈被压缩到 < 15 %；
• GPU 利用率从 35 % 升至 95 % ；
• 训练吞吐提升 1.5-1.6×，解码单 token 延迟降到 ~0.4 ms。

**DeepEP 把 T2 / T4 这两段“大喇叭”通信，改造成窄而快的“直通水管”，让整条 T1→T4 流水线重新以计算为主而不是等网为主。**



## 为何 MoE 必须率先解决通信

1. **激活稀疏**
   token 仅走 k 个 Expert（k ≪ N_expert）→ 计算省，但 *路由信息* 激增。

2. **All-to-All 两跳**

   ```
   Router
     ├─ Dispatch : 把 token 送到目标 GPU / Expert
     ├─ Expert   : 多 GPU 并行 MLP
     └─ Combine  : 把结果拉回原 GPU
   ```

   

3. **通信成本基准**（Megatron-MoE, H100×8, 8 Expert, BS 4096）

   | 阶段     | NCCL All-to-All | 占总时长 |
   | -------- | --------------- | -------- |
   | Dispatch | 0.42 ms         | 35 %     |
   | Expert   | 0.48 ms         | 40 %     |
   | Combine  | 0.39 ms         | 25 %     |

   → **65 %** 的 step 时间在 *等网*，GPU-util ≈ 35 %。

------

## DeepEP = 专为 Expert-Parallel 打造的通信栈

### 设计目标

| 目标          | 可量化指标                              |
| ------------- | --------------------------------------- |
| 吃满带宽      | NVLink ≥ 150 GB/s；RDMA ≥ 35 GB/s       |
| 最小延迟      | 自回归单 token < 0.4 ms                 |
| 计算-通信重叠 | SM Idle < 5 %                           |
| 精准搬运      | 仅发跨卡 token；FP8 压缩后数据 ↓ ≥ 60 % |
| 易用性        | Python API；handle 自动管理             |

### 两套内核

| 内核            | 主攻方向 | 推荐场景       | 关键特性                     |
| --------------- | -------- | -------------- | ---------------------------- |
| **normal**      | 吞吐     | 训练 / Prefill | 批量聚合；Ring doorbell      |
| **low-latency** | 时延     | 自回归 Decode  | 单包即时 doorbell；SM 占用≈0 |

------

## 架构全貌

```
┌────────────── Python Layer ──────────────┐
│ Router (Top-k)                          │
│ Buffer API (dispatch / combine)         │
│  ├─ get_dispatch_layout()               │
│  └─ low_latency_dispatch()              │
└─▼───────── runtime.cu ── stream & event 管理 ──▲
   │
   ├─ NVLink P2P  (intranode.cu)  ── 自定义 PTX + GPU IPC
   │     • normal & low-lat kernels
   └─ RDMA  P2P  (internode.cu)  ── NVSHMEM_put / get
         • 每 Expert = 一组 QP,  VL0/1 分流
```

T1 / T2 / T3 / T4” 是我们在方案文档里用来描述 **通信距离（或代价）等级** 的抽象分层；
而 “NVLink P2P” 与 “RDMA P2P” 则是落地实现时调用的 **具体链路 & API**。
两套命名可以一一对应——见下表：

| 逻辑层级 | 典型距离 / 代价                                              | 主要链路 & API                                            | 在代码中的实现文件 | 对应关系             |
| -------- | ------------------------------------------------------------ | --------------------------------------------------------- | ------------------ | -------------------- |
| **T1**   | GPU **片内**<br>• 同 SM warp-shuffle / shared-mem<br>• 同卡不同 SM 的 L2 copy | CUDA `__shfl_*`, `memcpy_async`, NCCL P2P within device   | 内核代码自身       | （无外链路，仅片内） |
| **T2**   | **同节点 GPU↔GPU**（机箱里）<br>NVLink 交换矩阵              | NVLink **P2P**<br>自定义 `PTX` / `cudaMemcpyAsync` / NCCL | `intranode.cu`     | NVLink P2P = **T2**  |
| **T3**   | **跨节点**、同机房 TOR 内<br>IB/NDR/HDR 网                   | **RDMA P2P**<br>`NVSHMEM_put/get` 或 ibverbs QP           | `internode.cu`     | RDMA P2P = **T3**    |
| **T4**   | 更远（跨机房 / 跨 Region）<br>需要多跳交换                   | TCP + gRPC / RoCE + RAAI<br>或分层 AllReduce / 参数服务器 | 上层框架（非本库） | T4 需额外组件        |

要点说明

1. T1–T4 是“抽象层级”；NVLink P2P、RDMA P2P 只是其中两级（T2、T3）的**具体实现**。
2. runtime.cu 会根据 `src_gpu` 与 `dst_gpu` 的拓扑关系决定走哪一级：
   • 同主机 → 调 `intranode.cu` (T2)
   • 跨主机 → 调 `internode.cu` (T3)
3. 若训练规模只在单机内，通信永远停留在 T1+T2；集群放大到多机时才会上升到 T3/T4。

因此，“T1 T2 T3 T4” 给的是**抽象概念与性能期望**；
“NVLink P2P / RDMA P2P” 给的是**如何在代码里落地该层级**，两者并不冲突，而是层级→实现的映射关系。

### 数据流 12 步

| #    | Step（操作）                                        | Device / Link      | Purpose / 作用                          | Typical Latency (A100, ≈8 k token) | T-Stage                                       |
| ---- | --------------------------------------------------- | ------------------ | --------------------------------------- | ---------------------------------- | --------------------------------------------- |
| 1    | Kernel 扫 top-k，判定本卡 / 跨卡 token              | GPU                | 找出需跨 GPU 发送的稀疏 token 子集      | 8–12 µs                            | **T1**                                        |
| 2    | `cub::Scan` 生成 prefix-sum offset 表               | GPU                | 计算每个 token 在 send-buf 中的写入偏移 | 0.02–0.08 ms                       | **T1**                                        |
| 3    | `cudaMallocAsync` 精确分配 send-buf（首帧 +3–6 µs） | GPU                | 按总字节数申请显存，避免过分配          | <0.01 ms                           | **T1**                                        |
| 4    | 打包 & FP8 压缩                                     | GPU                | 将跨卡 token 写入 send-buf 并降低位宽   | 0.03–0.10 ms                       | **T1**                                        |
| 5    | 触发 NVLink P2P / RDMA-GDR DMA                      | GPU→DMA            | 把压缩数据直推目标 GPU                  | NVLink≈0.03 ms<br>RDMA≈0.06 ms     | **T2** (同节点)<br>**T3** (跨节点) — Dispatch |
| 6    | Expert MLP 计算（FP8 GEMM）                         | GPU                | 对已路由到本卡的 token 执行前向 GEMM    | 0.20–0.40 ms                       | **T1**                                        |
| 7    | Doorbell 写 flag（NVSHMEM）                         | HCA                | GPU DMA 在对端 QP 置位，通知数据就绪    | overlapped in #6                   | **T2/T3** — Dispatch 末尾                     |
| 8    | Combine 端读取 handle / 偏移                        | GPU                | 读取对端 flag，拿到 recv-buf 基址与长度 | 0.02 ms                            | **T4** — Combine 起点                         |
| 9    | 稀疏 axpy 加权求和                                  | GPU                | 将跨卡结果与本卡结果按权重合并          | 0.05–0.20 ms                       | **T4** — Combine                              |
| 10   | 反向阶段：dispatch / combine 对调                   | GPU                | 在 BP 中执行相同 10 步但方向相反        | 同上                               | Dispatch = **T2/T3**；Combine = **T4**        |
| 11   | Checkpoint Push（可选）                             | GPU → CPU → S3/GCS | 周期性将模型快照写入对象存储            | 1–3 s / GB                         | **T4** (跨 DC，低频)                          |
| 12   | 异地同步 / 灾备复制（可选）                         | WAN TCP / gRPC     | 将最新 ckpt / 日志同步至异地 Region     | 100–300 ms RTT + size              | **T4** (跨 Region，超长距)                    |

说明

1. \#1–10 为 **高频核心路径**，覆盖一次 micro-batch 的 Dispatch 与 Combine，并与示意图中的 T1–T4 一一对应。
2. \#11–12 为 **低频扩展步骤**，仅在需要跨 Region 容灾、冷备或多活部署时启用；不会影响 #1–10 的亚毫秒级性能。
3. 若训练仅限单节点，可忽略 RDMA 分支（T3）与扩展步骤；若需更细的内核级调优，可在 Step 1、4、6 内再做 profiler 级拆分。

#### 内核亮点速览

| 关键词       | 说明                                                         |
| ------------ | ------------------------------------------------------------ |
| PTX 指令     | `ld.global.nc.L1::no_allocate.L2::256B` —— 不污染 L1，256 B 对齐直写 L2→NVLink |
| RDMA 直写    | `nvshmemx_putmem_nbi_block()`；GPU 侧发 WR，无 CPU 轮询      |
| Hook-overlap | `hook()` 在需要结果前才触发 RDMA read，实现双 micro-batch overlap |
| SM 配额      | `Buffer.set_num_sms(24)` → 通信 kernel 仅占 1/6 SM，其余给 GEMM |

------

## 编程模型示例

> 目标：在 **H100/H800 + CUDA ≥ 12.3 + PyTorch ≥ 2.1** 环境下，
> 编译 NVSHMEM → 安装 DeepEP Python 扩展 → 跑通最小示例。
> ​*Ampere (A100) 亦可运行，但 FP8 会自动回退为 FP16，带宽/显存收益约降 20 %。*

### 环境

| 组件          | 版本要求            | 入手方式                         |
| ------------- | ------------------- | -------------------------------- |
| NVIDIA Driver | ≥ 535               | `ubuntu-drivers` 或 NVIDIA 官网  |
| CUDA Toolkit  | ≥ 12.3              | `sudo apt install cuda-12-3`     |
| NCCL          | 与 CUDA 同版        | 随 Toolkit 安装                  |
| NVSHMEM       | **v2.10+** (需 GDR) | 源码编译，见下文                 |
| PyTorch       | ≥ 2.1 (cu12.x)      | `pip install torch==2.1.0+cu121` |
| Python        | 3.8 – 3.11          | 官档或 Conda                     |

### 编译并安装 NVSHMEM

```
# ① 克隆源码
git clone --depth=1 https://github.com/NVIDIA/nvshmem.git
cd nvshmem

# ② 配置 & 编译（启用 GPU-Direct RDMA + GDRCopy）
make -j $(nproc) CUDA_HOME=/usr/local/cuda PREFIX=$HOME/nvshmem \
     NVSHMEM_BUILD_GDRCOPY=1

# ③ 安装到自定义前缀
make install PREFIX=$HOME/nvshmem

# ④ 告知系统库搜索路径
echo 'export NVSHMEM_DIR=$HOME/nvshmem' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=$NVSHMEM_DIR/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

检查安装：

```
ls $NVSHMEM_DIR/lib | grep libnvshmem   # 应看到 libnvshmem_host.so 等文件
```

### 获取并安装 DeepEP

> 假设公司/团队把 DeepEP 托管在 `<org>/deep_ep`；
> 若已发布到 PyPI，请将第 2 步替换为 `pip install deepep`.

```
# ① 克隆仓库
git clone git@github.com:<org>/deep_ep.git
cd deep_ep

# ② 本地开发模式安装（便于调试）
pip install -e .        # 等同于 python setup.py develop
#   或
# pip install .         # 生产环境用正式 install

# ③ 验证 Python 扩展能正确加载 NVSHMEM
python - <<'PY'
import importlib, torch
deep_ep = importlib.import_module("deep_ep")
print("DeepEP version:", deep_ep.__version__)
buf = deep_ep.Buffer(torch.distributed.group.WORLD)  # 不报错即成功
PY
```

### 最小运行示例（单机 8 GPU）

```
#!/usr/bin/env bash
export MASTER_ADDR=127.0.0.1
export MASTER_PORT=29500
WORLD=8

python -m torch.distributed.run \
       --nproc_per_node=$WORLD \
       demo_moe.py               # deep_ep/examples/demo_moe.py
```

`demo_moe.py` 核心片段（FP8 正向 / FP16 反向）：

```
from deep_ep import Buffer, set_global_expert_mlps
import torch, torch.distributed as dist

group = dist.new_group()
buf   = Buffer(group, nvl_bytes=0, rdma_bytes=256<<20)
Buffer.set_num_sms(24)                     # 通信 kernel 占 1/6 SM

def forward(x_fp8, topk_idx):
    recv, hdl, hook = buf.dispatch(x_fp8, topk_idx, num_experts=8)
    y = expert_mlp(recv)                   # 自定义 MLP
    out, _        = buf.combine(y, hdl)
    return out
```

### 常见问题排查

| 现象                                                 | 可能原因                                    | 解决方案                                                  |
| ---------------------------------------------------- | ------------------------------------------- | --------------------------------------------------------- |
| `libnvshmem_host.so: cannot open shared object file` | `LD_LIBRARY_PATH` 未包含 `$NVSHMEM_DIR/lib` | 重新 `source ~/.bashrc`                                   |
| `RuntimeError: FP8 tensor core not supported`        | GPU 为 A100/Ampere                          | 设置 `export DEEP_EP_FORCE_FP16=1` 或升级至 H100          |
| RDMA 吞吐仅 20 GB/s                                  | GDRCopy 未开启 / NIC 不支持 NDR             | 确认 `make` 时 `NVSHMEM_BUILD_GDRCOPY=1`，并升级 HCA 固件 |

### 一键 Docker（可选）

```
FROM nvidia/cuda:12.3.2-devel-ubuntu22.04
RUN apt-get update && apt-get install -y git build-essential python3-pip \
    && pip install torch==2.1.0+cu121 \
    && git clone --depth=1 https://github.com/NVIDIA/nvshmem.git \
    && cd nvshmem && make -j$(nproc) CUDA_HOME=/usr/local/cuda \
         PREFIX=/opt/nvshmem NVSHMEM_BUILD_GDRCOPY=1 \
    && make install PREFIX=/opt/nvshmem \
    && echo "export NVSHMEM_DIR=/opt/nvshmem" >> /etc/profile \
    && echo "export LD_LIBRARY_PATH=\$NVSHMEM_DIR/lib:\$LD_LIBRARY_PATH" >> /etc/profile \
    && git clone https://github.com/<org>/deep_ep.git && cd deep_ep \
    && pip install .
```

完成以上步骤，即可在 **H100/H800**（或 A100、功能降级）上直接调用 `deep_ep.Buffer`、体验“FP8 正向 + FP16 反向” 的 Expert-Parallel 加速效果。



## 性能实测

### 训练吞吐（train-tokens / s / GPU，top-8）

| GPU×Node | Expert | NCCL   | DeepEP     | 提升    |
| -------- | ------ | ------ | ---------- | ------- |
| 8 × 1    | 8      | 190 k  | **300 k**  | ↑ 1.58× |
| 64 × 8   | 64     | 1.46 M | **2.33 M** | ↑ 1.60× |

### 单 token 延迟（Decode，batch = 128）

| Expert | NCCL (ms) | DeepEP-normal | DeepEP-LL | 说明        |
| ------ | --------- | ------------- | --------- | ----------- |
| 8      | 0.78      | 0.52          | **0.38**  | NVLink 内   |
| 256    | 1.23      | 0.74          | **0.45**  | 跨机 + RDMA |

### 火焰图对比（8 GPU）

```
NCCL AllToAll        DeepEP normal
██████ 通信          █ 通信提交
▒▒▒▒▒▒ 计算          ████ 计算
██████ 通信          ░░ 通信后台
```

GPU Idle: **39 % → 4 %**



**Refer to：**

https://github.com/naklecha/llama3-from-scratch?tab=readme-ov-file