# 使用 PyTorch 进行超大规模深度学习模型训练

在训练中几种并行的技术见下表所示：

| 并行范式            | 主要解决问题           | 前向 / 路由阶段通信               | 反向 / 参数更新通信                                          | 典型实现                    |
| :------------------ | :--------------------- | :-------------------------------- | :----------------------------------------------------------- | :-------------------------- |
| **D – 数据并行**    | 吞吐不足               | –                                 | All-Reduce（梯度）                                           | PyTorch DDP                 |
| **TP – 张量并行**   | 单层权重过大           | P2P / All-Gather（激活）          | Reduce-Scatter / All-Reduce                                  | Megatron-LM                 |
| **PP – 流水线并行** | 深层显存瓶颈；提升吞吐 | 微批串流；跨 stage 仅传激活       | ① 若 *每 stage = 1 GPU* → 无 All-Reduce<br>② 若 stage 内存在复制 → 需 All-Reduce | PyTorch Pipe / DeepSpeed-PP |
| **SP – 序列并行**   | 长序列注意力           | All-Gather（跨切片 Q/K/V）        | Reduce-Scatter / All-Reduce                                  | Megatron-SP                 |
| **E – 专家并行**    | 稀疏大容量 MoE         | All-to-All（token → expert 路由） | All-Reduce（同专家梯度）                                     | DeepSpeed-MoE               |
| **Z – ZeRO 1/2/3**  | 显存优化               | Stage-3：All-Gather（参数片段）   | Reduce-Scatter（梯度）                                       | DeepSpeed-ZeRO              |

### 常见混合范式

| 组合           | 目标           | 前向 / 路由通信              | 反向 / 更新通信                              | 典型实现           |
| :------------- | :------------- | :--------------------------- | :------------------------------------------- | :----------------- |
| **TP + D**     | 宽层 + 吞吐    | 同 TP                        | TP 内部通信 + D 组间梯度 All-Reduce          | Megatron-LM        |
| **PP + D**     | 深层 + 吞吐    | 微批串流                     | stage 内 All-Reduce                          | DeepSpeed-PP + DDP |
| **E + D**      | MoE + 吞吐     | All-to-All                   | ① 专家 All-Reduce<br>② D 组间梯度 All-Reduce | DeepSpeed-MoE      |
| **E + D + Z**  | MoE + 显存优化 | All-to-All + 参数 All-Gather | 专家 All-Reduce + ZeRO 通信                  | DeepSpeed-ZeRO-MoE |
| **E + D + TP** | 千亿级 LLM     | TP-P2P + All-to-All          | TP Reduce-Scatter + 各自 All-Reduce          | Megatron-DeepSpeed |

说明

1. “前向 / 路由阶段通信” 指开始计算前或过程中，为获得激活/参数片段/路由信息而进行的数据交换。
2. “反向 / 参数更新通信” 指梯度同步、优化器状态同步或分片参数归还等操作。
3. 只要同一层在多卡上存在“复制”，就一定需要在该复制组内做梯度 All-Reduce（即使使用了 PP、TP、MoE 等其他范式）。

## 1.数据并行

### **工作原理**

- **模型复制**：在每个 GPU 上复制完整的模型副本。
- **数据拆分**：将训练数据集划分成多份，每个 GPU 处理一部分数据。
- **独立计算**：每个 GPU 独立进行前向传播和反向传播，计算自己的梯度。
- **梯度同步**：使用 **All-Reduce** 操作在 GPU 之间同步并平均梯度。
- **参数更新**：所有 GPU 使用同步后的梯度更新模型参数，确保模型参数一致。

### **数据拆分**

- 将输入的批次（batch）等分到各个 GPU，每个 GPU 处理不同的数据子集。
- **目的**：加速训练，处理更多的数据，同时保持模型参数一致。

### **All-Reduce 操作的作用**

- **作用**：在各个 GPU 之间同步并平均梯度，确保模型参数的一致性。
- **原因**：每个 GPU 处理的数据不同，计算的梯度也不同，需要同步梯度。

### **是否需要共享存储**

- **训练数据**：需要共享存储或预先分发数据，以便各个 GPU 访问训练数据的不同部分。
- **模型参数**：每个 GPU 都有完整模型副本，参数存储在各自的显存中，不需要共享存储。

### **示意图**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/1.png)



数据并行是最直接、应用最广泛的并行技术。它涉及创建同一模型的多个副本，并在不同的数据子集上训练每个副本。在本地计算梯度后，这些梯度会被聚合（通常通过全归约运算）并用于更新模型的所有副本。

