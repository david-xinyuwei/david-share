# 分布式训练并行策略：DP、TP、PP、ZeRO 与 NCCL 内幕

> **全面介绍用于大语言模型训练与推理的分布式并行策略，涵盖理论、实现与 GPU 通信内部机制。**

本指南以图表驱动的方式清晰讲解所有主流并行策略、PyTorch/DeepSpeed 实现以及底层 NCCL 通信机制。它回答了最容易混淆的问题：*TP、PP 和 ZeRO 各切分了什么？NCCL 如何协调 GPU？何时该使用哪种策略？*


## 在 Azure 上运行

本项目的所有实验均在 **Azure GPU 虚拟机**上完成。

| 项目 | 详情 |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **框架** | vLLM, DeepSpeed |


## 目录

### 第一部分：并行策略

- [全局概览](#全局概览)
- [数据并行 (DP)](#数据并行-dp)
- [张量并行 (TP)](#张量并行-tp)
- [流水线并行 (PP)](#流水线并行-pp)
- [ZeRO (零冗余优化器)](#zero-零冗余优化器)
- [核心区别：TP vs ZeRO](#核心区别tp-vs-zero)
- [全分片数据并行 (FSDP)](#全分片数据并行-fsdp)
- [专家并行与 MoE](#专家并行与-moe)

### 第二部分：策略组合

- [并行范式分类与混合组合](#并行范式分类与混合组合)
- [3D 并行：TP × PP × DP](#3d-并行tp--pp--dp)
- [通信模式对比](#通信模式对比)
- [训练 vs 推理：不同的优先级](#训练-vs-推理不同的优先级)
- [决策指南：何时使用什么](#决策指南何时使用什么)
- [实际案例：训练 Llama-3 405B](#实际案例训练-llama-3-405b)

### 第三部分：NCCL 与 GPU 通信内幕

- [深度学习架构栈](#深度学习架构栈)
- [多 GPU 训练挑战](#多-gpu-训练挑战)
- [NCCL：角色与架构](#nccl角色与架构)
- [NCCL 集合通信操作](#nccl-集合通信操作)
- [MPI 多节点训练](#mpi-多节点训练)
- [NCCL 启动过程](#nccl-启动过程)
- [NCCL 算法：Ring、Tree、CollNet](#nccl-算法ringtreecollnet)
- [Ring AllReduce 详细步骤](#ring-allreduce-详细步骤)
- [NVLink 优势](#nvlink-优势)
- [NCCL 的"三头十五臂"](#nccl-的三头十五臂)
- [NCCL 协议：LL、LL128、Simple](#nccl-协议llll128simple)
- [DGX Superpod 架构](#dgx-superpod-架构)
- [NCCL 执行与日志分析](#nccl-执行与日志分析)
- [NCCL 环境变量](#nccl-环境变量)
- [NCCL 故障排查](#nccl-故障排查)

### [参考文献](#参考文献)

---

# 第一部分：并行策略

---

## 全局概览

所有并行策略解决的是同一个根本问题：**单个 GPU 没有足够的内存或算力来处理大模型**。但它们从不同角度切入：

![并行策略概览](images/parallelism_overview.png)

| 策略 | 切分对象 | 每个 GPU 处理的内容 | 通信方式 |
|------|---------|-------------------|---------|
| **DP**（数据并行） | **数据批次** | 不同数据，完整模型 | AllReduce 梯度 |
| **TP**（张量并行） | 每层内的**权重矩阵** | 相同数据，部分权重 | 每层 AllReduce |
| **PP**（流水线并行） | 跨阶段的**层组** | 相同数据，完整层（子集） | P2P 激活值传递 |
| **ZeRO** | 用于存储的**模型状态**（W/G/OS） | 不同数据，重建的完整权重 | 计算前 AllGather |

**核心洞察**：TP 和 PP 切分的是**模型如何计算**（模型并行）。ZeRO 切分的是**模型如何存储**（数据并行之上的内存优化）。

数据并行与模型并行的关系可以用图来理解：

![DP 与 MP](images/deepspeed_dp_and_tp.png)

![DP 与 MP 对比](images/deepspeed_mp_dp_comparison.webp)

- **DP** 有较好的计算/通信效率，但内存效率差（每个设备持有完整模型副本）。
- **MP** 有较好的内存效率，但通信效率可能因跨分区同步而受影响。
- **ZeRO-DP** 旨在兼得两者优势：通过分区模型状态（而非像 DP 那样复制它们）来保持内存效率，同时通过动态通信策略保持计算/通信效率。

---

## 数据并行 (DP)

**核心思想**：在每个 GPU 上复制完整模型。每个 GPU 处理训练数据的不同切片。

### 工作原理

```
全局批次 = [B0, B1, B2, B3]   (例如 1024 个样本)

GPU 0: 完整模型副本 → 处理 B0 (256 个样本) → 本地梯度 G0
GPU 1: 完整模型副本 → 处理 B1 (256 个样本) → 本地梯度 G1
GPU 2: 完整模型副本 → 处理 B2 (256 个样本) → 本地梯度 G2
GPU 3: 完整模型副本 → 处理 B3 (256 个样本) → 本地梯度 G3

                    ↓ AllReduce ↓
           G_avg = (G0 + G1 + G2 + G3) / 4
                    ↓
           所有 GPU 用 G_avg 更新参数
```

### 通信模式

- **何时**：反向传播后（每个训练步骤一次）
- **内容**：AllReduce 梯度
- **传输量**：每步 2M（M = 模型大小，ring AllReduce）
- **带宽需求**：中等

### 优缺点

| 优点 | 缺点 |
|------|------|
| 实现简单 | 每个 GPU 必须保存完整模型副本 |
| 无需修改模型 | 内存效率低（N 份模型的副本） |
| GPU 数量线性加速 | 受单 GPU 内存限制 |
| 适用于任何模型 | 梯度同步可能成为瓶颈 |

### 变体

- **DP**（PyTorch DataParallel）：使用 Python 线程，GPU0 为主节点 → 负载不均
- **DDP**（DistributedDataParallel）：多进程，每个 GPU 独立 → 推荐
- **FSDP**（Fully Sharded Data Parallel）：PyTorch 的 ZeRO 实现

![数据并行示意图](images/pytorch_dp_diagram.png)

PyTorch 通过 `torch.nn.DataParallel` 和 `torch.nn.parallel.DistributedDataParallel` (DDP) 提供内建的数据并行支持。DDP 因在多节点环境中具备更好的可扩展性和效率而被推荐使用。

### PyTorch 实现

```python
import torch
import torch.nn as nn
import torch.optim as optim

# 定义模型
model = nn.Linear(10, 1)

# 使用 DataParallel 包装模型
model = nn.DataParallel(model)

# 模型移至 GPU
model = model.cuda()

# 定义损失函数和优化器
criterion = nn.MSELoss()
optimizer = optim.SGD(model.parameters(), lr=0.01)

# 模拟数据
inputs = torch.randn(64, 10).cuda()
targets = torch.randn(64, 1).cuda()

# 前向传播
outputs = model(inputs)
loss = criterion(outputs, targets)

# 反向传播和优化
loss.backward()
optimizer.step()
```

---

## 张量并行 (TP)

**核心思想**：将每个层的权重矩阵拆分到多个 GPU 上。每个 GPU 计算**部分结果**，然后同步得到完整输出。

### 工作原理 — MLP 层示例

对于线性层 `Y = XW + b`，权重矩阵 `W ∈ R^{d_in × d_out}`：

```
列并行拆分（TP=2）：

W = [W_left | W_right]     (沿输出维度拆分)

GPU 0: Y_left  = X × W_left     → 部分输出
GPU 1: Y_right = X × W_right    → 部分输出

         ↓ AllReduce ↓
    Y_full = concat 或 reduce(Y_left, Y_right)
```

对于多头注意力，这更加自然，因为各头本身就是独立的：

```
32 头注意力，TP=2：

GPU 0: 头 0-15  → 部分注意力输出
GPU 1: 头 16-31 → 部分注意力输出

         ↓ AllReduce ↓
       完整注意力输出
```

### 通信模式

- **何时**：每一层（前向和反向）
- **内容**：AllReduce 激活值（每层中间结果）
- **传输量**：非常大（每层都要通信）
- **带宽需求**：非常高 → **需要 NVLink**（300-900 GB/s）

### 为什么 TP 需要 NVLink

典型 Transformer 层需要 **2 次 AllReduce**（MLP 一次，注意力一次）。对于 94 层模型，前向传播就需要 **188 次 AllReduce**，反向传播同理。如果使用以太网（~25 Gbps），通信开销将远超计算时间。

**经验规则**：TP 仅应在 NVLink 连接的**单节点内**使用。

### 优缺点

| 优点 | 缺点 |
|------|------|
| 按比例减少每 GPU 内存 | 需要极高带宽（NVLink） |
| 每个 GPU 计算部分工作 → 更快 | 每层都要通信 |
| 与注意力头天然匹配 | 必须修改模型架构 |
| 减少激活值内存 | TP 度数受注意力头数量限制 |

### 为什么 TP 不切分输入数据

![张量并行示意图](images/pytorch_tp_diagram.png)

在张量并行中，**输入数据通常不会被切分——每个 GPU 处理相同的输入数据**。原因如下：

**1. 模型计算需要完整输入数据**

- **完整性要求**：模型运算，尤其是矩阵乘法，需要完整输入才能正确计算。
- **拆分参数在完整输入上操作**：虽然模型参数被拆分，但仍需操作完整输入数据才能产生正确的中间结果。

**2. 拆分数据会增加通信和复杂度**

- **数据不足**：拆分输入数据意味着每个 GPU 缺少部分输入，缺少计算所需的必要信息。
- **增加通信**：为弥补不足，GPU 之间需要频繁交换数据，增加网络开销和实现复杂度。

**示例说明：**

假设有一个大权重矩阵 `W`，大小为 `[M, N]`，按列拆分到 2 个 GPU：
- **GPU 0**：持有 W 的前半部分 `[M, N/2]`
- **GPU 1**：持有 W 的后半部分 `[M, N/2]`

使用**未拆分的输入** `x [Batch, N]`：
- GPU 0 计算：`y0 = x × W0ᵀ` → 部分输出
- GPU 1 计算：`y1 = x × W1ᵀ` → 部分输出
- 合并：`y = y0 + y1`

如果**拆分输入**（`x_left [Batch, N/2]`，`x_right [Batch, N/2]`）：
- GPU 0 无法计算 `y0 = x × W0ᵀ`，因为 x 的维度与 W0 不匹配——缺少另一半。
- GPU 需要交换输入片段，这就失去了意义。

**结合 TP + DP**：同时扩展模型规模和吞吐量：
- GPU 被分为 DP 组；每组内使用 TP。
- 输入数据在 DP 组间拆分（不在 TP 组内拆分）。

### PyTorch 实现

```python
import torch
import torch.distributed as dist

def tensor_parallel_matmul(a, b, devices):
    # a 按行拆分，b 在各设备间共享
    a_shard = a.chunk(len(devices), dim=0)
    results = []
    for i, dev in enumerate(devices):
        a_device = a_shard[i].to(dev)
        b_device = b.to(dev)
        results.append(torch.matmul(a_device, b_device))
    return torch.cat(results, dim=0)

# 示例用法：
a = torch.randn(1000, 512)
b = torch.randn(512, 256)
devices = ['cuda:0', 'cuda:1']
result = tensor_parallel_matmul(a, b, devices)
```

Megatron-LM 和 DeepSpeed 等框架提供了生产级的 PyTorch 张量并行实现。

---

## 流水线并行 (PP)

**核心思想**：将不同的**完整层组**分配到不同 GPU 上。数据从第一个阶段流过整个流水线到最后一个阶段。

### 工作原理

```
94 层模型，PP=2：

GPU 0（阶段 0）：第 0 ~ 46 层    ← 这些层的完整权重
GPU 1（阶段 1）：第 47 ~ 93 层   ← 这些层的完整权重

前向：输入 → GPU0 计算 0-46 层 → 发送激活值 → GPU1 计算 47-93 层 → 输出
反向：反方向相同路径，发送激活值的梯度
```

### 流水线气泡问题

朴素 PP 中，同一时间只有一个 GPU 活跃（巨大浪费）：

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

- **何时**：仅在阶段边界处（层组之间）
- **内容**：点对点 (P2P) 发送/接收激活值
- **传输量**：低（仅边界层的激活值）
- **带宽需求**：低 → **以太网即可满足**

### 优缺点

| 优点 | 缺点 |
|------|------|
| 通信开销低 | 流水线气泡（空闲时间） |
| 可在低带宽链路上工作（以太网） | 增加单请求延迟 |
| 每个 GPU 持有完整层 | 各阶段负载均衡 |
| 无需修改模型架构 | 微批次增加复杂度 |

### PP 在训练 vs 推理中的差异

| 方面 | 训练 | 推理 |
|------|------|------|
| **微批次收益** | 填充气泡（独立样本） | 仅帮助吞吐量（token 是顺序的） |
| **气泡影响** | 通过 1F1B 调度缓解 | 对单请求延迟不可避免 |
| **何时使用** | 节点无法容纳完整模型时 | 单 GPU 无法容纳模型时 |

### PP 中的梯度同步

| 场景 | 是否需要 AllReduce？ | 说明 |
|------|---------------------|------|
| 单副本流水线 | 否 | 每层仅在 1 个 GPU 上；梯度天然独占 |
| PP + DP（阶段内有副本） | 是 | 同层副本必须同步梯度；与传统 DDP 相同 |
| PP + ZeRO/FSDP 混合 | 是 | 在副本同步基础上额外 Reduce-Scatter / All-Gather |

### 示意图

**纯流水线并行：**

![PP 示意图](images/pytorch_pp_diagram.png)

**流水线并行结合数据并行：**

![PP + DP 示意图](images/pytorch_pp_dp_diagram.png)

### PyTorch 实现

```python
import torch.nn as nn
from torch.distributed.pipeline.sync import Pipe

# 定义模型的两个顺序段
segment1 = nn.Sequential(
    nn.Linear(1024, 2048),
    nn.ReLU(),
    nn.Linear(2048, 2048)
)

segment2 = nn.Sequential(
    nn.Linear(2048, 2048),
    nn.ReLU(),
    nn.Linear(2048, 1024)
)

# 合并两段并用 Pipe 分配到不同设备
model = nn.Sequential(segment1, segment2)
model = Pipe(model, devices=['cuda:0', 'cuda:1'], chunks=4)

# 模拟输入批次
inputs = torch.randn(16, 1024).to('cuda:0')
outputs = model(inputs)
```

---

## ZeRO (零冗余优化器)

**核心思想**：在标准 DP 中，每个 GPU 冗余存储完整的模型参数 (W)、梯度 (G) 和优化器状态 (OS)。ZeRO 将这些**分区**到各 GPU 上以节省内存，同时在需要计算时**按需重建**。

> **ZeRO 不是模型并行。它是内存优化的数据并行。** 每个 GPU 仍然处理不同的数据批次并用完整的模型权重计算——只是不会*一直存储*所有东西。

![ZeRO 阶段](images/zero_stages.png)

### 内存分解（FP16 模型 + Adam 优化器）

对于具有 M 个参数的模型：

| 组件 | 每参数内存 | M 个参数的总量 |
|------|-----------|--------------|
| 参数 (W) FP16 | 2 字节 | 2M |
| 梯度 (G) FP16 | 2 字节 | 2M |
| Adam 优化器状态 | 12 字节（FP32 W 副本 + 动量 + 方差） | 12M |
| **总计** | **16 字节** | **16M** |

标准 DP 在 N 个 GPU 上：**每个 GPU 存储 16M** → 总内存 = 16M × N（巨大浪费！）

![训练内存](images/deepspeed_memory_training.webp)

### ZeRO Stage 1：优化器状态分区

**分区对象**：仅优化器状态 (OS)

```
4 个 GPU，模型 M：

GPU 0: W (完整 2M) + G (完整 2M) + OS_0 (3M)     = 7M 字节
GPU 1: W (完整 2M) + G (完整 2M) + OS_1 (3M)     = 7M 字节
GPU 2: W (完整 2M) + G (完整 2M) + OS_2 (3M)     = 7M 字节
GPU 3: W (完整 2M) + G (完整 2M) + OS_3 (3M)     = 7M 字节

vs. 标准 DP：每 GPU 16M → Stage 1 节省约 56% 内存
```

**通信**：与 DDP 相同（AllReduce 梯度）+ AllGather 更新后的参数

在幕后，ZeRO 将优化器状态分为 N 份。每个设备只负责更新 1/N 的优化器状态和对应的 1/N 参数。每个训练步结束时，通过 all-gather 同步参数。对于混合精度训练，内存需求变为 `4P + 12P/N`，当 N 很大时趋近于 `4P` — 相比标准 DP 的 `16P` 减少了 4 倍。

### ZeRO Stage 2：+ 梯度分区

**分区对象**：优化器状态 + 梯度

```
4 个 GPU，模型 M：

GPU 0: W (完整 2M) + G_0 (0.5M) + OS_0 (3M)      = 5.5M 字节
GPU 1: W (完整 2M) + G_1 (0.5M) + OS_1 (3M)      = 5.5M 字节

vs. 标准 DP：每 GPU 16M → Stage 2 节省约 66% 内存
```

**通信**：用 Reduce-Scatter 替代 AllReduce（每个 GPU 获得其梯度分片）

每个设备在反向传播时只需要 1/N 的梯度。此外，梯度分区一旦被消费就可以释放。内存变为 `2P + (2P + 12P)/N`，当 N 很大时趋近于 `2P` — 减少了 8 倍。

### ZeRO Stage 3：+ 参数分区

**分区对象**：优化器状态 + 梯度 + 参数（所有东西！）

```
4 个 GPU，模型 M：

GPU 0: W_0 (0.5M) + G_0 (0.5M) + OS_0 (3M)       = 4M 字节
GPU 1: W_1 (0.5M) + G_1 (0.5M) + OS_1 (3M)       = 4M 字节

vs. 标准 DP：每 GPU 16M → Stage 3 节省约 75% 内存
```

**通信**：All-Gather（每层前向/反向前收集完整 W）+ Reduce-Scatter（分发梯度）

每个设备只存储 1/N 的参数：每设备 `16P/N`。前向传播通信量为 P（每个设备向 N 个设备广播 P/N），反向传播重复，再加上 P 的梯度 Reduce-Scatter。**总通信量 = 3P**，是经典 DP 的 1.5 倍。

![DeepSpeed ZeRO 架构](images/deepspeed_zero3stage.png)

**ZeRO-3 如何处理前向传播**：
```
对于每一层 L：
  1. All-Gather：从所有 GPU 分片重建完整的 W
  2. 计算：Y = f(X, W_full)     ← 与单 GPU 完全相同的数学！
  3. 丢弃：丢掉收集的 W（只保留自己的分片）
  4. 移至下一层
```

### 为什么 ZeRO 不能分片激活值

虽然 ZeRO 可以分区梯度、优化器状态和参数，但它**不能分片激活值**。这是一个根本区别：

**激活值不能分片的原因：**

1. **激活值是前向传播的中间状态**：每层的激活值依赖于上一层的激活值。它们必须保留在计算设备上，以供反向传播使用。

2. **反向传播依赖激活值**：在反向传播过程中，需要前向传播保存的激活值来计算梯度。将激活值分片到不同设备上需要频繁的设备间数据传输，造成巨大的通信开销，降低训练效率。

**梯度和优化器状态可以分片的原因：**

1. **它们具有全局性**：梯度是损失函数相对于模型参数的偏导数——可以在不同设备上独立计算然后聚合。优化器状态（动量、二阶动量等）是与模型参数相关的辅助变量，可以在不同设备上独立存储和更新。

2. **减少冗余存储**：通过分片和分布梯度与优化器状态，ZeRO 减少了每个设备上的冗余存储。每个设备只需存储和计算一部分，需要时进行全局聚合。

### ZeRO 通信量总结

| 阶段 | 每 GPU 内存 | 每步通信量 | vs. 经典 DP |
|------|-----------|-----------|------------|
| 经典 DP | 16P | 2P | 1× |
| ZeRO-1 (OS) | 4P + 12P/N | 2P | 1× |
| ZeRO-2 (OS+G) | 2P + (2P+12P)/N | 2P | 1× |
| ZeRO-3 (OS+G+P) | 16P/N | 3P | 1.5× |

DeepSpeed ZeRO 仍然是数据并行范式，但在后台消除了模型状态冗余。通信是分布式的：参数仅在需要时才存在于节点上，使用后即丢弃，保持了上述的内存节省。

### DeepSpeed 实现

```python
import torch
import torch.nn as nn
import deepspeed

class LargeModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(LargeModel, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        x = self.relu(self.fc1(x))
        return self.fc2(x)

model = LargeModel(1024, 4096, 10)

ds_config = {
    "train_batch_size": 32,
    "optimizer": {
        "type": "Adam",
        "params": { "lr": 0.001 }
    },
    "zero_optimization": {
        "stage": 2,
        "allgather_partitions": True,
        "reduce_scatter": True,
        "allgather_bucket_size": 2e8,
        "overlap_comm": True
    }
}

model_engine, optimizer, _, _ = deepspeed.initialize(model=model, config=ds_config)
inputs = torch.randn(32, 1024).to(model_engine.local_rank)
outputs = model_engine(inputs)
loss = outputs.mean()
model_engine.backward(loss)
model_engine.step()
```

---

## 核心区别：TP vs ZeRO

这是最容易混淆的点。TP 和 ZeRO-3 都将权重拆分到多个 GPU 上。但计算模型有本质不同：

![TP vs ZeRO](images/tp_vs_zero.png)

| 方面 | 张量并行 (TP) | ZeRO Stage 3 |
|------|-------------|--------------|
| **拆分对象** | 每层内的权重矩阵 | 用于存储的权重分片 |
| **计算时** | 每个 GPU 使用**部分权重** | 每个 GPU 重建并使用**完整权重** |
| **处理的数据** | TP 组内**相同数据** | 每个 GPU **不同数据**（数据并行） |
| **通信类型** | AllReduce（每层，合并部分结果） | All-Gather（每层，重建权重） |
| **模型修改** | 需要（拆分 Linear、Attention） | 不需要 |
| **本质** | **模型并行** | **内存优化的数据并行** |
| **类比** | 工人各造汽车的**一部分**，然后组装 | 工人各**借用全套工具**，造自己的车，归还工具 |

### 为什么这很重要

1. **TP 减少每 GPU 的计算量**（各做部分矩阵乘法）→ 有利于延迟
2. **ZeRO 不减少计算量**（各做完整矩阵乘法）→ 与单 GPU 延迟相同
3. **TP 需要高带宽**（每层都要同步）→ 需要 NVLink
4. **ZeRO 的 All-Gather 可以预取**（与计算重叠）→ 更灵活

---

## 全分片数据并行 (FSDP)

FSDP 是 PyTorch 对 ZeRO-3 概念的原生实现。它通过分片参数、梯度和优化器状态提供最大的内存效率。

### FSDP 工作原理

1. **参数分片**：每个权重张量、梯度张量和优化器状态均匀分为 N 个分片，分布到 N 个 GPU 上。每个 GPU 只存储自己的分片，常驻内存降低到 1/N。

2. **前向传播**：当某层即将计算时，FSDP 使用 **All-Gather** 临时在每个 GPU 上重建完整参数。计算完成后，收集的参数立即释放。

3. **反向传播**：生成完整梯度后，FSDP 立即执行 **Reduce-Scatter** — 同时聚合梯度并将其分发回各自的分片。每个 GPU 仅保留自己的梯度分片。

4. **参数更新**：优化器（如 AdamW）在每个分片上独立进行本地更新。更新后，临时缓冲区被释放，内存恢复到最小的"仅一个分片"状态。

5. **混合精度**（FP16/BF16 + FP32 主权重）：梯度先以低精度参与 Reduce-Scatter，然后在本地累积到 FP32 主权重。如果启用了需要全局 L2 范数的梯度归一化或裁剪，则需要额外的 All-Gather/All-Reduce。

### FSDP 通信逻辑

| 阶段 | 主要通信 | 目的 |
|------|---------|------|
| 前向开始 | **All-Gather 参数分片** | 组装完整权重用于层计算 |
| 反向结束 | **Reduce-Scatter 梯度** | 聚合梯度并分发到分片 |
| （可选）混合精度后处理 | All-Reduce / All-Gather | 梯度归一化、裁剪或其他全局操作 |

> 与传统数据并行相比，FSDP 将"大的 All-Reduce"拆分为"前向 All-Gather + 反向 Reduce-Scatter"。总通信量相同，但峰值内存更低，且可与计算重叠。

---

## 专家并行与 MoE

### 背景与核心概念

1. **稀疏激活**：单次前向传播只路由到 K 个专家（K ≪ M 总专家数），因此计算量与 K 成正比，但模型可以堆叠 M ≫ K 个参数获得更大容量。
2. **并行挑战**：路由 All-to-All 和专家梯度同步需要高带宽；必须与数据并行、张量并行和 ZeRO 结合使用才能扩展。
3. **DeepSpeed** 提供集成的 MoE-Layer、Balanced-Gate、Expert-Parallel 和 ZeRO-3 支持。

### MoE 工作流

| 步骤 | 过程 | 主要通信 |
|------|------|---------|
| ① **门控路由** | 门控为每个 token 产生 Top-K 专家索引 | All-to-All（token 重分配） |
| ② **专家前向** | 被选中的专家独立计算 | 如果专家分布在不同 GPU 则无；如果复制则需参数同步 |
| ③ **专家反向** | 按 token-专家映射反向路由梯度 | All-to-All（与①相同） |
| ④ **梯度同步** | a. 专家权重：同名专家间 All-Reduce<br>b. 非专家权重：DP 组间 All-Reduce | All-Reduce |
| ⑤ **参数更新** | 可叠加 ZeRO/FSDP 进行分片更新 | Reduce-Scatter / All-Gather（ZeRO-3） |

> 步骤①和③中的两次 All-to-All 操作是 MoE 训练中**带宽需求最大**的部分。

### 常见组合

1. **E + D**（最常见）：All-to-All ×2；专家 All-Reduce；骨干 DDP All-Reduce。
2. **E + Z**（内存受限）：对骨干和专家参数都添加 ZeRO-3 分片。
3. **E + D + TP**（100B+ LLM）：骨干使用张量并行；专家使用专家并行。TP P2P/All-Gather + MoE All-to-All。
4. **E + D + Z**（DeepSpeed 推荐）：通信 = E+D All-to-All & All-Reduce + ZeRO-3 Gather/Scatter。

### MoE 示意图

**专家并行结合数据并行 (EP=2, DP=2)：**

![MoE 示意图 1](images/pytorch_moe_1.png)

**专家 + 模型并行 (EP + TP, DP=2)：**

![MoE 示意图 2](images/pytorch_moe_2.png)

**专家并行 + ZeRO (EP=2, DP=2 + ZeRO)：**

![MoE 示意图 3](images/pytorch_moe_3.png)

**完整专家分布 (8 个专家分布在 4 个 GPU 上)：**

![MoE 示意图 4](images/pytorch_moe_4.png)

### DeepSpeed MoE 实现

```python
from deepspeed.moe.layer import MoE
import deepspeed, torch.nn as nn

class MoEBlock(nn.Module):
    def __init__(self, d_model=2048, num_experts=32, k=2):
        super().__init__()
        self.moe = MoE(hidden_size=d_model,
                       expert_group_size=num_experts,
                       k=k,
                       expert_fn=lambda: nn.Linear(d_model, d_model))

    def forward(self, x):
        out, _ = self.moe(x)
        return out

model = MoEBlock()

ds_cfg = {
    "train_batch_size": 64,
    "zero_optimization": { "stage": 2 },
    "moe": {
        "enabled": True,
        "num_experts": 32,
        "k": 2,
        "expert_parallel_size": 8
    }
}

engine, optimizer, _, _ = deepspeed.initialize(model=model, config=ds_cfg)
```

### MoE 关键要点

- **MoE 性能瓶颈通常在 All-to-All 带宽** — 推荐 NVLink / 200 Gb IB 硬件。
- 当专家数量 ≫ GPU 数量时，合理的 `expert_parallel_size` 和 **Balanced-Gate** 设置可以显著减少负载不均。
- 如果内存是瓶颈，优先对骨干做 ZeRO-3；启用稀疏激活的专家层可以先保留完整副本，必要时再分片。

---

# 第二部分：策略组合

---

## 并行范式分类与混合组合

### 并行范式对比

| 范式 | 主要解决的问题 | 前向/路由通信 | 反向/更新通信 | 典型实现 |
|------|-------------|-------------|-------------|---------|
| **D – 数据并行** | 吞吐量 | – | All-Reduce（梯度） | PyTorch DDP |
| **TP – 张量并行** | 单层权重过大 | P2P / All-Gather（激活值） | Reduce-Scatter / All-Reduce | Megatron-LM |
| **PP – 流水线并行** | 深层模型内存；吞吐量提升 | 微批次流式传输；仅激活值跨阶段 | 阶段内 All-Reduce（如有副本） | PyTorch Pipe / DeepSpeed-PP |
| **SP – 序列并行** | 长序列注意力 | All-Gather（跨片 Q/K/V） | Reduce-Scatter / All-Reduce | Megatron-SP |
| **E – 专家并行** | 稀疏高容量 MoE | All-to-All（token → 专家路由） | All-Reduce（同专家梯度） | DeepSpeed-MoE |
| **Z – ZeRO 1/2/3** | 内存优化 | Stage-3：All-Gather（参数分片） | Reduce-Scatter（梯度） | DeepSpeed-ZeRO |

### 常见混合范式

| 组合 | 目标 | 前向/路由通信 | 反向/更新通信 | 典型实现 |
|------|------|-------------|-------------|---------|
| **TP + D** | 宽层 + 吞吐量 | 同 TP | TP 内部 + D 组间梯度 All-Reduce | Megatron-LM |
| **PP + D** | 深层 + 吞吐量 | 微批次流式传输 | 阶段内 All-Reduce | DeepSpeed-PP + DDP |
| **E + D** | MoE + 吞吐量 | All-to-All | 专家 All-Reduce + D 组间 All-Reduce | DeepSpeed-MoE |
| **E + D + Z** | MoE + 内存优化 | All-to-All + 参数 All-Gather | 专家 All-Reduce + ZeRO 通信 | DeepSpeed-ZeRO-MoE |
| **E + D + TP** | 100B+ LLM | TP-P2P + All-to-All | TP Reduce-Scatter + 各自 All-Reduce | Megatron-DeepSpeed |

**关键原则**：只要同一层在多个 GPU 上被"复制"，该副本组内就需要梯度 All-Reduce — 无论使用了哪些其他并行范式（PP、TP、MoE）。

---

## 3D 并行：TP × PP × DP

训练最大的模型（100B+）时，单一并行策略不够。**3D 并行**组合了三种：

![3D 并行](images/3d_parallelism.png)

### 如何组合

```
总 GPU 数 = TP_size × PP_size × DP_size

示例：8 个 GPU，TP=2，PP=2，DP=2

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
| **DP**（跨副本） | 中等 | 以太网/InfiniBand | 每步一次 AllReduce 梯度 |

### ZeRO + 3D 并行

将 ZeRO 与 PP+TP 结合时：
- **ZeRO-1**（优化器分片）与 PP+TP 配合良好
- **ZeRO-2**（+ 梯度分片）与 PP 有性能问题，因为每个微批次需要额外的 Reduce-Scatter
- **ZeRO-3**（+ 参数分片）通常不与 PP/TP 结合（冗余且增加通信）

---

## 通信模式对比

| 并行方式 | 集合操作 | 何时 | 每步传输量 | 可与计算重叠？ |
|---------|---------|------|-----------|-------------|
| **DP/DDP** | AllReduce | 反向传播后 | 2M（ring） | 是（梯度分桶） |
| **TP** | AllReduce | 每层（前向+反向） | 2 × L × 激活值大小 | 否（在关键路径上） |
| **PP** | P2P Send/Recv | 阶段边界 | 边界层激活值大小 | 部分（1F1B） |
| **ZeRO-1** | AllGather + ReduceScatter | 优化器步骤 | M | 是 |
| **ZeRO-2** | ReduceScatter | 反向传播后 | M | 是 |
| **ZeRO-3** | AllGather + ReduceScatter | 每层（前向+反向） | 总共 3M（前向AG + 反向AG + 反向RS） | 是（预取） |

其中：M = 模型大小，L = 层数。

---

## 训练 vs 推理：不同的优先级

| 方面 | 训练 | 推理 |
|------|------|------|
| **主要目标** | 最大化吞吐量（样本/秒） | 最小化延迟（毫秒/token） |
| **并行优先级** | DP > TP > PP | TP > PP > DP |
| **为什么训练首选 DP** | 通信最少，线性扩展 | 不适用（单个输入） |
| **为什么推理首选 TP** | — | 减少每 GPU 计算量，降低延迟 |
| **ZeRO 相关性** | 非常有用（节省内存用于更大批次） | ZeRO-Inference 存在但不常用 |
| **PP 权衡** | 可接受的气泡，微批次有帮助 | 增加延迟（每个 token 的流水线气泡） |

### 为什么训练首选 DP

- 每个 GPU 处理独立数据 → 最小通信（仅在结束时同步梯度）
- 通信可与反向计算重叠（梯度分桶）
- 线性吞吐量扩展：2× GPU ≈ 2× 吞吐量

### 为什么推理首选 TP

- 单个请求 → 无法拆分数据（DP 无收益）
- TP 减少每 GPU 计算量 → 更低延迟
- NVLink 带宽可高效处理每层 AllReduce

---

## 决策指南：何时使用什么

### 模型可放入单个 GPU
```
→ 训练用 DDP（数据并行）
→ 推理用单 GPU
```

### 模型无法放入单个 GPU

**单节点（有 NVLink）**：
```
→ 训练：先用 TP，需要的话加 ZeRO-1/2
→ 推理：TP（度数 = GPU 数量）
```

**多节点（节点间以太网）**：
```
→ 训练：节点内 TP + 跨节点 PP + DP 扩展
→ 推理：节点内 TP + 跨节点 PP
```

**内存仍不足**：
```
→ 添加 ZeRO-3（注意：Stage 3 通信量大）
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

## 实际案例：训练 Llama-3 405B

Meta 的 Llama-3 405B 在 **16,384 个 H100 GPU** 上使用 3D 并行训练：

| 维度 | 值 | 详情 |
|------|-----|------|
| **TP** | 8 | 节点内（8×H100 NVSwitch，900 GB/s） |
| **PP** | 4（上下文扩展时为 16） | 每个流水线跨 4 个节点 |
| **DP** | 512（上下文扩展时为 128） | 16384 / (8 × 4) = 512 个 DP 副本 |

### 每 GPU 视角

```
总参数量：405B
每 TP 组（8 个 GPU）：405B（共享，每个持有每层 1/8 的权重）
每 PP 阶段（TP 组处理部分层）：
  - 流水线有 4 个阶段 → 每阶段约 126B / 4 = ~31.5B 参数
  - TP=8：每 GPU 持有 ~31.5B / 8 = ~3.9B 参数
  - FP16 下：~3.9B × 2 字节 = ~7.8 GB 仅权重

每 GPU 内存分解：
  参数 (FP16):     ~7.8 GB
  梯度 (FP16):      ~7.8 GB
  优化器 (FP32):    ~23.4 GB (Adam: 3× 参数 FP32)
  激活值 & KV:      ~30-40 GB
  ──────────────────────────
  总计:             ~70-80 GB / 80 GB H100
```

---

# 第三部分：NCCL 与 GPU 通信内幕

---

## 深度学习架构栈

深度学习从下到上的架构栈：

```
  +---------------------+
  |        模型         |  ← 模型层（如 Phi3-Vision）
  +---------------------+
            |
            v
  +---------------------+
  |   DeepSpeed/vLLM    |  ← 特定框架（如 vLLM 用于 Transformer 优化）
  +---------------------+
            |
            v
  +---------------------+
  |    Transformer      |  ← 特定神经网络架构
  +---------------------+
            |
            v
  +---------------------+
  |      PyTorch        |  ← 深度学习框架
  +---------------------+
            |
            v
  +---------------------+
  |      Python         |  ← 编程语言
  +---------------------+
            |
            v
  +---------------------+
  |       CUDA          |  ← 底层计算加速库
  +---------------------+
```

---

## 多 GPU 训练挑战

### 算法挑战

- 数据并行还是模型并行
- 同步还是异步
- 大批次影响模型精度
- 预热和学习率调度（线性预热、LARC/LARS...）
- 给梯度加噪声
- 优化器选择（SGD、Momentum、Adam、RMSProp...）
- 速度与精度的平衡

![算法挑战](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sAUbicib5yRvLMzg1nP4szPjsLHhHJs4qcPlrvTXAIWzWKHfhYwic4OcZw/640?wx_fmt=png)

### 工程挑战

- CPU 和 GPU 性能扩展不均衡
- 先 Scale Up（NVLink），再通过网卡 Scale Out
- V100/A100、NVLink、NVSwitch、DGX、10G/25G/100G/200G 的匹配选择
- 混合精度、GPUDirect RDMA（IB/RoCE）
- 将部分 OP 从 CPU 卸载到 GPU（数据预处理、Allreduce）
- 梯度压缩提高通信效率
- 训练框架选择（Horovod、TensorFlow、PaddlePaddle、PyTorch...）
- 分布式 GPU 训练集群的搭建、管理和调度

![工程挑战](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sRPP6gdiaHlop4jvVqBTXebmIrMbeaNtOicQOK8XSJG0Rb9aviba5dMSkA/640?wx_fmt=png)

NCCL 可以解决算法设计中的许多通信挑战。

---

## NCCL：角色与架构

### 单 GPU 训练数据流

单 GPU 训练中，原始数据（图像、音频等）存储在数据库中。梯度用于更新参数，然后与下一批数据结合进行新一轮迭代，重复直到收敛。

![单 GPU 训练](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sXic5LmMOYWw0SgjdMWMNlv6xZPLE9fxUDUASibqSn6ZLS7KrfLJEX3vg/640?wx_fmt=png)

### NCCL 在分布式训练中的角色

在数据并行的分布式训练中，每个 GPU 从自己的数据生成梯度。这些梯度必须合并求和——需要 AllReduce 操作。NCCL 提供高效的并行梯度通信。AllReduce 后，每个 GPU 获得归约后的梯度并更新参数。

![NCCL 分布式](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhq6E1Eyqn1lf6RIbcxLWqE1LwOXSkibQIiahXlA9DZzSsxNu4FuKbnpeQ/640?wx_fmt=png)

NCCL 缓冲区驻留在 GPU 内存中，支持多种网络互联。

### NCCL 在深度学习栈中的位置

NCCL 位于 GPU/CUDA 之上、训练框架之下。它与 cuDNN 和 cuBLAS 并行为深度学习提供库级支持。

![NCCL 位置](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhl3F6Q1HmagxxbJKk8GUgHsEicgWLSJusS59mnUT6v208waQTrtMariag/640?wx_fmt=png)

### NCCL API 结构

NCCL API 分为五类：
1. NCCL Communicator 创建、销毁、容错
2. 同上（生命周期管理）
3. 五种集合操作：AllReduce、AllGather、Broadcast、Reduce、ReduceScatter
4. 点对点操作：send 和 receive
5. 组合/分组操作（合并集合通信）

其中：
- AllReduce = AllGather + ReduceScatter
- Broadcast 和 Reduce 互为逆操作

![NCCL 操作](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhcVwzdicibucXEj4R2azUmMNfBThHURMsicNnyzkJZQMkqk9fPDd780YSQ/640?wx_fmt=png)

![NCCL API](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRh7yzZ4Ry0G2BK7OyoriaicksvYcZrfRdpR3vDIxn9iaAYtCk80vvGONL3w/640?wx_fmt=png)

---

## NCCL 集合通信操作

### Reduce

一个 rank 接收所有 rank 的输入值的归约结果。例如，四个 rank 的四个值求和后发送到根 rank 2。

![Reduce](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1S97tqMTeZXVpfhn42uYjK1mpBCYn7ShfLuicVBSCcia1Xp0AXsAmSGqA/640?wx_fmt=png)

### Broadcast

所有 rank 从一个根 rank 接收数据。

![Broadcast](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1L5K9YIdSQTBMmTIzcAw63yf533YJBpvxt7s7JS7yn3RsNeXLUcl3Og/640?wx_fmt=png)

### AllReduce

每个 rank 接收所有 rank 输入值的归约结果。

![AllReduce](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1t2ia9oSdYO8tguhOsKgjibhuI6r7YF86bUPuDEkMia6ojl6XtZs1zEdTA/640?wx_fmt=png)

### AllGather

每个 rank 接收所有 rank 的聚合数据，按 rank 顺序排列。

![AllGather](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1cJUHRLj9K9kibgyibMd3ykibxDlYHQ7RwUNxlClILAvn8CL3hTC2SnsSg/640?wx_fmt=png)

### ReduceScatter

输入值在各 rank 间归约，每个 rank 接收归约结果的一部分。

![ReduceScatter](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1CyKCvaEKoVmxG950rUZ9vq8prlp6RiatssG1bEmuI08FLVPUcljSB4w/640?wx_fmt=png)

### 点对点操作

- **Send/Receive**：一对一通信
- **Gather**：多对一
- **Scatter**：一对多

![P2P 操作](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1o6J3Azm063bFibrCwWh7riaOsaHq5kwjplxS56gueDX1DcSHf0XRVL2g/640?wx_fmt=png)

![Gather](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1xEveo90ofk1Xy1LiaF9hToLENTG0bLfbjJOxx24icv3lbNico401fE1FA/640?wx_fmt=png)

![Scatter](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1zicyzrxxECD0OFuxuZA4vH18SPbEfFenwMEU10nwCkw96FibIFV4VbibA/640?wx_fmt=png)

![All-to-All](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1aH2cYLoicMNwT62yBYMKx3GGDyModcFTXy758mUYBnN2sKV9IgFw7Kw/640?wx_fmt=png)

---

## MPI 多节点训练

### 分布式 GPU 作业的前提条件

1. 硬件：计算服务器、网络
2. 代码：并行划分和实现
3. MPI：用于跨节点启动多进程作业、消息传递
4. 免密 SSH 访问
5. 统一用户信息（UID/GID）
6. 统一文件系统
7. 统一软件栈（跨节点一致的 NCCL 和 CUDA 版本）
8. `mpicc` 用于代码编译
9. 启动：`mpirun -np 16 -H node1:8,node2:8 ./application`

### 两种启动方式

**方式 1：MPI**

MPI（消息传递接口）是经典的并行任务执行方法，在 HPC 中使用了数十年。它有 6 个基本函数：

![MPI 函数](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s3ibmQQswsX3naPpFb5Wnx6sFuiahMHc8VAnibicltuMHE46OmZKlOE1euQ/640?wx_fmt=png)

MPI 需要节点间免密 SSH，从单个节点启动。`-H` 标志指定计算节点和进程数。

**方式 2：IP + Port (torchrun)**

这种方式更简单，不需要免密 SSH。只需在每个节点指定 master IP 和端口：

```bash
# 在节点 1
NCCL_DEBUG=INFO python -m torch.distributed.launch --nproc_per_node=8 --nnodes=2 \
    --node_rank=0 --master_addr="192.168.1.1" --master_port=12355 train.py

# 在节点 2
NCCL_DEBUG=INFO python -m torch.distributed.launch --nproc_per_node=8 --nnodes=2 \
    --node_rank=1 --master_addr="192.168.1.1" --master_port=12355 train.py
```

### NCCL vs MPI

NCCL（NVIDIA 集合通信库）处理服务器内优化的 GPU 到 GPU 通信。MPI 处理跨服务器的任务调度。当 NGC 用 MPI 启动测试时，底层通信使用 NCCL。MPI 只负责进程管理和启动。

![NCCL vs MPI](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sVmqmTJHQ8cibGzpjiczGNe9Z0ICCn6WNdib4Nic7v7XNj4LMjT1nwKicgcg/640?wx_fmt=png)

### GPUDirect RDMA (GDR)

跨节点 MPI 使用 GDR 时需要 NV_PEER_MEM。该模块加载在每个节点上。使用 GDR 时，GPU 和网卡必须在同一 PCIe 根复合体下——如果距离太远，性能可能反而下降。DGX1 和 DGX A100 需要 GPU 和网卡在同一 PCIe 交换机下。

![GDR 性能](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4svZb9Ax2rZJ0zic6Dc8icLibpLMrlnYW46gSqYuJd1SRMnBRy62AicUwTQw/640?wx_fmt=png)

---

## NCCL 启动过程

NCCL 有两种启动模式：

**模式 1：仅在 Worker 0 上启动**

NCCL 首先生成一个根线程，该线程向 NCCL 提供端口和 IP，然后 NCCL 广播给所有 rank。

![启动模式 1](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sUzdeJ0vC9ouFx2MIaQf2qeJDdS7ibxH9JMbvDzeiak8s29KBJXPC8e6A/640?wx_fmt=png)

**模式 2：在所有并行 worker 上启动**

在此模式下，NCCL 在每个 worker 上独立初始化 rank，然后将 rank 的 IP 和端口传递给引导根线程。

![启动模式 2](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sEK52IjnHE4IBV6OYZA3h9n5zS1GrBWuWBM9mNnm6U246OMTs6y8vOg/640?wx_fmt=png)

所有 rank 随后交换信息以形成 ring 或 tree 拓扑：

![拓扑形成](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sHO6EkAmKcZH9q3YKgVRZXia4MYLyr1J975dS6Y1dibQHVG0WpGc4NYBw/640?wx_fmt=png)

### NCCL Bootstrap

NCCL Bootstrap 使用 TCP/IP socket 连接作业中的各个 rank，提供带外通道用于信息交换。Bootstrap 操作在 NCCL communicator 的整个生命周期中可用，主要在初始化和动态 send/recv 连接建立时使用。当前没有加密或安全措施。使用 `NCCL_SOCKET_IFNAME` 确保 NCCL 使用私有网络接口。

### NCCL 的四个工作步骤

1. **拓扑检测** — 构建完整的 GPU 集群拓扑
2. **图搜索** — 找到最优通信架构（ring 或 tree）
3. **图连接** — 使用 PCI、NVLink 或 GDR 连接跨节点 GPU
4. **CUDA 内核** — 优化归约和拷贝，最小化 SM 使用

![NCCL 步骤](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRh7aewNj20GTRx4EsNpyK4GuFTVjYYziafDiaicjFzic7VGPNDKE40Fqjaxg/640?wx_fmt=png)

**步骤 1：拓扑发现**

NCCL 发现：IB、NVLink、NVLink Switch 互联（包括 NVLink 到 CPU，如 Power9 和 Grace CPU）。VM 配置包括链路带宽信息也会被检测。

![拓扑发现](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhQwgdx0x29yEa36z8gCZ8doEGQMH6ianVZtPAicUzCiaZkh2psekpjv93w/640?wx_fmt=png)

**步骤 2：图生成**

拓扑发现后，NCCL 生成图。NCCL 默认计算不同的模型，根据硬件、网络条件和节点数估计延迟，然后选择最快的选项。Ring 有更高的带宽；Tree 有更低的延迟。

![图类型](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4svZo1dkCaXd7ANoCDEWiaGJibibostPXo3EFmUxpQQ989lknFUOwjwZtbQ/640?wx_fmt=png)

**步骤 3：图连接**

集合通信通过 GPU 内核建立。NCCL 使用写操作（更高效）。连接使用 PCI、NVLink 或 GDR。

![图连接](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sq2Sd2BJnPGKjw0QLC2NgeGwK3fvxyGrx6zbficO4UdyLfH2uicAazCqg/640?wx_fmt=png)

![GDR 缓冲区](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s4xoMicwxJv0LfbrCEfI8lSLvkykojZ6QmIQ5FK37THUUibFXvoEvhicQg/640?wx_fmt=png)

使用 GDR 时，跨节点缓冲区不需要分配在主机内存中——直接使用设备内存。但仍需要 CPU 进程来发起 RDMA 拷贝操作。

---

## NCCL 算法：Ring、Tree、CollNet

NCCL 有三种通信算法：

- **Ring**：更高带宽，但延迟也更高
- **Tree**：更低延迟，但带宽可能不饱和
- **CollNet**：支持网内归约，但需要专用 IB 交换机

### Ring 算法

Ring 更容易达到满带宽。良好的拓扑检测对 Ring 性能至关重要——需要最优的环路径。

![Ring](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHkuV7piaXeicMM34dPQYibOFVn2A0SsR6hXJZorpege1xWrs5TLibLzZNdQ/640?wx_fmt=png)

在传统 ring broadcast 中，数据未分块，总延迟随 GPU 数量线性增长。

![Ring Broadcast](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH0jLvG9hDYm5IEYM5eMbq3eALn8mtFzZb9XibCnONObOWVnGwOckYttg/640?wx_fmt=png)

优化：将数据切分为消息。数据足够大且消息足够多时，节点数变得可以忽略。

![优化后的 Ring](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHBguqNLsBqjveCW8Hy5qVaicfkR3dGSwEtQUcyU4FE2c3z5b4ZOMrpibg/640?wx_fmt=png)

### Tree（双二叉树）

树总是成对使用。树对的目的是确保每个节点的发送/接收平衡。两棵树偏移一个位置，因此大多数节点各发送和接收两次。

![Tree](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHqhK54dpOICQK7iaFSfxRiaL3ewZYMzQQQNRWyQMR3zpDtahEaMe70sNA/640?wx_fmt=png)

### CollNet (SHARP)

CollNet 使用 SHARP 技术——归约在交换机内部完成。

![CollNet](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHFXZBVoQuhN83uibibX0AbxVTIasqx1Mjq8MB5sogKfHzyZGYhfRT7awQ/640?wx_fmt=png)

**SHARP 优势** vs. Tree：发送一次数据，接收最终结果（无中间结果）；有效双倍带宽且更少跳数；更低延迟。

![SHARP vs Tree](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s4CEvZrKJITC2DOuaLLlhu2AVlEYpaLYUibMVnLzInJ1HhHB2Uk9cCxw/640?wx_fmt=png)

### Ring Channel 配置

**节点内：**
- 基于 NVLink 的系统：总是创建双通道以饱和 NVLink 带宽（如 DGX-1V：6×2=12；DGX A100：12×2=24）
- 基于 PCIe 的系统：总是 2 个通道

**节点间：**
- 总是基于网卡数的双通道：2 × 网卡数

![Channel 配置](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1CEZSMgQg7Fs0QG12WVktAnbeiaia5JzgFt11CRyht5T6pdLnfjkklG1A/640?wx_fmt=png)

### Tree 类型

NCCL tree 有三个子类型：

- **Basic Tree**：所有网卡流量流入/流出同一 GPU
- **Balanced Tree**：网卡流量在两个 GPU 间分割（tree parent + 一个 child 在第一个 GPU，第二个 child 在第二个 GPU）
- **Split Tree**：网卡流量在两个 GPU 间分割（tree parent 在第一个 GPU，tree children 在第二个 GPU）

![Tree 类型](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1cwXwobycd1KMZRAwWsS22UbouB2h260IL0ib7CiaxMs4BrPoGicaqnhww/640?wx_fmt=png)

Balanced tree 是最常见的默认选择；Basic tree 仅在 GPU 数量较少时使用。CollNet 取决于交换机支持。

---

## Ring AllReduce 详细步骤

AllReduce 是深度学习分布式训练中最常用的 NCCL 操作。目标是在所有机器间高效归约数据并将结果分发到每台机器。

![AllReduce 目标](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHEzWja9ibEzgFNS5LYdpH3p4Cciau7vWSiam13tnj86ibP9yTxxZtcqiaFtg/640?wx_fmt=png)

### 4 GPU 逐步演示

数据被切分为块以最小化拷贝开销，最大化并发带宽。

![4 GPU 设置](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4spZzpPURXGnUqmhIc9iaT9Xf0RImZ5Q4ib5klo45YMMnIvAibEurnzU3aA/640?wx_fmt=png)

**步骤 1**：每个 GPU 将数据拷贝到环中的下一个 GPU。

![步骤 1](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sKibbYyJ4jK1oZcZoBNnmnw06jt6BQw605HXOt1CHAoPhnMgzXbD58Fw/640?wx_fmt=png)

**步骤 2**：每个 GPU 将接收的数据与自己的数据累加，然后传递给下一个 GPU。

![步骤 2](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sHN1W3cCnJicCfRaziaRqwRqnyJ1ibqMeucIHicmN1YP4GsFPIIuOwcOmAg/640?wx_fmt=png)

**步骤 3**：经过 3 轮通信（4 个 GPU），每个 GPU 都有了其他 3 个 GPU 数据之和。Reduce-Scatter 阶段完成。

![步骤 3](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sOe5AicyNnM1xw2Gy3QWxgwLLLqapqUFSqScp72oY2OwydY0mOKNpeqA/640?wx_fmt=png)

**步骤 4-6**：Broadcast 阶段——每个 GPU 将其完成归约的块发送给下一个 GPU。

![步骤 4](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sT1YBS63dIDxnicqjEjI5m0c9K0y1YKwo1X4uUV0tgt4AsKCkplYLmbw/640?wx_fmt=png)

![步骤 5](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sNCf0ricXRqjeLBmkPIBZ1Mo1bogiaPELsYQ0GniakZu6NSuibC9QlAVv8Q/640?wx_fmt=png)

![步骤 6](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s3eOjrliaIERibl8ImjOHB0ib0ePfbOTibH4WKpDibJamCPsDLLfZH9R0Giaw/640?wx_fmt=png)

**处理剩余块**：对每个数据块重复相同过程。

![块 2a](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sLTk60Xnb1pdfdPYL8YKserDAgdaG4icB4icDCxZ3m1ZxiavgW7K23acPw/640?wx_fmt=png)

![块 2b](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4seHLejlbzV1vTl41uEZlZJuF2XXjN5uIRR6H5icyTHJ9AI01StFcpiadg/640?wx_fmt=png)

**最终结果**：AllReduce 完成——每个 GPU 都有全局归约后的数据。

![AllReduce 完成](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sl4wmLKWmAb9fUahJkCFZPV0Myp5k3HV14CS6m3RNVOsK7gdBV0Qialg/640?wx_fmt=png)

整个过程：Reduce → Scatter → Broadcast。

![AllReduce 时序](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH6wBSgkvlwR9rYZMicia13VXLFuEvoQgbEPIFQ76GmT0LjAxxuIFOpAFA/640?wx_fmt=png)

---

## NVLink 优势

理解 ring 网络的局限性有助于解释为什么 DGX 使用 NVLink 进行数据传输。

### 单节点 NVLink GPU 系统（V100 示例）

两个 NUMA 节点，共 8 个 GPU。每个 GPU 有 6 个 NVLink 连接。总单向带宽：150 GB/s。

![NVLink V100](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH8p6ibOWHvuPoZ2f3dsiaMombolV2ghbiaeUeGKsibV4IlQxcxV4RDHsSFw/640?wx_fmt=png)

### 最佳实践

多 GPU 通信：节点内使用 NVLink，节点间使用 RDMA。

![NVLink + RDMA](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHI2ILofaFtLch4XQLNPI4IM5IrrGk99riaYia3N7faYR1zMAqehwpTRLw/640?wx_fmt=png)

### H100 NVLink Switch

H100 引入了 NVLink Switch 连接，AlltoAll 成为新方向。

![H100 NVSwitch](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHllicI2zzH3icCO5lThF7DNCSQmWzBXh5PsvT535NYE0icYFsFs4WHDbqA/640?wx_fmt=png)

---

## NCCL 的"三头十五臂"

NCCL 可以用三个维度和 15 种实现来描述：

**NCCL 通信函数**（面向业务，如分布式训练中的 AllReduce）：
1. 集合操作：Broadcast、Reduce、AllGather、ReduceScatter、AllReduce
2. 点对点操作：send/recv、scatter、gather、all-to-all

**NCCL 算法**：Ring、Tree、CollNet

**NCCL 协议**：LL、LL128、Simple

在大多数情况下，NCCL 会自动选择最优算法和协议。但理解通信函数对正确使用和配置至关重要。

---

## NCCL 协议：LL、LL128、Simple

- **LL (Low Latency)**：依赖 8 字节原子存储（4B 数据 / 4B 标志）。最大带宽为峰值的 50%，因为 50% 的负载是标志位。
- **LL128**：依赖 128 字节存储按序可见（120B 数据 / 8B 标志）。可达到峰值带宽的 95%。
- **Simple**：无标志位——原始数据传输。

> 标志位表示数据段的尾部已经送达，可以被流水线的下一阶段消费。
> LL128 的性能取决于通信方式（PCI 或 NVLink）和缓冲区位置（GPU 显存或系统内存）。

### 算法 × 协议组合

8 种选择 × 3 种协议 = {Ring, Tree, CollNet} × {LL, LL128, Simple}（CollNet 不支持 LL128）。

NCCL 根据通道数和速度为每种算法构建延迟和带宽模型，然后最优选择：
- **大消息**：Ring 在带宽上最优，但小消息受延迟主导，延迟随规模线性增长。
- **大规模**：Tree 有更好的延迟，但对于非常大的消息，Tree 由于 SM 开销无法达到峰值带宽——因此使用 Ring。

---

## DGX Superpod 架构

DGX Superpod 是 NVIDIA 的 GPU 集群参考架构。逻辑架构分为计算服务器和管理服务器。

![Superpod 逻辑](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s0p0icExPbhaYsTibs3IIFPbtCqxI1x4PMricnDBHzanoRY0rfoupqDwGQ/640?wx_fmt=png)

计算服务器栈：OS → CUDA → RoCE/IB → RDMA → NCCL/MPI。

管理服务器包括：Provisioning Node、Login Node、Monitor Node、Load Balancing Node、UFM Node。

![Superpod 管理](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhTA2hs1zIicRFbRAkn68CeTS29ic2gibY3opxjoLbpoGA7JRrxDBxgMwug/640?wx_fmt=png)

分布式系统要求：
- 免密 SSH、统一文件系统、统一 UID/GID、统一软件栈
- MPI、NCCL、nv_peer_mem、SHARP（可选）
- Slurm 或 K8s 调度器
- MPI + 容器

---

## NCCL 执行与日志分析

### 运行 NCCL 测试

```bash
mpirun -bind-to none -H node1:1,node2:1 \
    -x CUDA_VISIBLE_DEVICES=** \
    -x LD_LIBRARY_PATH \
    -x NCCL_IB_HCA=* \
    -x NCCL_DEBUG=INFO \
    -mca btl_openib_allow_ib true \
    ~/nccl-tests/build/all_reduce_perf -b 8 -e 128M -f2 -g8
```

- `NCCL_IB_HCA`：选择特定 IB 卡进行通信
- `-b 8 -e 128M`：消息大小从 8 字节到 128MB，每步翻倍
- `-g 8`：GPU 数量（可以每 GPU 一个进程或每进程多 GPU）
- `NCCL_SOCKET_IFNAME`：指定用于初始化的以太网卡

### 读取 NCCL 日志

Channel 信息显示生成的 ring 拓扑。NCCL 仅输出前 20 个 rank 的信息。

![NCCL 日志 1](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1aZXyCDrTtfTPEx9guGZCR60K1mTiciceVrJHUY4Ro9rEdts8IaLScvUg/640?wx_fmt=png)

示例：4 个节点，每个 8 个网卡，每个网卡形成 2 棵树 = 共 16 棵树。括号中的树编号 `[0-15]`：

```
NCCL INFO Trees [0] 19/-1/-1->18->17 [1] 19/-1/-1->18->16 ...
```

![NCCL 日志 2](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1ickzDBib5MGmPic4ibr205tSTHWxJrZNK2T8uVRvNeLdmHoxHM85Vibbacw/640?wx_fmt=png)

可视化工具：https://github.com/ROCmSoftwarePlatform/rccl/tree/develop/tools/TopoVisual

![NCCL 拓扑可视化](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1F3jOiblvVJQavzN0p1wvco4iaQy88xb6djFia8bicaP7DF1w3KMJCJuWeQ/640?wx_fmt=png)

### P2P 传输标签

P2P 传输是节点内的：
- **PIX**：连接到同一 PCIe 交换机
- **PXB**：通过多个 PCIe 交换机或 NVLink 连接
- **PHB, NODE, SYS**：跨 NUMA 节点，使用共享内存

### 性能指标

- **algbw**（算法带宽）：不完全代表硬件性能
- **busbw**（总线带宽）：更好地反映实际硬件性能
- **in-place**：发送和接收使用同一缓冲区
- **out-of-place**：发送和接收使用不同缓冲区

![性能指标](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1yu7iaqfcu25hRI7DC1Z4DFOqHdF6KIAP4OREC5BWp7h3Hb1LB9Gz3gA/640?wx_fmt=png)

### NCCL XML 文件

**Graph XML**（`NCCL_GRAPH_DUMP_FILE=graph.xml`）：
- `id="0"`：Ring 信息
- `id="1"`：Tree 信息
- `id="2"`：CollNet 信息
- 每个 channel 包含数据流序列；对于多节点，从网卡输入开始，经过 GPU，到网卡输出。

![Graph XML](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1qibWibibFWCQ8qoDufJ6qtwpNxVPIq0V0qAR5VP60SLKT19CMgNUzgG4w/640?wx_fmt=png)

**Topology XML**（`NCCL_TOPO_DUMP_FILE=topo.xml`）：导出服务器拓扑结构。

这两个文件都可以手动修改并强制加载，但**强烈不推荐这样做**。在绝大多数情况下，这些文件仅供查阅。

### Channel 数量总结

- **无 SHARP**：Ring 和 Tree channels = 2 × 网卡数
- **有 SHARP**：Ring、Tree 和 CollNet channels = 3 × 网卡数

---

## NCCL 环境变量

| 变量 | 用途 |
|------|------|
| **NCCL_SOCKET_IFNAME** | 指定用于通信的 IP 接口 |
| **NCCL_IB_HCA** | 指定 RDMA 接口（如 `mlx5_0:1,mlx5_1:1`，`^mlx5_1:2` 排除） |
| **NCCL_CROSS_NIC** | 控制跨网卡使用（0=同一网卡，1=允许不同，2=偏好相同） |
| **NCCL_IB_GID_INDEX** | RoCE 模式的 GID |
| **NCCL_IB_TC** | InfiniBand 流量类别 |
| **NCCL_COLLNET_ENABLE** | 启用 CollNet 插件 |
| **NCCL_P2P_LEVEL** | P2P 使用阈值（LOC/NVL/PIX/PXB/PHB/SYS，0-5） |
| **NCCL_NET_GDR_LEVEL** | GPU Direct RDMA 阈值（0-5，从禁用到跨 NUMA） |
| **NCCL_MAX_NCHANNELS** | 限制 channel 数量（减少用于通信的 CUDA 块） |
| **NCCL_DEBUG** | 调试输出级别（VERSION、WARN、INFO） |

### NCCL_P2P_LEVEL 详情

| 值 | 含义 |
|-----|------|
| LOC / 0 | 从不使用 P2P（始终禁用） |
| NVL | GPU 通过 NVLink 连接时使用 P2P |
| PIX / 1 | GPU 在同一 PCIe 交换机上时使用 P2P |
| PXB / 2 | GPU 通过 PCIe 交换机连接（多跳）时使用 P2P |
| PHB / 3-4 | GPU 在同一 NUMA 节点内（流量通过 CPU）时使用 P2P |
| SYS / 5 | 跨 NUMA 节点使用 P2P（可能跨 SMP 互联如 QPI/UPI） |

### NCCL_NET_GDR_LEVEL 详情

| 值 | 含义 |
|-----|------|
| 0 | 不使用 GPU Direct RDMA |
| 1 | GPU 和网卡在同一 PCIe 交换机上时使用 GDR |
| 2 | GPU 和网卡通过 PCIe 交换机连接时使用 GDR |
| 3 | GPU 和网卡在同一 PCIe 根复合体下（可能通过 CPU）时使用 GDR |
| 4 | 同一 NUMA 节点内，即使跨 PCIe 根复合体也使用 GDR |
| 5 | 跨 NUMA 节点使用 GDR，包括 SMP 互联 |

---

## NCCL 故障排查

参考：https://docs.nvidia.com/deeplearning/sdk/nccl-developer-guide/docs/troubleshooting.html

### 常见错误类型

- **ncclUnhandledCudaError / ncclSystemError**：外部库调用失败
- **ncclInvalidArgument / ncclInvalidUsage**：使用 NCCL 的应用程序中的编程错误

设置 `NCCL_DEBUG=WARN` 可以在返回错误前获得明确的警告信息。

![故障排查](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1H3qKSjXGR9vicWyvxUNqiaiaeDueia8fD6QdicynZt5tick0pzKcEFuvUgjw/640?wx_fmt=png)

### 调试步骤

1. **验证节点内 GPU-GPU 连通性**：
```bash
cd /usr/local/cuda/samples/1_Utilities/p2pBandwidthLatencyTest
sudo make
./p2pBandwidthLatencyTest
```

2. **验证 Mellanox IB/RoCE 的 GDR**：
```bash
lsmod | grep nv_peer_mem
```

3. **PCI Access Control Services (ACS)**：IO 虚拟化（VT-d / IOMMU）可能将所有 PCI P2P 流量重定向到 CPU 根复合体，导致严重性能下降或挂起。如果遇到性能问题，请禁用 ACS。

4. **拓扑检测**：NCCL 依赖 `/sys` 来发现 GPU PCI 拓扑、速度、CPU 亲和性和网卡。在 VM 或容器中运行时，确保 `/sys` 正确挂载。

5. **网络接口选择**：NCCL 自动检测网络接口。如果某些接口虽然处于 up 状态但无法在节点间通信，NCCL 可能尝试使用它们并失败。使用 `NCCL_SOCKET_IFNAME` 指定正确的接口。

6. **网卡亲和性问题**：NCCL 通常选择距离每个 GPU 最近的网卡。在极端调度情况下（如 server1 的 GPU0 用 mlx5_0，server2 的 GPU7 用 mlx5_7），IPoIB 或 RoCE 配置可能冲突。使用 `NCCL_IB_HCA` 强制指定网卡。

---

## 参考文献

- [ZeRO: Memory Optimizations Toward Training Trillion Parameter Models](https://arxiv.org/abs/1910.02054) (Rajbhandari et al., 2019)
- [Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism](https://arxiv.org/abs/1909.08053) (Shoeybi et al., 2019)
- [GPipe: Efficient Training of Giant Neural Networks using Pipeline Parallelism](https://arxiv.org/abs/1811.06965) (Huang et al., 2018)
- [Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM](https://arxiv.org/abs/2104.04473) (Narayanan et al., 2021)
- [DeepSpeed ZeRO++: A leap in speed for LLM and chat model training](https://www.microsoft.com/en-us/research/blog/deepspeed-zero-a-leap-in-speed-for-llm-and-chat-model-training-with-4x-less-communication/) (Microsoft Research, 2023)
- [HuggingFace: Efficient Training on Multiple GPUs](https://huggingface.co/docs/transformers/perf_train_gpu_many)
- [The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783) (Meta, 2024)
- [ZeRO-DP: Distributed Training for Large Models](https://pub.towardsai.net/deepspeed-zero-dp-distributed-training-for-large-models-20aa1d74d9bb)
- [PyTorch TensorBoard Profiler Tutorial](https://pytorch.org/tutorials/intermediate/tensorboard_profiler_tutorial.html)
- [Training Deep Learning Models at Ultra Scale Using PyTorch](https://medium.com/gitconnected/training-deep-learning-models-at-ultra-scale-using-pytorch-74c6cbaa814b)
- [Technologies Behind Distributed Deep Learning: AllReduce](https://tech.preferred.jp/en/blog/technologies-behind-distributed-deep-learning-allreduce/)
- [NVIDIA NCCL Developer Guide](https://docs.nvidia.com/deeplearning/sdk/nccl-developer-guide/docs/troubleshooting.html)
- [RCCL Topology Visualization Tool](https://github.com/ROCmSoftwarePlatform/rccl/tree/develop/tools/TopoVisual)
