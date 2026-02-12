# LLM 训练并行策略详解：DP、TP、PP 与 ZeRO

> **一份图解驱动的分布式并行策略综合指南，涵盖大语言模型训练与推理的四大并行策略。**

本指南以清晰的图表和对比，系统解释 LLM 训练与推理中使用的四大并行策略。重点回答一个最常被混淆的问题：*TP、PP 和 ZeRO 各自到底切分了什么，它们之间有什么本质区别？*

## 目录

- [全局概览](#全局概览)
- [数据并行 (DP)](#数据并行-dp)
- [张量并行 (TP)](#张量并行-tp)
- [流水线并行 (PP)](#流水线并行-pp)
- [ZeRO (零冗余优化器)](#zero-零冗余优化器)
  - [ZeRO Stage 1：优化器状态分区](#zero-stage-1优化器状态分区)
  - [ZeRO Stage 2：+ 梯度分区](#zero-stage-2-梯度分区)
  - [ZeRO Stage 3：+ 参数分区](#zero-stage-3-参数分区)
- [核心区别：TP vs ZeRO](#核心区别tp-vs-zero)
- [3D 并行：TP × PP × DP](#3d-并行tp--pp--dp)
- [通信模式对比](#通信模式对比)
- [训练 vs 推理：不同的优先级](#训练-vs-推理不同的优先级)
- [决策指南：何时用什么](#决策指南何时用什么)
- [真实案例：训练 Llama-3 405B](#真实案例训练-llama-3-405b)
- [参考资料](#参考资料)

---

## 全局概览

所有并行策略解决的都是同一个根本问题：**单块 GPU 没有足够的显存或算力来处理大型模型**。但它们从不同角度来解决：

![Parallelism Overview](images/parallelism_overview.png)

| 策略 | 切分对象 | 每块 GPU 处理 | 通信方式 |
|------|---------|-------------|---------|
| **DP** (数据并行) | **数据批次** | 不同数据，完整模型 | AllReduce 梯度 |
| **TP** (张量并行) | 每层的**权重矩阵** | 相同数据，部分权重 | 每层 AllReduce |
| **PP** (流水线并行) | 跨阶段的**层组** | 相同数据，部分层（完整权重） | 边界处 P2P 激活值 |
| **ZeRO** | **模型状态** (W/G/OS) 的存储 | 不同数据，重建后的完整权重 | 计算前 AllGather |

**核心洞察**：TP 和 PP 切分的是**模型如何计算**（模型并行）。ZeRO 切分的是**模型如何存储**（数据并行之上的显存优化）。

---

## 数据并行 (DP)

**核心思想**：在每块 GPU 上复制完整模型。每块 GPU 处理训练数据的不同切片。

### 工作原理

```
全局批次 = [B0, B1, B2, B3]   (例如 1024 个样本)

GPU 0: 完整模型副本 → 处理 B0 (256 样本) → 本地梯度 G0
GPU 1: 完整模型副本 → 处理 B1 (256 样本) → 本地梯度 G1
GPU 2: 完整模型副本 → 处理 B2 (256 样本) → 本地梯度 G2
GPU 3: 完整模型副本 → 处理 B3 (256 样本) → 本地梯度 G3

                    ↓ AllReduce ↓
           G_avg = (G0 + G1 + G2 + G3) / 4
                    ↓
           所有 GPU 使用 G_avg 更新参数
```

### 通信模式

- **时机**：反向传播后一次（每个训练步）
- **内容**：梯度的 AllReduce
- **通信量**：每步 2M（M = 模型大小，环形 AllReduce）
- **带宽需求**：中等

### 优缺点

| 优点 | 缺点 |
|------|------|
| 实现简单 | 每块 GPU 必须存完整模型 |
| 不需要修改模型 | 显存效率低下（N 份模型副本） |
| GPU 数量线性加速 | 受限于单卡显存 |
| 适用于任何模型 | 梯度同步可能成为瓶颈 |

### 变体

- **DP** (PyTorch DataParallel)：使用 python 线程，GPU0 作为主节点 → 负载不均衡
- **DDP** (DistributedDataParallel)：多进程，每块 GPU 独立 → 推荐使用
- **FSDP** (Fully Sharded Data Parallel)：PyTorch 的 ZeRO 实现

---

## 张量并行 (TP)

**核心思想**：将每层的权重矩阵切分到多块 GPU 上。每块 GPU 计算**部分结果**，然后同步得到完整输出。

### 工作原理 — MLP 层示例

对于线性层 `Y = XW + b`，权重矩阵 `W ∈ R^{d_in × d_out}`：

```
列并行切分 (TP=2)：

W = [W_left | W_right]     (沿输出维度切分)

GPU 0: Y_left  = X × W_left     → 部分输出
GPU 1: Y_right = X × W_right    → 部分输出

         ↓ AllReduce ↓
    Y_full = concat 或 reduce(Y_left, Y_right)
```

对于多头注意力，切分更加自然，因为注意力头本身就是独立的：

```
32 个头的注意力，TP=2：

GPU 0: 第 0-15 头  → 部分注意力输出
GPU 1: 第 16-31 头 → 部分注意力输出

         ↓ AllReduce ↓
       完整注意力输出
```

### 通信模式

- **时机**：每层（前向和反向都要）
- **内容**：激活值的 AllReduce（每层中间结果）
- **通信量**：非常高（每层都需要通信）
- **带宽需求**：非常高 → **必须使用 NVLink**（300-900 GB/s）

### 为什么 TP 需要 NVLink

一个典型的 Transformer 层需要 **2 次 AllReduce 操作**（MLP 一次，注意力一次）。对于 94 层模型，前向传播就是 **188 次 AllReduce**，反向也是同样数量。如果使用以太网（~25 Gbps），通信开销将远超计算时间。

**经验法则**：TP 只应在 **NVLink 连接的单节点内** 使用。

### 优缺点

| 优点 | 缺点 |
|------|------|
| 按比例减少每卡显存 | 需要极高带宽（NVLink） |
| 每卡计算部分工作 → 更快 | 每层都需要通信 |
| 自然适配注意力头 | 必须修改模型架构 |
| 减少激活值显存 | TP 度数受限于注意力头数量 |

---

## 流水线并行 (PP)

**核心思想**：将**完整的若干层**分配到不同 GPU。数据从第一阶段流向最后阶段，像流水线一样。

### 工作原理

```
94 层模型，PP=2：

GPU 0 (阶段 0): 第 0 ~ 46 层    ← 这些层的完整权重
GPU 1 (阶段 1): 第 47 ~ 93 层   ← 这些层的完整权重

前向：输入 → GPU0 计算 0-46 层 → 发送激活值 → GPU1 计算 47-93 层 → 输出
反向：相同路径反向，发送激活值的梯度
```

### 流水线气泡问题

朴素 PP 同一时刻只有一块 GPU 在工作（巨大浪费）：

```
朴素 PP（无微批次）：

GPU0: [F0 ][    空闲    ][B0 ]
GPU1: [空闲][F1 ][B1 ][空闲]
              ↑ 气泡 ↑
```

**微批次**（GPipe/1F1B 调度）通过将批次拆分为更小的块来缓解：

```
1F1B 调度（4 个微批次）：

GPU0: [F0][F1][F2][F3][B0][B1][B2][B3]
GPU1:     [F0][F1][F2][F3][B0][B1][B2][B3]
              ↑ 更小的气泡 ↑
```

### 通信模式

- **时机**：仅在阶段边界（层组之间）
- **内容**：点对点 (P2P) 发送/接收激活值
- **通信量**：低（仅边界层的激活值）
- **带宽需求**：低 → **以太网即可**

### 优缺点

| 优点 | 缺点 |
|------|------|
| 通信开销低 | 流水线气泡（空闲时间） |
| 可用于低带宽链路（以太网） | 增加单请求延迟 |
| 每卡持有完整的层 | 跨阶段负载均衡 |
| 无需修改模型架构 | 微批次增加复杂性 |

### PP 在训练与推理中的区别

| 方面 | 训练 | 推理 |
|------|------|------|
| **微批次效果** | 填充气泡（独立样本） | 仅帮助吞吐量（token 是顺序的） |
| **气泡影响** | 通过 1F1B 调度减少 | 单请求延迟不可避免 |
| **使用时机** | 单节点放不下模型时 | 单卡放不下模型时 |

---

## ZeRO (零冗余优化器)

**核心思想**：在标准 DP 中，每块 GPU 冗余存储模型参数 (W)、梯度 (G) 和优化器状态 (OS) 的完整副本。ZeRO **分区存储**这些状态到不同 GPU，在需要计算时**按需重建**。

> **ZeRO 不是模型并行。它是显存优化的数据并行。** 每块 GPU 仍然处理不同的数据批次，使用完整模型权重计算 — 只是不会*一直存储*所有东西。

![ZeRO Stages](images/zero_stages.png)

### 显存分析（FP16 模型 + Adam 优化器）

对于 M 个参数的模型：

| 组件 | 每参数显存 | M 个参数总量 |
|------|----------|------------|
| 参数 (W) FP16 | 2 字节 | 2M |
| 梯度 (G) FP16 | 2 字节 | 2M |
| Adam 优化器状态 | 12 字节 (FP32 W 副本 + 动量 + 方差) | 12M |
| **总计** | **16 字节** | **16M** |

标准 DP 在 N 块 GPU 上：**每卡存储 16M** → 总显存 = 16M × N（巨大浪费！）

### ZeRO Stage 1：优化器状态分区

**分区内容**：仅优化器状态 (OS)

```
4 块 GPU，模型 M：

GPU 0: W (完整 2M) + G (完整 2M) + OS_0 (3M)     = 7M 字节
GPU 1: W (完整 2M) + G (完整 2M) + OS_1 (3M)     = 7M 字节
GPU 2: W (完整 2M) + G (完整 2M) + OS_2 (3M)     = 7M 字节
GPU 3: W (完整 2M) + G (完整 2M) + OS_3 (3M)     = 7M 字节

对比标准 DP：每卡 16M → Stage 1 节省约 56% 显存
```

**通信**：与 DDP 相同（AllReduce 梯度）+ AllGather 获取更新后的参数

### ZeRO Stage 2：+ 梯度分区

**分区内容**：优化器状态 + 梯度

```
4 块 GPU，模型 M：

GPU 0: W (完整 2M) + G_0 (0.5M) + OS_0 (3M)      = 5.5M 字节
GPU 1: W (完整 2M) + G_1 (0.5M) + OS_1 (3M)      = 5.5M 字节

对比标准 DP：每卡 16M → Stage 2 节省约 66% 显存
```

**通信**：用 Reduce-Scatter 替代 AllReduce（每卡获取自己的梯度分片）

### ZeRO Stage 3：+ 参数分区

**分区内容**：优化器状态 + 梯度 + 参数（所有内容！）

```
4 块 GPU，模型 M：

GPU 0: W_0 (0.5M) + G_0 (0.5M) + OS_0 (3M)       = 4M 字节
GPU 1: W_1 (0.5M) + G_1 (0.5M) + OS_1 (3M)       = 4M 字节

对比标准 DP：每卡 16M → Stage 3 节省约 75% 显存
```

**通信**：All-Gather（每层前向/反向前收集完整 W）+ Reduce-Scatter（分发梯度）

**ZeRO-3 前向传播流程**：
```
对于每层 L：
  1. All-Gather：从所有 GPU 分片重建层 L 的完整 W
  2. 计算：Y = f(X, W_full)     ← 与单卡计算完全相同！
  3. 丢弃：释放收集到的 W（仅保留自己的分片）
  4. 处理下一层
```

---

## 核心区别：TP vs ZeRO

这是**最容易被混淆的点**。TP 和 ZeRO-3 都把权重切分到多卡。但计算模型有本质区别：

![TP vs ZeRO](images/tp_vs_zero.png)

| 方面 | 张量并行 (TP) | ZeRO Stage 3 |
|------|-------------|--------------|
| **切分方式** | 每层内的权重矩阵 | 用于存储的权重分片 |
| **计算时** | 每卡使用**部分权重** | 每卡重建并使用**完整权重** |
| **处理的数据** | TP 组内**相同数据** | 每卡**不同数据**（数据并行） |
| **通信类型** | AllReduce（每层，合并部分结果） | All-Gather（每层，重建权重） |
| **需要修改模型** | 需要（切分 Linear、Attention） | 不需要 |
| **本质** | **模型并行** | **显存优化的数据并行** |
| **类比** | 工人各造汽车的**一部分**，然后组装 | 工人各自**借来全套工具**，造自己的车，用完归还 |

### 为什么这很重要

1. **TP 减少每卡计算量**（每卡做部分矩阵乘法）→ 有利于降低延迟
2. **ZeRO 不减少计算量**（每卡做完整矩阵乘法）→ 延迟与单卡相同
3. **TP 需要高带宽**（每层都要同步）→ 需要 NVLink
4. **ZeRO 的 All-Gather 可以预取**（与计算重叠）→ 更灵活

---

## 3D 并行：TP × PP × DP

训练最大的模型（100B+）时，单一并行策略不够。**3D 并行**组合使用三种策略：

![3D Parallelism](images/3d_parallelism.png)

### 如何组合

```
总 GPU 数 = TP_size × PP_size × DP_size

示例：8 块 GPU，TP=2, PP=2, DP=2

                    DP Rank 0                    DP Rank 1
              ┌────────────────────┐      ┌────────────────────┐
PP 阶段 0     │ GPU0(TP0) GPU1(TP1)│      │ GPU4(TP0) GPU5(TP1)│
(第 0-46 层)  │  ←── NVLink ──→   │      │  ←── NVLink ──→   │
              ├────────────────────┤      ├────────────────────┤
PP 阶段 1     │ GPU2(TP0) GPU3(TP1)│      │ GPU6(TP0) GPU7(TP1)│
(第 47-93 层) │  ←── NVLink ──→   │      │  ←── NVLink ──→   │
              └────────────────────┘      └────────────────────┘
                         ↕ AllReduce 梯度 (DP) ↕
```

### 通信层次

| 维度 | 带宽需求 | 典型互联 | 通信方式 |
|------|---------|---------|---------|
| **TP**（节点内） | 最高 | NVLink (600-900 GB/s) | 每层 AllReduce |
| **PP**（跨节点） | 低 | 以太网 (10-100 Gbps) | 阶段边界 P2P |
| **DP**（跨副本） | 中等 | 以太网/InfiniBand | 每步 AllReduce 梯度 |

### ZeRO + 3D 并行

ZeRO 与 PP+TP 组合时：
- **ZeRO-1**（优化器分片）与 PP+TP 配合良好
- **ZeRO-2**（+ 梯度分片）与 PP 组合有性能问题，因为每个微批次需要额外的 Reduce-Scatter
- **ZeRO-3**（+ 参数分片）通常不与 PP/TP 组合使用（冗余且增加通信）

---

## 通信模式对比

| 并行策略 | 集合通信操作 | 时机 | 每步通信量 | 能否与计算重叠？ |
|---------|-----------|------|----------|--------------|
| **DP/DDP** | AllReduce | 反向传播后 | 2M (环形) | 是（梯度桶化） |
| **TP** | AllReduce | 每层 (前向+反向) | 2 × L × 激活值大小 | 否（在关键路径上） |
| **PP** | P2P Send/Recv | 阶段边界 | 边界层激活值大小 | 部分（1F1B） |
| **ZeRO-1** | AllGather + ReduceScatter | 优化器步骤 | M | 是 |
| **ZeRO-2** | ReduceScatter | 反向传播后 | M | 是 |
| **ZeRO-3** | AllGather + ReduceScatter | 每层 (前向+反向) | 总计 3M (前向 AG + 反向 AG + 反向 RS) | 是（预取） |

其中：M = 模型大小，L = 层数。

---

## 训练 vs 推理：不同的优先级

| 方面 | 训练 | 推理 |
|------|------|------|
| **首要目标** | 最大化吞吐量 (样本/秒) | 最小化延迟 (毫秒/token) |
| **并行优先级** | DP > TP > PP | TP > PP > DP |
| **为什么训练偏好 DP** | 通信最少，线性扩展 | 不适用（单个输入） |
| **为什么推理偏好 TP** | — | 减少每卡计算量，降低延迟 |
| **ZeRO 相关性** | 非常有用（节省显存用于更大批次） | ZeRO-Inference 存在但不常用 |
| **PP 权衡** | 可接受的气泡，微批次有帮助 | 增加延迟（每个 token 都有气泡） |

### 为什么训练偏好 DP

- 每卡处理独立数据 → 最少通信（只需最后同步梯度）
- 通信可与反向计算重叠（梯度桶化）
- 线性吞吐量扩展：2× GPU ≈ 2× 吞吐量

### 为什么推理偏好 TP

- 单请求 → 无法切分数据（DP 无收益）
- TP 减少每卡计算量 → 更低延迟
- NVLink 带宽高效处理每层 AllReduce

---

## 决策指南：何时用什么

### 模型能放进单卡
```
→ 训练用 DDP（数据并行）
→ 推理用单卡
```

### 模型放不进单卡

**单节点（有 NVLink）**：
```
→ 训练：优先 TP，需要时加 ZeRO-1/2
→ 推理：TP（度数 = GPU 数量）
```

**多节点（节点间以太网）**：
```
→ 训练：节点内 TP + 跨节点 PP + DP 扩展
→ 推理：节点内 TP + 跨节点 PP
```

**显存仍不够**：
```
→ 加 ZeRO-3（注意：Stage 3 通信量大）
→ 考虑 ZeRO-Offload（卸载到 CPU/NVMe）
```

### 快速决策表

| 场景 | 推荐策略 |
|------|---------|
| 7B 模型，1 节点 8×H100 | DDP（训练）/ TP=1（推理） |
| 70B 模型，1 节点 8×H100 | TP=8（推理）/ TP=8 + ZeRO-1（训练） |
| 70B 模型，2 节点 4×H100 | TP=4 + PP=2 |
| 405B 模型，8 节点 8×H100 | TP=8 + PP=4 + DP=2 |
| 405B 模型，192 节点 8×H100 | TP=8 + PP=4 + DP=48（Llama-3 实际配置） |

---

## 真实案例：训练 Llama-3 405B

Meta 的 Llama-3 405B 使用 **16,384 块 H100 GPU** 进行 3D 并行训练：

| 维度 | 值 | 详情 |
|------|-----|------|
| **TP** | 8 | 节点内（8×H100 NVSwitch，900 GB/s） |
| **PP** | 4（长上下文扩展时为 16） | 跨 4 个节点构成流水线 |
| **DP** | 512（长上下文扩展时为 128） | 16384 / (8 × 4) = 512 个 DP 副本 |

### 单卡视角

```
总参数量：405B
每 TP 组 (8 块 GPU)：405B（共享，每卡持有每层权重的 1/8）
每 PP 阶段（TP 组处理部分层）：
  - 流水线 4 阶段 → 每阶段约 405B / 4 ≈ 101B 参数
  - TP=8：每卡持有约 101B / 8 ≈ 12.6B 参数
  - FP16：约 12.6B × 2 字节 ≈ 25.2 GB 权重

单卡显存分析：
  参数 (FP16)：        ~7.8 GB
  梯度 (FP16)：        ~7.8 GB
  优化器 (FP32)：      ~23.4 GB (Adam: 3× 参数 FP32)
  激活值 & KV：        ~30-40 GB
  ──────────────────────────────
  总计：               ~70-80 GB / 80 GB H100
```

## 相关资源

本系列其他仓库覆盖特定领域的深入内容：

| 仓库 | 聚焦 |
|------|------|
| [Deep-Speed-ZeRO-Policy](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Deep-Speed-ZeRO-Policy) | ZeRO 阶段与 DeepSpeed 深入解析 |
| [NVIDIA-GPU-Distributed-Training](https://github.com/xinyuwei-david/david-share/tree/master/GPUs/NVIDIA-GPU-Distributed-Training) | NCCL 通信内部机制（Ring、Tree、CollNet） |
| [Memory-consumption-in-Training-and-Inference](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference) | 训练和推理的 GPU 显存分析 |
| [How-to-Run-Training-Faster](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/How-to-Run-Training-Faster) | 训练速度优化技术 |
| [Megatron+Deepspeed-Pretrain-GPT2](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Megatron+Deepspeed-Pretrain-GPT2) | Megatron-DeepSpeed 3D 并行实战 |

## 参考资料

- [ZeRO: Memory Optimizations Toward Training Trillion Parameter Models](https://arxiv.org/abs/1910.02054) (Rajbhandari et al., 2019)
- [Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism](https://arxiv.org/abs/1909.08053) (Shoeybi et al., 2019)
- [GPipe: Efficient Training of Giant Neural Networks using Pipeline Parallelism](https://arxiv.org/abs/1811.06965) (Huang et al., 2018)
- [Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM](https://arxiv.org/abs/2104.04473) (Narayanan et al., 2021)
- [DeepSpeed ZeRO++: A leap in speed for LLM and chat model training](https://www.microsoft.com/en-us/research/blog/deepspeed-zero-a-leap-in-speed-for-llm-and-chat-model-training-with-4x-less-communication/) (Microsoft Research, 2023)
- [HuggingFace: Efficient Training on Multiple GPUs](https://huggingface.co/docs/transformers/perf_train_gpu_many)
- [The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783) (Meta, 2024)
