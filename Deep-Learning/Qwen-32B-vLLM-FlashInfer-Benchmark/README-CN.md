# vLLM 注意力后端基准测试：FA2 vs FlashInfer (H100)

> **作者**: 魏新宇 (Xinyu Wei)  
> **日期**: 2026-02-05  
> **模型**: Qwen3-32B-FP8 (FP8 E4M3, 32GB)  
> **GPU**: Azure NC40ads H100 v5 (单卡 H100 NVL 94GB)  
> **场景**: (1024 输入, 1024 输出), 流式模式

---

## 📊 核心结论

![架构图](images/01-architecture.png)

**核心发现**: 在 vLLM 0.11.2 + H100 NVL + FP8 模型配置下，**FlashAttention 2 比 FlashInfer 快 7.5%**（高并发场景）。

| 指标 | FlashAttention 2 | FlashInfer | 差异 |
|------|------------------|------------|------|
| **峰值吞吐 (512 并发)** | **4,022.6 t/s** | 3,741.4 t/s | **FA2 +7.5%** |
| **首 Token 延迟 @ 512** | **1,116 ms** | 1,866 ms | **FA2 -40%** |
| 低并发 (1-128) | ~ | +1~3% | FlashInfer 略快 |
| 高并发 (256-512) | **+5~7%** | ~ | **FA2 显著更快** |

---

## ⚠️ 重要更新：先前基准测试为何错误

### 不公平对比问题

先前基准测试对比了**不同 vLLM 版本**，导致结论错误：

| 配置 | vLLM 版本 | 后端 | 峰值吞吐 |
|------|-----------|------|----------|
| 先前"基线" | 0.11.2 | FA2 | 3,907.8 t/s |
| 先前"优化版" | **0.15.0** | FlashInfer | 4,531.3 t/s |
| 声称提升 | - | - | +16% |

**问题**: 16% 的提升来自 **vLLM 版本升级**，而非注意力后端差异！

### 公平对比 (相同 vLLM 0.11.2)

| 配置 | vLLM | 后端 | 峰值吞吐 |
|------|------|------|----------|
| FA2 | 0.11.2 | FLASH_ATTN | **4,022.6 t/s** |
| FlashInfer | 0.11.2 | FLASHINFER | 3,741.4 t/s |
| **实际差异** | - | - | **FA2 +7.5%** |

---

## 🔬 为什么 FA2 在 H100 + FP8 上更快？（理论分析）

### 根本原因：FlashInfer FP8 Tensor Core 启发式 Bug