当模型本身适合单个 GPU 的内存，但数据集太大而无法按顺序处理时，此方法特别有效。

`torch.nn.DataParallel`PyTorch 通过& （DDP）模块内置了对数据并行的支持`torch.nn.parallel.DistributedDataParallel`。其中，DDP 广受青睐，因为它在多节点设置下提供了更好的可扩展性和效率。NVIDIA 的 NeMo 框架很好地阐释了它的工作原理——

![img](https://miro.medium.com/v2/resize:fit:1155/0*N0oUz4CoUu_70X5K.gif)

其示例实现可能如下所示：

```
import torch
import torch.nn as nn
import torch.optim as optim

# Define your model
model = nn.Linear(10, 1)

# Wrap the model with DataParallel
model = nn.DataParallel(model)

# Move the model to GPU
model = model.cuda()

# Define loss and optimizer
criterion = nn.MSELoss()
optimizer = optim.SGD(model.parameters(), lr=0.01)

# Dummy data
inputs = torch.randn(64, 10).cuda()
targets = torch.randn(64, 1).cuda()

# Forward pass
outputs = model(inputs)
loss = criterion(outputs, targets)

# Backward pass and optimization
loss.backward()
optimizer.step()
```

#### 关键要点

- **小模型/大数据集**——此方法仅当模型本身适合单个 GPU 的内存，但不适合数据集时才有效。
- **模型复制**——每个 GPU 都持有模型参数的相同副本。
- **小批量分割**——输入数据在 GPU 之间划分，确保每个设备处理单独的小批量。
- **梯度同步**——在前向和后向传递之后，梯度在 GPU 之间同步以保持一致性。

#### 优点和注意事项

- **简单高效**——易于实现，可与现有代码库直接集成，并且可出色地扩展到大型数据集。
- **通信开销**——梯度同步期间的通信开销可能成为大规模系统的瓶颈。

## 2. 张量并行

### **工作原理**

- **模型拆分**：将模型的某些大型张量（如权重矩阵）按特定维度拆分，分布在多个 GPU 上。
- **数据处理**：所有 GPU **共同处理相同的输入数据**，协同完成前向和后向计算。
- **协同计算**：在计算过程中，GPU 之间需要交换中间结果和梯度。
- **梯度同步**：使用 **All-Reduce** 操作在 GPU 之间同步必要的梯度信息。

### **数据拆分**

- **通常不拆分数据**，所有 GPU 处理相同的输入数据。
- **目的**：协同计算超大模型，使其能够分布在多个 GPU 的显存中。

### **All-Reduce 操作的作用**

- **前向传播**：交换中间计算结果，确保后续计算正确。
- **反向传播**：同步拆分张量的梯度，确保参数更新正确。

### **是否需要共享存储**

- **训练数据**：所有 GPU 需要访问相同的训练数据，需要共享数据存储。
- **模型参数**：模型参数被拆分存储在各自的 GPU 上，不需要共享模型参数的存储。

### **示意图**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/2.png)

**为什么不拆分输入数据？**


在张量并行中，**输入数据通常不拆分，而是每个 GPU 都处理相同的输入数据**。原因如下：

**模型计算需要完整的输入数据**

- **完整性需求**：模型的某些计算，尤其是矩阵乘法，需要完整的输入数据才能正确计算。

- **拆分模型参数对应完整输入**：虽然模型参数被拆分了，但这些参数仍需要作用于完整的输入数据，以产生正确的中间结果。

  **如果拆分数据，会增加通信和复杂性**

- **数据缺失**：拆分输入数据会导致每个 GPU 无法获得完整的输入，计算中会缺少必要的信息。

- **增加通信**：为了弥补缺失的数据，各个 GPU 需要频繁地通信，交换输入数据，增加了网络开销和实现复杂度。

- **效率降低**：通信的增加会导致计算效率降低，抵消了张量并行的优势。


**举例说明**

让我们以一个简单的矩阵乘法为例来说明。

**模型参数的拆分**

假设我们有一个大型的权重矩阵 W，大小为 [M, N]。

- **按列拆分**：将 W 的列维度拆分到两个 GPU 上。

  - **GPU 0**：持有 W 的前半部分，大小为 [M, N/2]。

  - **GPU 1**：持有 W 的后半部分，大小为 [M, N/2]。

    **输入数据的处理**

- **输入数据 x**：大小为 [Batch Size, N]。

- **不拆分数据**：每个 GPU 都拥有完整的 x，大小为 [Batch Size, N]。

  **前向传播计算**

- **GPU 0** 计算：y0 = x * 转置(W0)，得到部分输出 y0，大小为 [Batch Size, M]。

- **GPU 1** 计算：y1 = x * 转置(W1)，得到部分输出 y1，大小为 [Batch Size, M]。

- **合并结果**：将 y0 和 y1 相加，得到完整的输出 y = y0 + y1，大小为 [Batch Size, M]。

  **如果拆分了输入数据**

- **输入数据 x 拆分**

  - **GPU 0**：持有 x 的前半部分，大小为 [Batch Size, N/2]。
  - **GPU 1**：持有 x 的后半部分，大小为 [Batch Size, N/2]。

- **计算问题**

  - **GPU 0** 计算：无法直接进行 y0 = x * 转置(W0)，因为 x 的大小与 W0 不匹配（缺少后半部分的数据）。
  - **需要大量通信**：GPU 0 和 GPU 1 需要交换彼此的 x 部分，才能拥有完整的输入数据进行计算，增加了通信开销。

**总结**

- **在张量并行中，不拆分数据的原因是为了保证模型计算的完整性和效率**。
- **每个 GPU 都需要完整的输入数据**，以便使用本地的模型参数部分进行计算。
- **避免了过多的通信开销**：如果拆分输入数据，会导致各个 GPU 频繁地通信交换数据，降低计算效率。


**实际应用中的考虑**

- **结合数据并行（TP + DP）**
  - 为了同时扩展模型规模和增加训练吞吐量，常常将张量并行与数据并行结合。
  - **数据并行组**：将所有 GPU 分成多个数据并行组，每个组内部进行张量并行。
  - **数据拆分**：在数据并行组之间拆分数据，每个组处理不同的数据子集。
  - **在数据并行组内**：各个 GPU 仍然不拆分数据，共同处理相同的数据，以满足张量并行的要求。
- **通信优化**
  - **减少通信开销**：通过不拆分输入数据，避免了在前向和后向传播过程中额外的数据交换。
  - **效率提升**：使得 GPU 间的通信主要集中在必要的中间结果和梯度上，提高了并行效率。

**类比**

- **工厂生产线**
  - **产品（输出）**：需要多个车间（GPU）共同完成。
  - **原材料（输入数据）**：每个车间都需要完整的原材料，才能完成自己负责的加工步骤。
  - **分工协作**：车间之间按照分工（模型参数拆分）完成不同的加工任务，但原材料必须是完整的。
  - **避免材料切分**：如果将原材料拆分，每个车间无法得到完整的材料，无法完成加工，还需要花费时间和其他车间交换材料。

**结论**

- **在张量并行中，不拆分数据是为了保证计算的正确性和提高效率**。

- **所有 GPU 共同处理相同的数据**，使得拆分的模型参数能够与完整的输入数据进行计算。

- **这样设计可以减少通信开销，简化实现的复杂性**，充分发挥张量并行的优势。

  

数据并行侧重于数据分割，而**张量并行**（或**模型并行**）则将模型 本身划分到多个设备上。这种方法对大型权重矩阵和中间张量进行划分，使每个设备能够处理一小部分计算。张量并行并非像数据并行那样在每个 GPU 上复制整个模型，而是将模型的层或张量划分到多个设备。每个设备负责计算模型前向和后向传播的一部分。

该技术对于训练无法放入单个 GPU 内存的超大模型（尤其是基于 Transformer 的架构）特别有用。

虽然 PyTorch 不提供对张量并行的开箱即用支持，但使用 PyTorch 灵活的张量运算和分布式通信原语可以轻松实现自定义实现。如果您想要更强大的解决方案，可以使用[DeepSpeed](https://www.deepspeed.ai/)和[Megatron-LM](https://github.com/NVIDIA/Megatron-LM)等框架扩展 PyTorch 来实现此功能。张量并行实现的简单代码片段如下：

```
import torch
import torch.distributed as dist

def tensor_parallel_matmul(a, b, devices):
    # a is divided row-wise, b is shared across devices
    a_shard = a.chunk(len(devices), dim=0)
    results = []
    for i, dev in enumerate(devices):
        a_device = a_shard[i].to(dev)
        b_device = b.to(dev)
        results.append(torch.matmul(a_device, b_device))
    # Concatenate results from each device
    return torch.cat(results, dim=0)

# Example usage:
a = torch.randn(1000, 512)  # Assume this tensor is too big for one GPU
b = torch.randn(512, 256)
devices = ['cuda:0', 'cuda:1']

result = tensor_parallel_matmul(a, b, devices)
```

#### 关键要点

- **更大的模型**——当模型不适合单个 GPU 的内存时，此方法非常有效。
- **分片权重**——张量并行化不是在每个设备上复制完整模型，而是对模型的参数进行切片。
- **集体计算**——前向和后向传递在 GPU 上集体执行，需要仔细协调以确保张量的所有分量都得到正确计算。
- **自定义操作**——通常使用专门的 CUDA 内核或第三方库来有效地实现张量并行。

#### 优点和注意事项

- **内存效率**——通过拆分大型张量，您可以释放训练超出单个设备内存容量的模型的能力。它还能显著降低矩阵运算的延迟。
- **复杂性**——设备之间所需的协调带来了额外的复杂性。当扩展到超过两个 GPU 时，开发者必须谨慎管理同步。手动分区可能导致负载不平衡，而为了避免 GPU 长时间处于空闲状态，设备间通信是这些实现中常见的问题。
- **框架增强**——像 Megatron-LM 这样的工具已经为张量并行设定了标准，许多这样的框架可以与 PyTorch 无缝集成。然而，集成并不总是那么简单。

## 3. 流水线并行

### 工作原理

• 模型拆分
– 按拓扑顺序把网络划分为 N 个连续 stage（S₀…Sₙ₋₁），每个 stage 部署在 1 或 多张 GPU。

• 数据处理
– 将一个训练 batch 切成 m 个 **micro-batch**（μ₀…μₘ₋₁）。

• 流水线执行
– μ₀ 先进入 S₀，计算完立即传给 S₁；与此同时 μ₁ 开始在 S₀ 计算……
– 这样形成“计算-通信”重叠的流水线，可显著提升吞吐 / 显存利用率。

• 梯度同步

1. **单副本流水线（每个 stage = 1 GPU）**

– 各 GPU 只持有自己的层；梯度天然独占，无需跨 GPU All-Reduce。

2. **流水线 + 数据并行（某 stage 内有 k 张 GPU 副本）**

– 同一 stage 的 k 张 GPU 需在反向结束后对本 stage 梯度做 **All-Reduce**，以保持副本参数一致。
– 这一步与传统 DDP 相同，只是在流水线调度器内部触发。

------

### 数据拆分

• 将训练批次拆成若干微批次，按顺序送入 S₀。
• 目的：让各 stage 同时工作，减少气泡（idle gap），提高 GPU 利用率。
• 常见配置：micro-batch × stage ≥ 2 × stage （经验法则，可覆盖流水线启动/收尾气泡）。

------

### All-Reduce 的角色

| 场景                     | 是否执行 All-Reduce | 说明                                                         |
| ------------------------ | ------------------- | ------------------------------------------------------------ |
| 单副本流水线             | 否                  | 每层只在 1 张 GPU 上，梯度无需同步                           |
| stage 内存在副本 (PP+DP) | 是                  | 同层多副本需同步梯度；通信量与副本数 k 成正比                |
| 与 ZeRO/FSDP 混合        | 是                  | 在副本 All-Reduce 之外，还可能有 ZeRO-style Reduce-Scatter / All-Gather |

------

### 存储与数据访问

• 训练数据
– 单副本：仅 **S₀** 所在节点需要直接读取数据；其余 stage 通过前向激活接收信息。
– PP+DP：每个 **数据并行组** 的第一 stage 负责数据加载。

• 模型参数
– 参数被分段放在各自的 stage 显存中，无需全局共享存储。
– 若叠加 ZeRO-3 / FSDP，还会在 GPU 间对参数分片。

### **示意图**

 **纯流水线并行：**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/4.png)

**结合数据并行的流水线并行：**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/5.png)



