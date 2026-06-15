# vLLM 注意力架构与性能对比

> vLLM 注意力优化技术栈全面指南 — PagedAttention、FlashAttention、FlashInfer、CUDAGraph 和连续批处理 — 附多 GPU 实测数据。


## 在 Azure 上运行

本项目的所有实验均在 **Azure GPU 虚拟机**上完成。

| 项目 | 详情 |
|---|---|
| **Azure VM** | [NC RTX Pro 6000V6 BSE](https://learn.microsoft.com/en-us/azure/virtual-machines/ncv3-series) |
| **GPU** | NVIDIA RTX 6000 Ada 48GB |
| **框架** | vLLM |


## 🎯 核心发现

| 条件 | 胜出 | 差距 | 建议 |
|------|------|------|------|
| **CUDAGraph + 长序列** | FlashInfer | **+9~15%** | 生产部署 |
| CUDAGraph + 短序列 | FlashInfer | +1% | 默认选择 |
| Eager 模式（任何配置） | FlashAttention | +1~7% | 开发调试 |
| 大批量 (128) + Eager | FlashAttention | +11.8% | 批处理 |

**结论**:
- **生产环境（启用 CUDAGraph）**: 使用 FlashInfer（vLLM 默认）- 长序列场景快 **9-15%**
- **开发环境（enforce_eager=True）**: FlashAttention 稍快

### 跨 GPU 验证（鲁棒性）

| 配置 | A100 (Ampere) | RTX 6000 (Blackwell, 3次平均) | 结论 |
|------|--------------|-------------------------------|------|
| 长序列 + CUDAGraph | **FI +15.4%** | **FI +9.3%** | ✅ **一致：FI 胜出** |
| 短序列 + CUDAGraph | FI +1.2% | FI +0.9% | ✅ 一致 |
| 中批量 + CUDAGraph | FI +1.3% | FA +4.1% | ⚠️ 因架构而异 |

---

## 🧠 技术背景

### vLLM 架构概览

vLLM（Virtual Large Language Model）由 Kwon 等人在 2023 年论文 *"Efficient Memory Management for Large Language Model Serving with PagedAttention"* 中提出。它解决了 LLM 服务系统中 GPU 显存管理 KV 缓存的低效问题 — 导致 GPU 资源利用不充分、推理速度慢、显存占用高。

vLLM 综合了多项关键技术实现高吞吐、低延迟推理：

| 技术 | 功能 | 效果 |
|------|------|------|
| **PagedAttention** | 分页式 KV 缓存内存管理 | 消除显存碎片化 |
| **连续批处理** | 动态请求调度 | 最大化 GPU 利用率 |
| **FlashAttention / FlashInfer** | 优化注意力内核 | 减少计算和显存开销 |
| **CUDAGraph** | 预编译执行图 | 消除内核启动开销 |
| **显存预分配** | 预留 90% GPU 显存 | 避免运行时分配成本 |

**LLM 服务中的批处理策略**：

- **客户端（静态）批处理**：客户端将多个推理请求打包为一个批次。需要修改客户端代码，与批次大小强耦合
- **服务端（动态）批处理**：服务端动态合并到达的独立请求 — 包括动态批处理、连续批处理和 PagedAttention 批处理。无需修改客户端。vLLM 使用连续批处理在生成过程中动态调整批次大小

### PagedAttention：受操作系统启发的 KV 缓存管理

PagedAttention 是 vLLM 高性能的核心驱动力。受操作系统虚拟内存分页机制的启发，它通过块表（Block Table）将逻辑连续的虚拟块映射到物理上不连续的 GPU 显存块。

#### 虚拟块到物理块的映射

```mermaid
flowchart LR
    subgraph VB["虚拟块 - 逻辑连续"]
        V0["#0: the, cat, is, sleeping"]
        V1["#1: in, the, kitchen, and"]
        V2["#2: the, dog, is"]
    end

    subgraph PM["物理 GPU 显存 - 非连续"]
        P1["物理 #1 空闲"]
        P2["物理 #2"]
        P3["物理 #3"]
        P4["物理 #4 空闲"]
        P5["物理 #5"]
    end

    V0 -.->|"映射"| P5
    V1 -.->|"映射"| P2
    V2 -.->|"映射"| P3
```

**核心机制**：

| 机制 | 说明 |
|------|------|
| **固定大小的块** | KV 张量被分为固定大小的块（如 block_size=4 个 token），每个块存储固定数量 token 的 KV 对 |
| **按需分配** | 块在推理过程中按需分配，高效填充碎片化的 GPU 显存 |
| **逐块获取** | 注意力内核按查询 token 逐块获取 KV 缓存 — 由于块大小有限，比加载整个 KV 序列更快 |
| **虚拟块共享** | 在束搜索或并行采样时，所有序列共享相同的虚拟块，避免 KV 缓存重复。节省显存并支持更多并发请求 |

**性能表现**：伯克利的基准测试显示 vLLM 显著优于 HuggingFace TGI，在更大的模型上性能差距更明显（大模型受显存碎片化影响更大）。

### vLLM 显存预分配

vLLM 默认设置 `gpu_memory_utilization=0.9`，预分配 90% 显存作为 KV 缓存块池：

| 方面 | 详情 |
|------|------|
| **默认值** | `gpu_memory_utilization=0.9` |
| **目的** | 预先分配 KV 缓存块池 |
| **收益** | 消除运行时分配/释放开销 |
| **机制** | PagedAttention 按需填充预分配的块 |

这确保了处理长序列或大批量时有足够的显存存储所有中间结果，避免频繁的显存分配/释放操作导致性能下降。

### FlashAttention：IO 感知的分块计算

FlashAttention（Dao 等人，Stanford）通过利用 GPU 显存层次结构实现快速、高显存效率的**精确**注意力计算。

#### GPU 显存层次结构

| 显存类型 | 带宽 | 容量 | FlashAttention 中的作用 |
|---------|------|------|---------------------|
| **GPU SRAM** | ~19 TB/s | ~20 MB | 在此计算注意力分块 |
| **GPU HBM** | ~1.5 TB/s | 40-80 GB | 存储 Q、K、V、输出矩阵 |
| **CPU DRAM** | ~12.8 GB/s | >1 TB | 注意力计算时不使用 |

#### 分块机制

传统注意力在 HBM 中计算完整的 N x N 注意力矩阵 — 对长序列来说开销禁止。FlashAttention 通过**分块（Tiling）**避免这个问题：

```mermaid
flowchart TB
    subgraph HBM["GPU HBM"]
        Q["Q 矩阵"]
        K["K 矩阵"]
        V["V 矩阵"]
        O["输出矩阵"]
    end

    subgraph SRAM["GPU SRAM - 片上内存, ~19 TB/s"]
        KB["K 分块"]
        VB["V 分块"]
        QB["Q 分块"]
        OB["部分输出"]
    end

    K -->|"1. 外层循环: 加载 K,V 分块"| KB
    V -->|"1. 外层循环: 加载 K,V 分块"| VB
    Q -->|"2. 内层循环: 加载 Q 分块"| QB
    OB -->|"3. 写回结果"| O
```

1. **外层循环**：从 HBM 加载 K 和 V 的分块到快速的片上 SRAM
2. **内层循环**：对每个 K、V 分块，遍历 Q 分块并完全在 SRAM 中计算部分注意力
3. **写回**：分块计算完成后才将结果写回 HBM

结果：在 GPT-2 上相比 PyTorch 标准注意力实现取得 **7.6 倍加速**（Dao 等人实测）。

#### FlashAttention-2 改进

| 优化 | 详情 |
|------|------|
| **减少非矩阵乘法操作** | A100 上：matmul 吞吐 = 312 TFLOPS/s vs 非 matmul = 19.5 TFLOPS/s（**每 FLOP 成本差 16 倍**）。FA-2 最小化非 matmul 操作，最大化 Tensor Core 使用时间 |
| **序列长度并行化** | FA-1 仅在批次和注意力头维度并行。FA-2 还在序列长度维度并行 — 对小批次长序列场景至关重要 |
| **更优的 Warp 分区** | 减少线程 Warp 间的通信和同步开销（每个 Warp = 32 个线程） |
| **更广泛的模型支持** | 支持最多 256 个注意力头；支持 MQA（Multi-Query Attention）和 GQA（Grouped-Query Attention） |

### 连续批处理（Continuous Batching）

与静态批处理（等待批次中所有请求完成）不同，**连续批处理**在有槽位释放时动态加入新请求：

| 时间 | 请求 1: "Capital of" | 请求 2: "The diamondback turtle is" | 请求 3: "Largest Mammal is" |
|------|---------------------|-----------------------------------|--------------------------|
| T1 | 预填充 | 预填充 | 预填充 |
| T2 | 预填充 | 预填充 | 预填充 |
| T3 | 解码 | 解码 | 解码 |
| T4 | 解码 | 解码 | 解码 |
| T5 | 解码 | 解码 | **完成** → 新请求进入 |
| T6 | 解码 | **完成** → 新请求进入 | 新请求处理 |
| T7 | **完成** | 新请求处理 | 新请求处理 |

**核心优势**：
- **最大化 GPU 利用率**：不需等待最长请求完成，无 GPU 空闲时间
- **降低平均延迟**：短请求完成后立即退出批次
- **提高吞吐量**：槽位释放后新请求立即进入

### FlashInfer vs FlashAttention：对比总结

两者都实现了 O(N) 显存效率，但设计侧重不同：

| 方面 | FlashAttention | FlashInfer |
|------|---------------|------------|
| **来源** | Stanford / Tri Dao | CMU / UW |
| **主要聚焦** | 训练 + 推理 | 推理服务 |
| **核心优化** | IO 感知分块（SRAM/HBM 层次结构） | Paged KV 缓存 + CUDAGraph 优化 |
| **显存效率** | O(N) 替代 O(N^2) | O(N) + 动态批处理 |
| **CUDAGraph 支持** | 基础支持 | 专门优化 |
| **PagedAttention** | 外部（vLLM 管理分页） | 原生 Paged KV 缓存支持 |

> FlashAttention 优化的是注意力计算本身，而 vLLM 的整体加速来自 **PagedAttention + 连续批处理 + CUDAGraph + 优化注意力内核** 的协同作用。

### 为什么 CUDAGraph 很重要

#### CPU-GPU 内核启动开销分析

在传统 Eager 执行模式下，每个 CUDA 内核调用都需要完整的启动流程：

| 阶段 | CPU 操作 | GPU 状态 | 开销 |
|------|---------|---------|------|
| 1 | 准备内核参数 | 等待 | ~1μs |
| 2 | 调用 CUDA API | 接收指令 | ~2μs |
| 3 | 同步等待 | 执行内核 | ~2μs |
| **合计** | | | **~5μs/内核** |

**量化影响**：Llama-7B 单次 Decode 涉及 300+ 内核调用，启动开销 = 5μs × 300 = 1.5ms，而实际计算仅需 2-3ms，**启动开销占比 30-40%**。

#### CUDAGraph 工作原理

```mermaid
flowchart LR
    subgraph Eager["Eager 模式"]
        E1[内核1] -->|"同步 5μs"| E2[内核2] -->|"同步 5μs"| E3[内核3]
    end
    
    subgraph Graph["CUDAGraph 模式"]
        G1["捕获阶段<br/>(一次性)"] --> G2["Graph 对象"]
        G2 --> G3["Replay<br/>(每次推理)"]
        G3 -->|"单次启动 ~10μs"| K["K1→K2→K3<br/>连续执行"]
    end
```

#### 关键约束条件

| 约束 | 说明 | LLM 推理兼容性 |
|------|------|---------------|
| **静态拓扑** | 计算图结构必须固定 | ✅ Transformer 前向传播拓扑固定 |
| **固定 Shape** | 张量形状在录制时确定 | ⚠️ vLLM 通过分桶处理 |
| **无动态分支** | 禁止 if/while 运行时分支 | ✅ 推理无动态分支 |
| **内存绑定** | 张量地址在图生命周期内固定 | ✅ vLLM 预分配内存池 |

#### 性能收益

| 指标 | Eager 模式 | CUDAGraph | 改善 |
|------|-----------|-----------|------|
| 内核启动 | N 次 × 5μs | 1 次 × 10μs | **N:1** |
| Decode 延迟 | ~4ms | ~1.5ms | **2.5x** |
| GPU 利用率 | 60-70% | 85-95% | +25% |

FlashInfer 专门为 CUDAGraph 捕获进行了优化，这就是为什么启用 CUDAGraph 时它比 FlashAttention 更快。

---

## 🔧 Eager vs Graph 执行模式

### 执行范式对比

| 特性 | Eager 执行 | Graph 执行 |
|------|-----------|-----------|
| **执行时机** | 逐算子即时执行 | 预编译后批量执行 |
| **调试支持** | ✅ 完整堆栈追踪 | ⚠️ 仅图级错误 |
| **动态控制流** | ✅ 支持 if/while | ❌ 不支持 |
| **启动开销** | 高（每算子同步） | 低（整图同步） |

### vLLM 配置

```python
from vllm import LLM

# Graph 模式（默认，生产推荐）
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct")

# Eager 模式（调试时使用）
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", enforce_eager=True)
```

---

## 🔗 执行模式与注意力后端的组合关系

### 架构分层

```mermaid
flowchart TB
    subgraph Layer1["执行模式层"]
        Eager["Eager Mode<br/>逐算子执行"]
        Graph["Graph Mode<br/>CUDAGraph 批量执行"]
    end
    
    subgraph Layer2["注意力后端层"]
        FA["FlashAttention<br/>Stanford"]
        FI["FlashInfer<br/>CMU/UW"]
    end
    
    Layer1 -->|"正交组合"| Layer2
```

**关键概念**：执行模式和注意力后端是**正交维度**，可自由组合。

### 四种组合性能（A100 实测）

```mermaid
quadrantChart
    title Execution Mode x Attention Backend
    x-axis Low Throughput --> High Throughput
    y-axis Hard to Debug --> Easy to Debug
    quadrant-1 Development
    quadrant-2 Not Recommended
    quadrant-3 Production Offline
    quadrant-4 Online Serving Optimal
    "Eager+FA": [0.25, 0.85]
    "Eager+FI": [0.20, 0.80]
    "Graph+FA": [0.70, 0.25]
    "Graph+FI": [0.85, 0.20]
```

| 组合 | 吞吐量 (tok/s) | vs 基准 | 适用场景 |
|------|---------------|---------|----------|
| Eager + FA | 682 | 基准 | 开发调试 |
| Eager + FI | 675 | -1% | 不推荐 |
| Graph + FA | 1,522 | +123% | 生产（离线批处理） |
| **Graph + FI** | **1,757** | **+158%** | **生产（在线服务）** ✅ |

### vLLM 配置示例

```python
import os
from vllm import LLM

# 组合 1: Eager + FA（开发调试）
os.environ["VLLM_ATTENTION_BACKEND"] = "FLASH_ATTN"
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", enforce_eager=True)

# 组合 2: Graph + FA（生产-离线批处理）
os.environ["VLLM_ATTENTION_BACKEND"] = "FLASH_ATTN"
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct")

# 组合 3: Graph + FI（生产-在线服务）✅ vLLM 默认
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct")
```

---

## 🖥️ 测试环境

### 硬件

| GPU | 架构 | 显存 | 计算能力 |
|-----|------|------|---------|
| NVIDIA H100 NVL | Hopper | 94GB HBM3 | SM90 |
| NVIDIA A100 80GB PCIe | Ampere | 80GB HBM2e | SM80 |
| NVIDIA RTX Pro 6000 | Blackwell | 96GB | SM120 |

### 软件

| 组件 | A100 | RTX 6000 |
|------|------|----------|
| vLLM | 0.10.2 | 0.13.0 |
| FlashInfer | 0.5.3 | 0.6.0rc2 |
| FlashAttention | 2.8.3 | 2.8.3 |
| PyTorch | 2.8.0+cu128 | 2.9.0+cu128 |

### 测试模型

- **模型**: `Qwen/Qwen2.5-0.5B-Instruct`
- **原因**: 小模型以隔离注意力内核性能（避免内存瓶颈）

---

## 📊 测试结果

### 测试 1: 多 GPU 对比（Eager 模式）

**配置**: 128 请求, max_tokens=256, enforce_eager=True, 3 次平均

| GPU | FlashInfer (tok/s) | FlashAttention (tok/s) | 胜出 | 差距 |
|-----|-------------------|----------------------|------|------|
| H100 NVL | 9,893 | 10,334 | FA | +4.5% |
| A100 80GB | 8,780 | 9,260 | FA | +5.5% |
| RTX Pro 6000 | 9,845 | 10,300 | FA | +4.6% |

**结论**: Eager 模式下，FlashAttention 一致领先 4-5%。

### 测试 2: 批量大小扫描（A100, Eager 模式）

**配置**: A100 80GB, enforce_eager=True, 3 次平均

| 批量大小 | FlashInfer (tok/s) | FlashAttention (tok/s) | 胜出 | 差距 |
|----------|-------------------|----------------------|------|------|
| 1 | 72 | 75 | FA | +4.3% |
| 8 | 556 | 557 | FA | +0.2% |
| 32 | 1,978 | 2,015 | FA | +1.9% |
| 128 | 7,014 | 7,949 | FA | +11.8% |

**结论**: Eager 模式下，批量越大 FlashAttention 优势越明显。

### 测试 3: CUDAGraph + 序列长度（A100）

**配置**: A100 80GB, batch=8, 各 1 次

| 配置 | FlashInfer (tok/s) | FlashAttention (tok/s) | 胜出 | 差距 |
|------|-------------------|----------------------|------|------|
| 短序列 (256 tok), Eager | 675 | 682 | FA | +1.1% |
| 短序列 (256 tok), CUDAGraph | 1,647 | 1,628 | **FI** | +1.2% |
| 长序列 (1024 tok), Eager | 663 | 671 | FA | +1.2% |
| **长序列 (1024 tok), CUDAGraph** | **1,757** | **1,522** | **FI** | **+15.4%** |
| 中批量 (32×512), CUDAGraph | 6,176 | 6,095 | **FI** | +1.3% |

**关键发现**: FlashInfer 的优势在启用 CUDAGraph 后显现，尤其是长序列场景下吞吐量高 **15.4%**。

### 测试 4: RTX Pro 6000 鲁棒性测试（3 次平均）

**配置**: RTX Pro 6000 Blackwell, vLLM 0.13.0, FlashInfer 0.6.0rc2, **3 次平均**

| 配置 | FlashInfer (tok/s) | FlashAttention (tok/s) | 胜出 | 差距 |
|------|-------------------|----------------------|------|------|
| 短序列 (256), CUDAGraph | 2,644 | 2,620 | **FI** | +0.9% |
| **长序列 (1024), CUDAGraph** | **2,290** | **2,096** | **FI** | **+9.3%** |
| 中批量 (32×512), CUDAGraph | 8,723 | 9,100 | FA | +4.1% |

<details>
<summary>📈 原始数据（每项 3 次）</summary>

```json
{
  "Short_CUDAGraph": {
    "FLASHINFER": [2600.1, 2696.3, 2636.4],
    "FLASH_ATTN": [2613.1, 2638.4, 2607.6]
  },
  "Long_CUDAGraph": {
    "FLASHINFER": [2407.0, 2110.6, 2352.9],
    "FLASH_ATTN": [2617.1, 1843.0, 1827.6]
  },
  "Medium_CUDAGraph": {
    "FLASHINFER": [8958.7, 8548.1, 8662.2],
    "FLASH_ATTN": [9139.5, 9129.2, 9030.3]
  }
}
```

</details>

**验证**: RTX 6000 (Blackwell 架构) 确认了 A100 的发现 - **FlashInfer 在长序列 + CUDAGraph 场景下快 9.3%**。

---

## 🔬 分析

### 为什么 FlashInfer 在 CUDAGraph 下胜出

1. **优化的图捕获**: FlashInfer 内核专为 CUDAGraph 友好设计
2. **Paged Attention**: 图重放时更好的内存访问模式
3. **内核融合**: 更多操作融合到更少的内核启动中

### 为什么 FlashAttention 在 Eager 模式下胜出

1. **更低的内核启动开销**: FlashAttention 内核可能有稍低的单次启动成本
2. **更简单的执行路径**: 没有图捕获开销

### CUDAGraph 加速倍数

| 配置 | Eager | CUDAGraph | 加速 |
|------|-------|-----------|------|
| FlashInfer (短序列) | 675 | 1,647 | **2.44x** |
| FlashInfer (长序列) | 663 | 1,757 | **2.65x** |
| FlashAttention (短序列) | 682 | 1,628 | 2.39x |
| FlashAttention (长序列) | 671 | 1,522 | 2.27x |

FlashInfer 从 CUDAGraph 获益更多（2.44-2.65x）比 FlashAttention（2.27-2.39x）。

---

## 🚀 快速开始

### 依赖

```bash
pip install vllm>=0.10.2 flashinfer flash-attn
```

### 运行测试

```bash
# 克隆仓库
git clone https://github.com/davidsajare/flashinfer-vs-flashattention-benchmark.git
cd flashinfer-vs-flashattention-benchmark

# 基础对比（eager 模式）
python scripts/benchmark_vllm.py --model Qwen/Qwen2.5-0.5B-Instruct --output results.json

# 批量大小扫描
python scripts/benchmark_batch_sweep.py --quick --output batch_sweep.json

# 高级测试（CUDAGraph + 长序列）
python scripts/benchmark_advanced.py --output advanced.json

# 鲁棒性测试（3 次运行）
python scripts/robust_test.py --output robust.json
```

### 手动设置后端

```bash
# 使用 FlashInfer（vLLM 默认）
export VLLM_ATTENTION_BACKEND=FLASHINFER

# 使用 FlashAttention
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
```

---

## 💡 选型建议

| 使用场景 | 推荐后端 | 原因 |
|----------|---------|------|
| **生产服务** | FlashInfer（默认） | CUDAGraph + 长序列快 9-15% |
| **开发调试** | FlashAttention | Eager 模式稍快 |
| **批量推理任务** | FlashAttention | 大批量 + Eager 更好 |
| **交互式对话** | FlashInfer | CUDAGraph 延迟更低 |

### vLLM 配置示例

```python
from vllm import LLM

# 生产环境（启用 CUDAGraph - 默认）
llm = LLM(model="your-model")  # 默认使用 FlashInfer

# 开发环境（禁用 CUDAGraph 便于调试）
llm = LLM(model="your-model", enforce_eager=True)
# 考虑: export VLLM_ATTENTION_BACKEND=FLASH_ATTN
```

---

## ⚠️ 重要说明

### enforce_eager 的影响

`enforce_eager=True` 会禁用 CUDAGraph，导致：
- 允许更简单的调试（无图捕获问题）
- 允许动态张量形状
- **吞吐量降低 2-2.5 倍**

大多数生产环境测试**不应该**使用 `enforce_eager=True`。

### 版本兼容性

| vLLM 版本 | FlashInfer | FlashAttention | 备注 |
|-----------|------------|----------------|------|
| 0.10.x | 0.5.3 | 2.8.x | A100 测试 |
| 0.12.x | 0.5.3 | 2.8.x | 已测试 |
| 0.13.x | 0.6.0rc2 | 2.8.x | RTX 6000 测试 |

---

## 📁 仓库结构

```
flashinfer-vs-flashattention-benchmark/
```

---

## 📚 参考资料

- [vLLM: PagedAttention 论文 (Kwon et al., 2023)](https://arxiv.org/abs/2309.06180)
- [FlashAttention 论文 (Dao et al., 2022)](https://arxiv.org/abs/2205.14135)
- [FlashAttention-2 论文 (Dao, 2023)](https://arxiv.org/abs/2307.08691)
- [FlashInfer 论文](https://arxiv.org/abs/2501.01005)
- [FlashInfer GitHub](https://github.com/flashinfer-ai/flashinfer)
- [FlashAttention GitHub](https://github.com/Dao-AILab/flash-attention)
- [vLLM 文档](https://docs.vllm.ai/)

---

*作者: 魏新宇 (Microsoft AI GBB) | 测试时间: 2026-01-02/03*