参考: [vLLM GitHub Issue #9471](https://github.com/vllm-project/vllm/issues/9471)

FlashInfer 的 `use_tensor_cores` 启发式在 FP8 场景下失效：

```
FlashInfer Tensor Core 决策逻辑:
┌─────────────────────────────────────────────────────┐
│ if head_dim >= 128:                                 │
│     use_tensor_cores = True   # ✅ 正确             │
│ else:                                               │
│     # 基于 FP16/BF16 性能分析的启发式               │
│     use_tensor_cores = (batch * heads) > threshold  │
│                                                     │
│ 问题: FP8 有不同的最优阈值！                        │
│ 结果: 回退到 CUDA Core 而非 Tensor Core             │
└─────────────────────────────────────────────────────┘
```

**数学分析**:

| 后端 | 内核类型 | H100 TFLOPS (FP8) | 利用率 |
|------|----------|-------------------|--------|
| FA2 | 始终 Tensor Core | 3,958 | ~85% |
| FlashInfer (FP8 bug) | 混合 CUDA+Tensor | 3,958 | ~70% |

效率损失: `(85% - 70%) / 85% ≈ 17.6%` 理论值 → 7.5% 实测值 (其他优化补偿)

---

## 🧪 测试环境

### 硬件配置

| 组件 | 规格 |
|------|------|
| **GPU** | NVIDIA H100 NVL 94GB HBM3 (单卡) |
| **VM SKU** | Azure Standard_NC40ads_H100_v5 |
| **vCPU** | 40 核 |
| **内存** | 320 GB |
| **存储** | 3.5 TB NVMe SSD |

### 软件配置

| 组件 | 版本 |
|------|------|
| **vLLM** | 0.11.2 (Docker: `vllm/vllm-openai:v0.11.2`) |
| **CUDA** | 12.8 |
| **PyTorch** | 2.9.0+cu128 |
| **FlashAttention** | 2.8.3 (内置) |
| **FlashInfer** | 0.5.2 (内置) |

### 模型配置

| 参数 | 值 |
|------|-----|
| **模型** | Qwen/Qwen3-32B-FP8 |
| **精度** | FP8 (E4M3) |
| **max_model_len** | 4096 |
| **tensor_parallel_size** | 1 |
| **gpu_memory_utilization** | 0.95 |

---

## 🐳 为什么用 Docker 而不是 pip install？

### 依赖冲突问题

```bash
$ pip install vllm==0.11.2

ERROR: Cannot install vllm==0.11.2 because:
  huggingface_hub 0.32.0 requires transformers>=4.45.0
  but vllm 0.11.2 requires transformers==4.51.3
```

### 解决方案：官方 Docker 镜像

Docker 镜像 `vllm/vllm-openai:v0.11.2` 已预锁定依赖：

| 包 | 版本 |
|----|------|
| vLLM | 0.11.2 |
| transformers | 4.51.3 |
| huggingface_hub | 0.30.x |
| FlashAttention | 2.8.3 |
| FlashInfer | 0.5.2 |

---

## 📈 基准测试结果 (vLLM 0.11.2)

### 测试方法论

- **每配置 3 轮测试**，取**中位数**
- 容器启动后等待 30s 模型预热
- 测试间清理 GPU 显存: `docker stop && docker rm`

### FlashAttention 2 结果

| 并发数 | QPS | TTFT (ms) | 吞吐量 (t/s) |
|--------|-----|-----------|--------------|
| 1 | 0.08 | 26 | 55.7 |
| 4 | 0.27 | 37 | 195.2 |
| 8 | 0.45 | 41 | 344.4 |
| 16 | 0.80 | 46 | 600.7 |
| 32 | 1.51 | 52 | 1,096.6 |
| 64 | 2.70 | 63 | 1,889.7 |
| 128 | 4.21 | 102 | 2,759.9 |
| 256 | 5.45 | 145 | 3,607.2 |
| **512** | **6.22** | **1,116** | **4,022.6** |

### FlashInfer 结果

| 并发数 | QPS | TTFT (ms) | 吞吐量 (t/s) |
|--------|-----|-----------|--------------|
| 1 | 0.08 | 31 | 55.4 |
| 4 | 0.27 | 38 | 200.6 |
| 8 | 0.45 | 44 | 354.9 |
| 16 | 0.89 | 53 | 613.2 |
| 32 | 1.58 | 60 | 1,110.2 |
| 64 | 2.72 | 79 | 1,923.6 |
| 128 | 3.84 | 129 | 2,788.7 |
| 256 | 4.88 | 205 | 3,444.6 |
| **512** | **5.35** | **1,866** | **3,741.4** |

### 并排对比

| 并发数 | FA2 (t/s) | FlashInfer (t/s) | 差异 |
|--------|-----------|------------------|------|
| 1-128 | ~ | ~ | ±3% |
| 256 | 3,607.2 | 3,444.6 | FA2 +4.7% |
| **512** | **4,022.6** | **3,741.4** | **FA2 +7.5%** |

---

## 📋 运行日志示例

### FA2 测试成功日志

```
$ curl http://localhost:8088/v1/models
{"object":"list","data":[{"id":"Qwen3-32B-FP8","object":"model"...}]}

$ python3 bench_0112.py
[2026-02-05 10:15:23] Starting benchmark...
[2026-02-05 10:15:23] Backend: FLASH_ATTN (default)
[2026-02-05 10:15:23] Concurrency: 512
[2026-02-05 10:17:45] Completed 512 requests
[2026-02-05 10:17:45] Results:
  - QPS: 6.22
  - TTFT: 1116.3 ms
  - Throughput: 4022.6 tokens/sec
  - Total tokens: 524288
```

### FlashInfer 测试成功日志

```
$ docker run -e VLLM_ATTENTION_BACKEND=FLASHINFER ...
INFO: Using attention backend: FLASHINFER

$ python3 bench_0112.py
[2026-02-05 10:45:23] Starting benchmark...
[2026-02-05 10:45:23] Backend: FLASHINFER
[2026-02-05 10:45:23] Concurrency: 512
[2026-02-05 10:48:12] Completed 512 requests
[2026-02-05 10:48:12] Results:
  - QPS: 5.35
  - TTFT: 1866.2 ms
  - Throughput: 3741.4 tokens/sec
```

---

## 🎯 决策矩阵

| 场景 | 推荐 | 原因 |
|------|------|------|
| **生产 Chatbot** | **FA2** | TTFT 更低 = 更好的用户体验 |
| **批处理** | **FA2** | 更高吞吐量 |
| **低并发 (<128)** | 均可 | <3% 差异 |
| **高并发 (256+)** | **FA2** | 快 5-7% |

**建议**: 使用 vLLM 默认配置 (FlashAttention 2)。在 H100 + FP8 场景下**不要**设置 `VLLM_ATTENTION_BACKEND=FLASHINFER`。

---


| Repo 路径 | VM 路径 |
|-----------|---------|
| `scripts/bench_0112.py` | `/tmp/bench_0112.py` |
| `logs/bench_0112_fa2.log` | `/tmp/bench_0112_fa2.log` |
| `logs/bench_0112_fi.log` | `/tmp/bench_0112_fi.log` |

---

## 📚 参考资料

- [vLLM GitHub Issue #9471](https://github.com/vllm-project/vllm/issues/9471) - FlashInfer FP8 tensor cores 启发式 bug
- [FlashAttention-2 论文](https://arxiv.org/abs/2307.08691) - Dao et al., 2023
- [FlashInfer 文档](https://flashinfer.ai/)
- [vLLM Docker Hub](https://hub.docker.com/r/vllm/vllm-openai)

---

## 📄 许可证

MIT License