![img](https://miro.medium.com/v2/resize:fit:1155/0*DbBWp9kHM1ptPnyU.gif)

流水线并行引入了将神经网络划分为多个连续阶段的概念，每个阶段由不同的 GPU 处理。随着数据在网络中流动，中间结果会从一个阶段转移到下一个阶段，类似于流水线作业。这种交错执行允许计算和通信重叠，从而提高整体吞吐量。

值得庆幸的是，PyTorch 确实有一个开箱即用的 API 支持此功能，`Pipe`可以使用它轻松创建分段模型。该 API 会自动将顺序模型划分为流经指定 GPU 的微批次。

有关如何使用此 API 的一个简单示例是：

```
import torch.nn as nn
from torch.distributed.pipeline.sync import Pipe

# Define two sequential segments of a model
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

# Combine the segments using Pipe
# The placement of modules across devices is handled by Pipe
# automatically if provided device assignments
model = nn.Sequential(segment1, segment2)
model = Pipe(model, chunks=4)

# Now, when you pass data through the model, micro-batches are processed
# in a pipelined fashion.
inputs = torch.randn(16, 1024)
outputs = model(inputs)import torch
import torch.nn as nn
from torch.distributed.pipeline.sync import Pipe

# Define model segments
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

# Combine segments into one model using Pipe
model = nn.Sequential(segment1, segment2)
# Split the model into micro-batches that traverse devices 'cuda:0'
# and 'cuda:1'
model = Pipe(model, devices=['cuda:0', 'cuda:1'], chunks=4)

# Simulated input batch
inputs = torch.randn(16, 1024).to('cuda:0')
outputs = model(inputs)
```

#### 关键要点

- **分阶段计算**——模型被划分为一系列阶段（或“流水线”）。每个阶段分配给不同的 GPU。
- **微批次处理**——不是一次通过一个阶段输送大量物料，而是将物料分成多个微批次，并连续流经管道。
- **提高吞吐量**——通过确保所有设备同时工作（即使是在不同的微批次上），管道并行性可以显著提高吞吐量。

#### 优点和注意事项

- **资源利用率**——管道并行性可以通过重叠不同阶段的计算来提高 GPU 利用率。

- **延迟与吞吐量的权衡**——虽然吞吐量增加了，但由于引入了管道延迟，延迟可能会略有下降。

- **复杂的调度**——有效的微批次调度和负载平衡对于实现跨阶段的最佳性能至关重要。、

  

## 5. **完全分片数据并行（Fully Sharded Data Parallel，FSDP）**

### 工作原理

1. **参数分片（Shard）**
   • 将每个权重张量、梯度张量以及对应的优化器状态平均切成 N 片，分别存放在 N 张 GPU 上。
   • 每张 GPU 常驻的只有“自己那一片”，从而把常驻显存占用降到 1/N。
2. **前向传播**
   • 当某层即将计算时，FSDP 在该层入口用 **All-Gather** 把该层完整参数临时拉到本地显存；计算结束后立即释放。
   • 激活可以选择再做 “activation checkpointing”，进一步节省显存。
3. **反向传播**
   • 生成完整梯度后，FSDP 立即对梯度做 **Reduce-Scatter**——既完成梯度聚合，又把结果拆回各自分片。
   • 每张 GPU 只保留属于自己的梯度片，等待优化器更新。
4. **参数更新**
   • 优化器（如 AdamW）在本地分片上独立执行更新。
   • 更新完毕后临时缓存被释放，显存重新回到“仅一片”的最小占用状态。
5. **混合精度补充（FP16/BF16 + FP32 master weight）**
   • 梯度先以低精度参与 Reduce-Scatter，然后在本地累加到 FP32 主权重。
   • 若开启梯度规范化、clip 或其它需要全量梯度 L2-norm 的操作，还会追加一次 **All-Gather / All-Reduce**。因此混合精度下往往是“两步通信”：
   ① Reduce-Scatter ② 可选 All-Gather / All-Reduce。

------

### 数据拆分

- 与普通数据并行相同：将训练集按批次切分到各 GPU；每张卡只处理自己的 mini-batch，从而在 **计算维度** 上继续做数据并行。

------

### 通信逻辑

| 阶段                  | 主要通信                | 目的                              |
| --------------------- | ----------------------- | --------------------------------- |
| 前向开始              | **All-Gather 参数片段** | 组装完整权重以执行层计算          |
| 反向结束              | **Reduce-Scatter 梯度** | 聚合梯度并把结果拆回各分片        |
| (可选) 混合精度后处理 | All-Reduce / All-Gather | 做梯度归一化、clip 或其它全局运算 |

> 与传统数据并行相比，FSDP 把“大 All-Reduce”拆成了“前向 All-Gather + 反向 Reduce-Scatter”，总体通信量相同但峰值显存占用更低，并可与计算重叠。

------

### 存储与 IO

- **训练数据** 需要位于共享文件系统，或在训练开始前拷贝到各节点；使用与普通 DDP 相同的 Dataset / DataLoader 即可。
- **模型参数** 物理上被分片存在各自 GPU 显存；无需集中式参数服务器或共享磁盘。模型保存时需调用 `FSDP.state_dict()` / `FSDP.full_state_dict()` 收集完整权重。

### **示意图**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/1.png)

## 6. 专家并行性

#### 背景与核心思想

1. **稀疏激活** 一次前向仅路由到 K 个专家 (K ≪ M)，计算量 ∝ K，但可堆叠 M≫K 的参数容量。
2. **并行挑战** 路由-All-to-All 与专家梯度同步带来高带宽需求；需与数据并行、张量并行、ZeRO 分片等技术混合，才能落地超大规模模型。
3. **DeepSpeed** 提供了 MoE-Layer、Balanced-Gate、Expert-Parallel 以及 ZeRO-3 的一站式封装。

------

### MoE 基本工作流

| 步骤           | 过程                                                         | 主要通信                                 |
| -------------- | ------------------------------------------------------------ | ---------------------------------------- |
| ① **门控路由** | Gate 对每个 token 产生 Top-K 专家索引                        | All-to-All（token 重排）                 |
| ② **专家前向** | 选中专家独立计算                                             | 若专家跨 GPU → 无；若副本存在 → 同步参数 |
| ③ **专家反向** | 按 token-to-expert 反路由梯度                                | 同 ①，All-to-All                         |
| ④ **梯度同步** | a. 专家权重：对“同名专家”做 All-Reduce<br>b. 非专家权重：按数据并行组做 All-Reduce | All-Reduce                               |
| ⑤ **参数更新** | 可叠加 ZeRO/FSDP，对参数分片各自更新                         | Reduce-Scatter / All-Gather（ZeRO-3）    |

> ①、③ 的两次 All-to-All 是 MoE **最占网络带宽** 的环节；梯度同步次之。

------

### 并行维度与组合

| 记号         | 说明                                                   |
| :----------- | :----------------------------------------------------- |
| **E**        | Expert Parallel：将 M 个专家拆到多个 GPU/节点          |
| **D**        | Data Parallel：不同 GPU 处理不同 batch                 |
| **M(TP/PP)** | Model / Tensor / Pipeline Parallel：拆主干 Transformer |
| **Z**        | ZeRO-1/2/3：对参数/梯度/优化器状态分片                 |

典型组合与通信要点：

1. **E + D**（最常见）
   • All-to-All ×2；专家内 All-Reduce；主干参数 DDP All-Reduce。
2. **E + Z**（显存极限）
   • 在 1 的基础上，主干和专家参数都以 ZeRO-3 方式分片；前向需参数 All-Gather。
3. **E + D + M(TP)**（千亿参数 LLM）
   • 主干层用张量并行；专家仍拆 E。TP 内有 P2P / All-Gather，外加 MoE All-to-All。
4. **E + D + Z**（DeepSpeed 推荐大规模配置）
   • 通信路径 = E+D 里的 All-to-All & All-Reduce + ZeRO-3 的 Gather/Scatter。

------

### 数据与参数布局

| 对象     | 布局                          | 共享需求                                    |
| -------- | ----------------------------- | ------------------------------------------- |
| 训练数据 | 按 D 组切分；各组首卡负责载入 | 需要共享文件系统或事先拷贝                  |
| 专家参数 | 按 E 维度分片                 | **不**需全局共享；只在同名专家间同步梯度    |
| 主干参数 | 可复制 (D) 或分片 (Z/FSDP)    | 若复制→每卡一份；若分片→训练期间动态 Gather |

------

### 通信原语速查

| 环节                | 原语                                     |
| ------------------- | ---------------------------------------- |
| token 路由 / 反路由 | `all_to_all` / `all_to_all_single`       |
| 专家梯度聚合        | `all_reduce` (按专家 tag)                |
| 主干梯度            | `all_reduce` (按 DDP bucket)             |
| ZeRO-3 参数         | 前向 `all_gather`，反向 `reduce_scatter` |

------

### 示例代码片段（DeepSpeed-MoE）

```
from deepspeed.moe.layer import MoE
import deepspeed, torch.nn as nn

class MoEBlock(nn.Module):
    def __init__(self, d_model=2048, num_experts=32, k=2):
        super().__init__()
        self.moe = MoE(hidden_size=d_model,
                       expert_group_size=num_experts,
                       k=k,
                       expert_fn=lambda : nn.Linear(d_model, d_model))

    def forward(self, x):
        out, _ = self.moe(x)   # out: [batch, seq, d_model]
        return out

model = MoEBlock()

ds_cfg = {
  "train_batch_size": 64,
  "zero_optimization": { "stage": 2 },
  "moe": {
      "enabled": True,
      "num_experts": 32,
      "k": 2,
      "expert_parallel_size": 8    # =E
  }
}

engine, optimizer, _, _ = deepspeed.initialize(model=model,
                                               config=ds_cfg)
```



#### **示意图1**

 
假设有 **4 个 GPU**，总共有 **8 个专家（Expert 0 - Expert 7）**，专家并行组大小为 **2**，数据并行组大小为 **2**。

**GPU 分组：**

- **数据并行组 0**：GPU 0、GPU 1

  - GPU 0：Expert 0、Expert 1、Expert 2、Expert 3
  - GPU 1：Expert 4、Expert 5、Expert 6、Expert 7
  - **专家并行组**：

- **数据并行组 1**：GPU 2、GPU 3

  - GPU 2：Expert 0、Expert 1、Expert 2、Expert 3

  - GPU 3：Expert 4、Expert 5、Expert 6、Expert 7

    **示意图：**

  - **专家并行组**：

    ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/6.png)

