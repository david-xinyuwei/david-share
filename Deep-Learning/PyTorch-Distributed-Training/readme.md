# 使用 PyTorch 进行超大规模深度学习模型训练

*https://medium.com/gitconnected/training-deep-learning-models-at-ultra-scale-using-pytorch-74c6cbaa814b*



![img](https://miro.medium.com/v2/resize:fit:1155/0*P3x3trJ1291XRI99)

​										3D并行范式[[图片来源](https://syncedreview.com/2020/09/14/microsoft-democratizes-deepspeed-with-four-new-technologies/)]

日活跃用户）更快迭代和部署的关键驱动因素。

# 1.数据并行

![img](https://miro.medium.com/v2/resize:fit:1155/1*nDV4X7Rbdgo0Y6EJGgFC7w.png)

数据并行[[图片来源](https://papers.nips.cc/paper_files/paper/2012/hash/6aca97005c68f1206823815f66102863-Abstract.html)]

数据并行是最直接、应用最广泛的并行技术。它涉及创建同一模型的多个副本，并在不同的数据子集上训练每个副本。在本地计算梯度后，这些梯度会被聚合（通常通过全归约运算）并用于更新模型的所有副本。

当模型本身适合单个 GPU 的内存，但数据集太大而无法按顺序处理时，此方法特别有效。

`torch.nn.DataParallel`PyTorch 通过& （DDP）模块内置了对数据并行的支持`torch.nn.parallel.DistributedDataParallel`。其中，DDP 广受青睐，因为它在多节点设置下提供了更好的可扩展性和效率。NVIDIA 的 NeMo 框架很好地阐释了它的工作原理——

![img](https://miro.medium.com/v2/resize:fit:1155/0*N0oUz4CoUu_70X5K.gif)

数据并行图解 [[图片来源](https://docs.nvidia.com/nemo-framework/user-guide/latest/_images/ddp.gif)]

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

## 关键要点

- **小模型/大数据集**——此方法仅当模型本身适合单个 GPU 的内存，但不适合数据集时才有效。
- **模型复制**——每个 GPU 都持有模型参数的相同副本。
- **小批量分割**——输入数据在 GPU 之间划分，确保每个设备处理单独的小批量。
- **梯度同步**——在前向和后向传递之后，梯度在 GPU 之间同步以保持一致性。

## 优点和注意事项

- **简单高效**——易于实现，可与现有代码库直接集成，并且可出色地扩展到大型数据集。
- **通信开销**——梯度同步期间的通信开销可能成为大规模系统的瓶颈。

# 2. 张量并行

![img](https://miro.medium.com/v2/resize:fit:1018/1*0RX4G3YwVMe95N09xSwlTg.png)

张量并行性[[图片来源](https://papers.nips.cc/paper_files/paper/2012/hash/6aca97005c68f1206823815f66102863-Abstract.html)]

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

## 关键要点

- **更大的模型**——当模型不适合单个 GPU 的内存时，此方法非常有效。
- **分片权重**——张量并行化不是在每个设备上复制完整模型，而是对模型的参数进行切片。
- **集体计算**——前向和后向传递在 GPU 上集体执行，需要仔细协调以确保张量的所有分量都得到正确计算。
- **自定义操作**——通常使用专门的 CUDA 内核或第三方库来有效地实现张量并行。

## 优点和注意事项

- **内存效率**——通过拆分大型张量，您可以释放训练超出单个设备内存容量的模型的能力。它还能显著降低矩阵运算的延迟。
- **复杂性**——设备之间所需的协调带来了额外的复杂性。当扩展到超过两个 GPU 时，开发者必须谨慎管理同步。手动分区可能导致负载不平衡，而为了避免 GPU 长时间处于空闲状态，设备间通信是这些实现中常见的问题。
- **框架增强**——像 Megatron-LM 这样的工具已经为张量并行设定了标准，许多这样的框架可以与 PyTorch 无缝集成。然而，集成并不总是那么简单。

# 3. 上下文并行

上下文并行则采用了不同的方法， 它针对的是输入数据的上下文维度，在基于序列的模型（例如 Transformer）中尤其有效。其主要思想是将长序列或上下文信息进行拆分，以便同时处理不同的部分。这使得模型能够处理更长的上下文，而不会占用过多的内存或计算资源。这种方法在需要同时训练多个任务的场景中尤其有用，例如在多任务 NLP 模型中。

与张量并行类似，PyTorch 本身并不支持上下文并行。然而，创造性地运用数据重构使我们能够有效地管理长序列。想象一下，有一个必须处理长文本的 Transformer 模型——该序列可以分解成更小的片段，并行处理，然后合并。

下面是一个如何在自定义 Transformer 块中拆分上下文的示例。在此示例中，该块可能会并行处理长序列的不同段，然后合并输出以进行最终处理。

```
import torch
import torch.nn as nn

class ContextParallelTransformer(nn.Module):
    def __init__(self, d_model, nhead, context_size):
        super(ContextParallelTransformer, self).__init__()
        self.context_size = context_size
        self.transformer_layer = nn.TransformerEncoderLayer(
                                    d_model=d_model, nhead=nhead)
    
    def forward(self, x):
        # x shape: [batch, seq_len, d_model]
        batch, seq_len, d_model = x.size()
        assert seq_len % self.context_size == 0,
                "Sequence length must be divisible by context_size"
        # Divide the sequence dimension into segments
        segments = x.view(batch, seq_len // self.context_size,
                          self.context_size, d_model)
        # Process each segment in parallel using a loop or parallel map
        processed_segments = []
        for i in range(segments.size(1)):
            segment = segments[:, i, :, :]
            processed_segment = self.transformer_layer(
                                segment.transpose(0, 1))
            processed_segments.append(processed_segment.transpose(0, 1))
        # Concatenate processed segments back to full sequence
        return torch.cat(processed_segments, dim=1)

# Example usage:
model = ContextParallelTransformer(d_model=512, nhead=8, context_size=16)
# [batch, sequence_length, embedding_dim]
input_seq = torch.randn(32, 128, 512)
output = model(input_seq)
```

## 关键要点

- **序列划分**——对序列或上下文维度进行划分，从而实现对数据不同段的并行计算。
- **长序列的可扩展性**——这对于处理极长序列的模型特别有用，因为一次性处理整个上下文既不可能又低效。
- **注意力机制**——在 Transformer 中，将注意力计算划分到各个段中，使得每个 GPU 能够处理序列的一部分及其相关的自注意力计算。

## 优点和注意事项

- **高效的长序列处理**——通过将长上下文划分为并行段，模型可以处理大量序列而不会占用过多的内存资源。
- **顺序依赖关系**——必须特别注意跨越上下文段边界的依赖关系。可能需要使用诸如重叠段或额外聚合步骤之类的技术。
- **新兴领域**——随着研究的继续，我们期望出现更多标准化的工具和库，专门促进 PyTorch 中的上下文并行性。

# 4. 流水线并行

![img](https://miro.medium.com/v2/resize:fit:1155/0*DbBWp9kHM1ptPnyU.gif)

流水线并行性图示 [[图片来源](https://docs.nvidia.com/nemo-framework/user-guide/latest/_images/pp.gif)]

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

## 关键要点

- **分阶段计算**——模型被划分为一系列阶段（或“流水线”）。每个阶段分配给不同的 GPU。
- **微批次处理**——不是一次通过一个阶段输送大量物料，而是将物料分成多个微批次，并连续流经管道。
- **提高吞吐量**——通过确保所有设备同时工作（即使是在不同的微批次上），管道并行性可以显著提高吞吐量。

## 优点和注意事项

- **资源利用率**——管道并行性可以通过重叠不同阶段的计算来提高 GPU 利用率。
- **延迟与吞吐量的权衡**——虽然吞吐量增加了，但由于引入了管道延迟，延迟可能会略有下降。
- **复杂的调度**——有效的微批次调度和负载平衡对于实现跨阶段的最佳性能至关重要。

# 5. 专家并行性

![img](https://miro.medium.com/v2/resize:fit:1155/0*NVxbRSN6t6XcMORt.png)

专家并行性[[图片来源](https://docs.nvidia.com/nemo-framework/user-guide/latest/_images/ep.png)]

**专家并行性是一种受混合专家 (MoE)**模型启发的技术，旨在扩展模型容量，同时保持计算成本可控。在此范式中，模型由多个专门的“专家”组成——这些子网络通过门控机制针对每个输入选择性地激活。只有一小部分专家参与处理特定样本，从而允许在不相应增加计算开销的情况下实现巨大的模型容量。

![img](https://miro.medium.com/v2/resize:fit:1155/1*6xkK-TxwPBG4671NttMlXA.png)

混合专家模型采用的门控函数[[图片来源](https://arxiv.org/pdf/2407.06204)]

同样，PyTorch 并没有提供开箱即用的解决方案，但它的模块化设计允许创建自定义实现。该策略通常包括定义一组专家层以及一个决定激活哪些专家的门控。

在生产环境中，专家并行通常与其他并行策略相结合。例如，您可以同时使用数据并行和专家并行来处理大型数据集和海量模型参数，同时选择性地将计算路由到相应的专家。下图展示了一个简化的实现：

```
import torch
import torch.nn as nn
import torch.nn.functional as F

class Expert(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(Expert, self).__init__()
        self.fc = nn.Linear(input_dim, output_dim)
    
    def forward(self, x):
        return F.relu(self.fc(x))

class MoE(nn.Module):
    def __init__(self, input_dim, output_dim, num_experts, k=2):
        super(MoE, self).__init__()
        self.num_experts = num_experts
        self.k = k  # number of experts to use per example
        self.experts = nn.ModuleList([Expert(input_dim, output_dim)
                                      for _ in range(num_experts)])
        self.gate = nn.Linear(input_dim, num_experts)
    
    def forward(self, x):
        # x shape: [batch, input_dim]
        gate_scores = self.gate(x)  # [batch, num_experts]
        # Select top-k experts for each input
        topk = torch.topk(gate_scores, self.k, dim=1)[1]
        outputs = []
        for i in range(x.size(0)):
            expert_output = 0
            for idx in topk[i]:
                expert_output += self.experts[idx](x[i])
            outputs.append(expert_output / self.k)
        return torch.stack(outputs)

# Example usage:
batch_size = 32
input_dim = 512
output_dim = 512
num_experts = 4
model = MoE(input_dim, output_dim, num_experts)
x = torch.randn(batch_size, input_dim)
output = model(x)
```

## 关键要点

- **混合专家**——每个训练示例仅使用一部分专家，大大减少每个示例所需的计算量，同时保持非常大的整体模型容量。
- **动态路由**——门控功能动态决定哪个专家应该处理每个输入令牌或数据段。
- **专家级别的并行性**——专家可以分布在多个设备上，从而允许并行计算并进一步减少瓶颈。

## 优点和注意事项

- **可扩展的模型容量**——专家并行性使您能够构建具有大容量的模型，而无需为每个输入线性增加计算量。
- **高效计算**——通过仅处理每个输入的选定专家子集，您可以实现高计算效率。
- **路由复杂性**——门控机制至关重要。设计不良的路由会导致负载不平衡和训练不稳定。
- **研究前沿**——专家并行性仍然是一个活跃的研究领域，正在进行的研究旨在改进门控方法和专家之间的同步。

# 6. ZeRO：零冗余优化器

![img](https://miro.medium.com/v2/resize:fit:1155/1*zW4JGv6pT6NXOMEBgMi-sg.png)

分区策略和 GPU 性能 [[图片来源](https://nanotron-ultrascale-playbook.static.hf.space/assets/images/zero_memory.svg)]

**ZeRO是****零冗余优化器**的缩写，代表了大规模训练内存优化领域的一项突破。ZeRO 作为 DeepSpeed 库的一部分开发，通过对优化器状态、梯度和模型参数进行分区，解决了分布式训练的内存限制问题。本质上，ZeRO 消除了每个 GPU 都保存所有副本时产生的冗余，从而显著节省了内存。

它的工作原理是将优化器状态和梯度的存储空间分配给所有参与设备，而不是复制它们。这种策略不仅减少了内存占用，还能使模型训练更加高效，否则这些模型的内存容量将超出单个 GPU 的容量。ZeRO 通常分为三个不同的阶段实施，每个阶段分别处理内存冗余的不同方面：

## ZeRO-1：优化器状态分区

- 跨 GPU 划分优化器状态（例如动量缓冲区）
- 每个 GPU 仅存储其部分参数的优化器状态
- 模型参数和梯度仍在所有 GPU 上复制

## ZeRO-2：梯度分区

- 包含 ZeRO-1 的全部功能
- 另外在 GPU 之间划分梯度
- 每个 GPU 仅计算和存储其参数部分的梯度
- 模型参数仍在所有 GPU 上复制

## ZeRO-3：参数分区

- 包含 ZeRO-1 和 ZeRO-2 的全部内容
- 另外在 GPU 之间划分模型参数
- 每个GPU只存储部分模型参数
- 需要在前向/后向传递过程中收集参数

![img](https://miro.medium.com/v2/resize:fit:1155/0*LS6Kzkq3QfLOz7Rc)

ZeRO Offload 的架构 [[图片来源](https://syncedreview.com/2020/09/14/microsoft-democratizes-deepspeed-with-four-new-technologies/)]

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

## 关键要点

- **阶段选择**——ZeRO 通常分多个阶段实现，每个阶段在内存节省和通信开销之间提供不同的平衡。根据模型大小、网络能力和可接受的通信开销水平选择合适的阶段至关重要。
- **与其他技术的集成**——它可以无缝地融入到可能包括上面讨论的并行化策略的生态系统中。

## 优点和注意事项

- **通信开销**——此策略的一个固有挑战是，减少内存冗余通常会增加 GPU 之间交换的数据量。因此，高效利用高速互连（如 NVLink 或 InfiniBand）变得更加重要。
- **配置复杂性**——与更传统的优化器相比，ZeRO 引入了额外的配置参数。这些设置需要仔细的实验和性能分析，以匹配硬件的优势，确保优化器高效运行。设置包括但不限于：用于梯度聚合的适当存储桶大小，以及针对各种状态（优化器状态、梯度、参数）的分区策略。
- **强大的监控功能**——在支持 ZeRO 的训练中调试问题可能非常具有挑战性。因此，能够洞察 GPU 内存使用情况、网络延迟和整体吞吐量的监控工具至关重要。

# 将它们整合在一起

![img](https://miro.medium.com/v2/resize:fit:1155/1*iRnQIyDQgMUDMnVmkr8f4w.png)

各种混合并行方法[[图片来源](https://arxiv.org/pdf/2407.06204)]

大规模训练深度学习模型通常需要采用混合方法——通常会结合使用上述技术。例如，最先进的 LLM 可能会使用数据并行性在节点之间分配批次，使用张量并行性来拆分海量权重矩阵，使用上下文并行性来处理长序列，使用流水线并行性来链接连续的模型阶段，使用专家并行性来动态分配计算资源，最后使用 ZeRO 来优化内存使用。这种协同作用确保即使参数数量庞大的模型也能保持可训练性和高效性。

了解何时、何地以及如何使用这些技术，对于突破可能性的界限至关重要。再加上 PyTorch 的模块化和即插即用库，构建强大、可扩展且突破传统硬件限制的训练流程，正变得越来越容易被更广泛的受众所接受。