#### **示意图2**

- 假设有 **8 个 GPU**，数据并行组大小为 **2**，每个数据并行组内包含 **模型并行组** 和 **专家并行组**。

  **GPU 分组：**

- **数据并行组 0**：

  - GPU 0：Expert 0、Expert 1
  - GPU 1：Expert 2、Expert 3

  - **基础模型拆分**：例如张量并行。

  - **模型并行组**：GPU 0、GPU 1
  - **专家并行组**：

  **数据并行组 1**：

  - GPU 2：Expert 0、Expert 1

  - GPU 3：Expert 2、Expert 3

    **示意图：**

  - **基础模型拆分**。

  - **模型并行组**：GPU 2、GPU 3
  - **专家并行组**：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/7.png)

#### **示意图3**

 
假设有 **4 个 GPU**，数据并行组大小为 **2**，专家并行组大小为 **2**。

**GPU 分组：**

- **数据并行组 0**：

  - GPU 0、GPU 1

- **数据并行组 1**：

  - GPU 2、GPU 3

    **专家分配：**

- **GPU 0**：Expert 0、Expert 1

- **GPU 1**：Expert 2、Expert 3

- **GPU 2**：Expert 0、Expert 1

- **GPU 3**：Expert 2、Expert 3

  **基础模型参数**：通过 ZeRO 优化分片存储在所有 GPU 间。

  **示意图：**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/8.png)

#### **示意图**4
假设有 **4 个 GPU**，专家总数为 **8**。

**GPU 分配：**

- **GPU 0**：Expert 0、Expert 1

- **GPU 1**：Expert 2、Expert 3

- **GPU 2**：Expert 4、Expert 5

- **GPU 3**：Expert 6、Expert 7

  **示意图：**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PyTorch-Distributed-Training/images/9.png)

#### **总结**

- **组合并行策略**：通过组合专家并行、数据并行、模型并行、ZeRO 优化等策略，可以训练超大规模的 MOE 模型，充分利用计算和存储资源。
- **通信操作**：在不同的并行组合下，需要使用 **All-Reduce**、**All-Gather**、**Reduce-Scatter** 等集合通信操作，确保模型参数的同步和数据的正确路由。
- **资源利用**：根据模型规模和硬件资源，可以选择合适的并行组合，以达到最佳的训练效率。

------

#### 小结

• **MoE 的性能上限往往受 All-to-All 带宽制约**，NVLink / 200 Gb IB 是推荐硬件。
• 当专家数 ≫ GPU 数时，合理设置 `expert_parallel_size` 与 **Balanced-Gate** 可显著减轻负载失衡。
• 若显存成为瓶颈，优先在主干用 ZeRO-3；专家层由于激活稀疏，可先保留完整副本，必要时再做分片。



## ZeRO：零冗余优化器

![img](https://miro.medium.com/v2/resize:fit:1155/1*zW4JGv6pT6NXOMEBgMi-sg.png)

**ZeRO是****零冗余优化器**的缩写，代表了大规模训练内存优化领域的一项突破。ZeRO 作为 DeepSpeed 库的一部分开发，通过对优化器状态、梯度和模型参数进行分区，解决了分布式训练的内存限制问题。本质上，ZeRO 消除了每个 GPU 都保存所有副本时产生的冗余，从而显著节省了内存。

它的工作原理是将优化器状态和梯度的存储空间分配给所有参与设备，而不是复制它们。这种策略不仅减少了内存占用，还能使模型训练更加高效，否则这些模型的内存容量将超出单个 GPU 的容量。ZeRO 通常分为三个不同的阶段实施，每个阶段分别处理内存冗余的不同方面：

### ZeRO-1：优化器状态分区

- 跨 GPU 划分优化器状态（例如动量缓冲区）
- 每个 GPU 仅存储其部分参数的优化器状态
- 模型参数和梯度仍在所有 GPU 上复制

### ZeRO-2：梯度分区

- 包含 ZeRO-1 的全部功能
- 另外在 GPU 之间划分梯度
- 每个 GPU 仅计算和存储其参数部分的梯度
- 模型参数仍在所有 GPU 上复制

### ZeRO-3：参数分区

- 包含 ZeRO-1 和 ZeRO-2 的全部内容
- 另外在 GPU 之间划分模型参数
- 每个GPU只存储部分模型参数
- 需要在前向/后向传递过程中收集参数

![img](https://miro.medium.com/v2/resize:fit:1155/0*LS6Kzkq3QfLOz7Rc)

如上所示，ZeRO 结合了数据和模型并行的优势，提供了最大的灵活性。

虽然 DeepSpeed 本身就是一个特性，但它与 PyTorch 的集成使其成为训练优化库中不可或缺的工具，能够促进高效的内存管理，并使之前无法训练的模型大小在现代硬件上变得可行。其虚拟实现如下：

```
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

# DeepSpeed configuration with ZeRO optimizer settings
ds_config = {
    "train_batch_size": 32,
    "optimizer": {
        "type": "Adam",
        "params": {
            "lr": 0.001
        }
    },
    "zero_optimization": {
        "stage": 2,  # Stage 2: Gradient partitioning
        "allgather_partitions": True,
        "reduce_scatter": True,
        "allgather_bucket_size": 2e8,
        "overlap_comm": True
    }
}

# Initialize DeepSpeed with ZeRO for the model
model_engine, optimizer, _, _ = deepspeed.initialize(model=model,
                                                     config=ds_config)
inputs = torch.randn(32, 1024).to(model_engine.local_rank)
outputs = model_engine(inputs)
loss = outputs.mean()  # Simplified loss computation
model_engine.backward(loss)
model_engine.step()
```

#### 关键要点

- **阶段选择**——ZeRO 通常分多个阶段实现，每个阶段在内存节省和通信开销之间提供不同的平衡。根据模型大小、网络能力和可接受的通信开销水平选择合适的阶段至关重要。
- **与其他技术的集成**——它可以无缝地融入到可能包括上面讨论的并行化策略的生态系统中。

#### 优点和注意事项

- **通信开销**——此策略的一个固有挑战是，减少内存冗余通常会增加 GPU 之间交换的数据量。因此，高效利用高速互连（如 NVLink 或 InfiniBand）变得更加重要。
- **配置复杂性**——与更传统的优化器相比，ZeRO 引入了额外的配置参数。这些设置需要仔细的实验和性能分析，以匹配硬件的优势，确保优化器高效运行。设置包括但不限于：用于梯度聚合的适当存储桶大小，以及针对各种状态（优化器状态、梯度、参数）的分区策略。
- **强大的监控功能**——在支持 ZeRO 的训练中调试问题可能非常具有挑战性。因此，能够洞察 GPU 内存使用情况、网络延迟和整体吞吐量的监控工具至关重要。

## 将它们整合在一起

![img](https://miro.medium.com/v2/resize:fit:1155/1*iRnQIyDQgMUDMnVmkr8f4w.png)

大规模训练深度学习模型通常需要采用混合方法——通常会结合使用上述技术。例如，最先进的 LLM 可能会使用数据并行性在节点之间分配批次，使用张量并行性来拆分海量权重矩阵，使用上下文并行性来处理长序列，使用流水线并行性来链接连续的模型阶段，使用专家并行性来动态分配计算资源，最后使用 ZeRO 来优化内存使用。这种协同作用确保即使参数数量庞大的模型也能保持可训练性和高效性。

了解何时、何地以及如何使用这些技术，对于突破可能性的界限至关重要。再加上 PyTorch 的模块化和即插即用库，构建强大、可扩展且突破传统硬件限制的训练流程，正变得越来越容易被更广泛的受众所接受。



Refer to *https://medium.com/gitconnected/training-deep-learning-models-at-ultra-scale-using-pytorch-74c6cbaa814b*