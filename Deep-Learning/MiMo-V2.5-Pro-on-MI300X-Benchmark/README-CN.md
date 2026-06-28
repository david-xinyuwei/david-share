# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD fork MTP/EAGLE，与小米 H200 参考数据对齐 benchmark。

本 repo 提供完整的复现脚本、启动命令、benchmark 结果和 server 日志。使用 2 台 Azure ND96isr_MI300X_v5 和指定 Docker 镜像，可以按下面步骤从 clean-room 容器重建 MI300X 环境，并运行 AMD 同一套 benchmark 脚本。PD-separated decode 必须把 RDMA 设备暴露给容器（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`），否则 Mooncake 可能 fallback 到 TCP，使高并发吞吐结果失效。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

[English](README.md) | 中文

---

## 核心发现（2026-06-26 更新）

AMD 6 月 26 日提供了新的 1P1D MI300X 测试栈：`sammysun0711/sglang` 的 `mimo_aiter_attn` 分支，`amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4`，Prefill 和 Decode 都走 `aiter backend + MTP=3`。

证据文件：

- 6/26 对齐报告：[`reports/amd_aiter_mtp_20260626_h200_alignment.md`](reports/amd_aiter_mtp_20260626_h200_alignment.md)
- 解析后的 TSV：[`data/amd_aiter_mtp_20260626_h200_alignment.tsv`](data/amd_aiter_mtp_20260626_h200_alignment.tsv)
- 原始日志：[`data/raw-logs/20260626-amd-aiter-mtp/`](data/raw-logs/20260626-amd-aiter-mtp/)

### 对口倍数结论

- **Prefill**：8K/64K 吞吐仍是 H200 快 1.8-2.0x；256K 长上下文单点 MI300X 快 2.14x。
- **Decode**：两边都固定 `SIMULATE_ACC_LEN=3` 后，MI300X 的 TPOT latency 接近 H200；但 output tok/s 仍然封顶，因为这次 MI300X 只跑了单个 decode service（`tp=8`，没有 DP/EP 扩展）。
- **关键发现**：H200 的 `accept_rate=0.75` 是通过 `SGLANG_SIMULATE_ACC_LEN=3` 模拟固定出来的，不是真实 draft model accuracy。

**Prefill throughput（output=1，主指标是 tok/s）**

| Context | MI300X tok/s | H200 tok/s | 结论 |
|---:|---:|---:|---|
| 8K | 16,323 | 31,950 | H200 快 1.96x |
| 64K | 15,047 | 27,400 | H200 快 1.82x |
| 256K | 37,252 | 17,400 | MI300X 快 2.14x |

**Decode 8K/1K，同口径（两边都 `SIMULATE_ACC_LEN=3`）**

| BS | MI300X TPOT | H200 TPOT | MI300X tok/s | H200 tok/s | 结论 |
|---:|---:|---:|---:|---:|---|
| 16 | 14.75 ms | 11.59 ms | 973 | 1,381 | H200 延迟和吞吐都领先 |
| 32 | 17.82 ms | 12.56 ms | 1,518 | 2,549 | H200 吞吐高 1.7x |
| 64 | 20.42 ms | 14.28 ms | 1,852 | 4,483 | MI300X 到达吞吐天花板 |
| 128 | 20.31 ms | 18.25 ms | 1,852 | 7,013 | TPOT 只差 11%，tok/s 仍差 3.8x |

**指标来源说明**：MI300X 的 TPOT 和 output tok/s 都来自 SGLang `bench_serving` 原始日志，是本次 MI300X 实测值。H200 的 TPOT 和 output tok/s 来自小米 H200 reference sheet；其中 H200 output tok/s 列与 `BS * 1000 / TPOT` 一致，没有再乘 DP=4。因此本 repo 主比较采用 H200 表自己给出的吞吐列，称为 **visible-BS-row comparison**；否则会把 H200 表中的吞吐口径二次放大。

### Prefill 吞吐 — 2026-06-26

| Input | MI300X aiter+MTP3 tok/s | H200 EP16/DP2 tok/s | MI/H200 | H200 快多少 | H200 EP32/DP4 tok/s | MI/H200 | H200 快多少 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8K | 16,323.45 | 31,950 | 51.1% | 1.96x | 27,500 | 59.4% | 1.68x |
| 64K | 15,047.08 | 27,400 | 54.9% | 1.82x | 23,000 | 65.4% | 1.53x |
| 256K | 37,251.55 | 17,400 | 214.1% | 0.47x | 13,425 | 277.5% | 0.36x |

### Decode 8K/1K — 2026-06-26

| BS 行 | MI300X TPOT ms | H200 TPOT ms | MI300X latency 倍数 | MI300X output tok/s | H200 output tok/s | MI/H200 throughput | H200 快多少 | MI accept len/rate | H200 accept rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 21.61 | 11.59 | 1.86x | 689.22 | 1,380.71 | 49.9% | 2.00x | 2.38/0.46 | 0.75 |
| 32 | 27.94 | 12.56 | 2.22x | 1,017.58 | 2,548.66 | 39.9% | 2.50x | 2.34/0.44 | 0.75 |
| 64 | 34.78 | 14.28 | 2.44x | 1,391.54 | 4,482.93 | 31.0% | 3.22x | 2.25/0.41 | 0.75 |
| 128 | 34.70 | 18.25 | 1.90x | 1,396.29 | 7,013.05 | 19.9% | 5.02x | 2.15/0.38 | 0.75 |

### aiter + MTP 状态

6/26 的新栈把 `aiter + MTP=3` 从 6/19 的低 accept 状态拉回来了一部分：`accept_length` 从约 1.6 提升到 2.15-2.38，`accept_rate` 从约 0.2 提升到 0.38-0.46。但 H200 表里的 accept rate 是 0.75，decode throughput 仍然是 H200 领先。

### 关键发现：H200 的 accept_rate = 0.75 是模拟值，不是真实值

小米 H200 参考表使用了 `SGLANG_SIMULATE_ACC_LEN=3` + `SGLANG_SIMULATE_ACC_METHOD=match-expected` 来**固定 MTP accept_length = 3.0**。这一点来自 AMD/SGLang 技术复核，并且可以从 SGLang 源码（`sglang/srt/speculative/eagle_utils.py` L519-530）直接验证：当 `SIMULATE_ACC_LEN > 0` 时，真实 verification 结果会被**完全替换**为模拟值（`predict.fill_(100)`, `num_correct_drafts.fill_(simulate_acc_len - 1)`）。H200 表中所有场景的 accept_rate 恒定为 0.75（零方差）与此一致。

这意味着 H200 的 TPOT 数字反映的是**理想 MTP 加速下的纯 kernel 延迟**，不是真实 draft model 预测准确率。正确的同口径对比需要 MI300X 也使用相同的 `SIMULATE_ACC_LEN=3` 设置。

### Decode 8K/1K — 同口径对比（两边都固定 accept_length=3）

原始日志：[`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/)  
N = 256 requests/BS 点；input=8192, output=1024, seed=12345, warmup=32。

| BS | MI300X Median TPOT (ms) | MI300X P99 (ms) | H200 TPOT (ms) | MI300X 慢几倍 | MI300X output tok/s | H200 output tok/s | MI/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 14.75 | 15.32 | 11.59 | 1.27x | 973.06 | 1,380.71 | 70.5% |
| 32 | 17.82 | 18.39 | 12.56 | 1.42x | 1,518.15 | 2,548.66 | 59.6% |
| 64 | 20.42 | 20.62 | 14.28 | 1.43x | 1,852.16 | 4,482.93 | 41.3% |
| 128 | 20.31 | 20.52 | 18.25 | **1.11x** | 1,851.63 | 7,013.05 | **26.4%** |

**核心结论**：在同口径（`SIMULATE_ACC_LEN=3`，和 H200 测试方法一致）下，MI300X decode Median TPOT 差距从 1.86-2.44x 缩小到 **1.11-1.43x**。BS≥128 时 MI300X 只差 H200 单路 decode 延迟 11%（N=256，P99 波动 <1ms）。但 output tok/s 仍然显示系统级拓扑差距：MI300X 约 973-1,852 tok/s，H200 报 1,381-7,013 tok/s。TPOT 反映单路延迟；output tok/s 同时反映 DP 并行度、scheduler、router 开销和 KV transfer。

### Decode 吞吐差距解释

即使 TPOT 同口径后差距很小，MI300X 吞吐在 BS≥64 时封顶在 ~1,852 tok/s，而 H200 报 4,483-7,013 tok/s。原因：

1. **单 decode service 天花板**：这次 MI300X 只启动了一个 `--tp-size 8` 的 decode server，没有 DP/EP 参数。BS≥64 后 output tok/s 不再增长，说明继续加并发主要增加排队，而不是增加 decode 产能。
2. **H200 吞吐来自 reference sheet，且与 `BS × 1000 / TPOT` 一致**；MI300X 吞吐是 `bench_serving` 端到端实测值（包含 PD router 开销、KV transfer 延迟、scheduler 间隙）
3. **MI300X scheduler 饱和**：output throughput 在 BS≥64 后不再增长，说明单 decode server 达到调度天花板

### 关键配置发现：CUDA Graph

> **⚠️ 2026-06-19 发现**：Decode server **禁止**使用 `--disable-cuda-graph`。禁用后 TPOT 退化 5 倍（23ms → 120ms）。仅 Prefill server 应禁用 CUDA Graph（长序列需要动态内存分配）。

---

## 历史 H200 对齐矩阵 — 6/18 与 6/19 基线

下面保留的是 6/18 triton+MTP 与 6/19 第一版 aiter attention 的历史结果。不要把这些数字和最上方 6/26 的 aiter+MTP3 对口倍数混在一起；6/26 是新的软件栈，证据和对比口径以上方新章节为准。

### Decode 8K TPOT (ms) — 三版本对比

| BS | ① triton+MTP=3 | ② aiter+MTP=3 | ③ aiter no-MTP | H200 |
|:--:|:---:|:---:|:---:|:---:|
| 16 | **13.71** | 22.78 | 23.23 | 11.59 |
| 32 | **16.53** | 29.14 | 27.29 | 12.56 |
| 64 | **19.70** | 35.29 | 34.62 | 14.28 |
| 128 | **22.16** | 40.45 | 35.96 | 18.25 |
| 192 | **22.56** | 44.36 | 41.79 | 23.29 |
| 256 | **22.86** | 47.23 | 43.64 | 27.38 |

### Decode 64K TPOT (ms)

| BS | ③ aiter no-MTP | ① triton+MTP=3 | H200 | aiter/H200 |
|:--:|:---:|:---:|:---:|:---:|
| 16 | 20.25 | 23.36 | 11.99 | 1.7× |
| 32 | 20.58 | 23.37 | 14.31 | 1.4× |
| 64 | 22.27 | 24.39 | 16.33 | 1.4× |
| 96 | OOM | 24.18 | 19.63 | — |

### Prefill 吞吐 (tok/s)

| 上下文长度 | aiter no-MTP | triton+MTP | 提升 | H200 | aiter/H200 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **8K** | **15,133** | 13,531 | +12% | 31,950 | 47% |
| **64K** | **16,125** | 11,500 | +40% | 27,400 | 59% |
| **256K** | **11,410** | 7,294 | +56% | 17,400 | 66% |

### aiter + MTP 状态变化

| 指标 | triton + MTP=3 | aiter + MTP=3（2026-06-19） | aiter + MTP=3（2026-06-26） |
|------|:---:|:---:|:---:|
| acceptance_rate | **0.666** | 0.2 | 0.38-0.46（BS16-128） |
| accept_length | **3.2** | 1.6 | 2.15-2.38（BS16-128） |
| Decode 8K BS16 TPOT | **13.71ms** | 22.78ms | 21.61ms |
| Decode 8K BS16 output tok/s | — | — | 689.22 |

> **状态**：6/26 新栈说明 `aiter + MTP=3` 已经不是 6/19 的低 accept failure mode；但它仍低于 triton+MTP 的 decode latency，也低于 H200 表里的 0.75 accept rate。按 6/26 H200 表自己的 output throughput 口径，H200 在 BS16 快 2.0x，在 BS128 快 5.0x。

---

## aiter 覆盖情况（2026-06-19 更新）

| 组件 | aiter 启用 | 后端 | 说明 |
|------|:---:|:---:|------|
| MoE expert dispatch (fused_moe) | ✅ | CK kernel | 384 expert routing |
| MoE topk routing | ✅ | aiter topk | Expert 选择 |
| MORI-EP token dispatcher | ✅ | aiter FP8 quant | 跨 GPU 通信 |
| FP8 quantization | ✅ | aiter per-token FP8 | 权重/激活量化 |
| LayerNorm | ✅ | aiter fused | Fused normalization |
| **Attention (prefill + decode)** | **✅** | **aiter `mha_batch_prefill`** | **2026-06-18 commit `f5fe8e944` 启用** |

---

## 硬件与软件栈

### 计算 — 双节点 Azure MI300X 集群

| 属性 | 值 |
|------|---|
| Azure SKU | `Standard_ND96isr_MI300X_v5`（每节点 8× MI300X） |
| GPU | AMD Instinct MI300X, `gfx942` (CDNA 3), **192 GB HBM3e**, 5.3 TB/s |
| 节点数 | 2（VMSS，相同 placement group — IB 保证） |
| 总 GPU 内存 | **16× 192 GB = 3,072 GB** |
| InfiniBand | 8× CX7 400G NDR/节点，实测 **368 Gbps**/端口 |

### 软件栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker 镜像 | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | AMD 0510 build |
| SGLang | `0.0.0.dev14146+gdb840d935.d20260626` | AMD 6/26 fork: `sammysun0711/sglang` branch `mimo_aiter_attn` |
| ROCm | 7.2.0 | |
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` | MoE/GEMM/FP8/LayerNorm/Attention 全部启用。Prefill 节点 sglang-kernel 0.4.3，Decode 节点 sglang-kernel 0.4.2.post1 |
| Mooncake | `0.3.7.post2` | PD 分离 KV cache 传输 |
| PyTorch | 2.9.1 | ROCm backend |

### 模型

| 属性 | 值 | 来源 |
|------|---|------|
| 模型 | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| 总参数 | 1.02 T | HF Model Card |
| 活跃参数 | 42 B / token | HF Model Card |
| Routed experts | 384, 每 token 8 个活跃 | HF Model Card |
| Attention | 混合：10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3 层 multi-layer EAGLE | HF Model Card |
| 量化 | FP8 E4M3 | HF Model Card |
| Checkpoint 大小 | 963 GB (34 safetensors) | 实测 |

---

## 架构 — PD 分离部署

```
Node 1 (8× MI300X)               Node 2 (8× MI300X)
┌────────────────────┐            ┌────────────────────┐
│  Prefill Server     │  ──IB──▶  │  Decode Server      │
│  TP=8, port 30000   │  Mooncake │  TP=8, port 30001   │
│  --disagg prefill   │  KV xfer  │  --disagg decode     │
│  cuda_graph OFF     │  8×CX7    │  cuda_graph ON ⚠️    │
│  aiter attention    │  400G     │  aiter attention     │
└────────────────────┘            └────────────────────┘
         │
    sglang_router (port 40000)
    --pd-disaggregation
```

> ⚠️ Decode server **必须保持 CUDA Graph 启用**（不加 `--disable-cuda-graph`），否则 TPOT 退化 5×。

---

## 已知问题

| 问题 | 状态 | 影响 |
|------|------|------|
| ~~aiter attention 后端~~ | **✅ 已修复** | commit `f5fe8e944` 已修复 |
| **aiter + MTP accept gap** | **⚠️ 改善但未闭环** | 6/19：accept rate 约 0.2 / accept length 约 1.6；6/26：accept length 提升到 2.15-2.38，accept rate 0.38-0.46，但 H200 仍为 0.75，decode throughput 仍落后 2.0-5.0x |
| **Decode CUDA Graph** | **⚠️ 关键配置** | Decode 禁用 CUDA Graph 导致 5× TPOT 退化 |
| TP16/DP2 DP-attention | ❌ 阻塞 | MORI dispatch heap OOM |
| 跨节点 MORI-EP=16 | ❌ 阻塞 | RCCL 不稳定 |
| 256K PD router drain | ⚠️ 调查中 | 并发 256K 请求触发 router 错误 |

---

## 结论

1. **Prefill 8K/64K 达到 H200 EP16/DP2 的 51-55%**：H200 仍快约 1.8-2.0x，主因是拓扑差异（EP8/DP1 vs EP16/DP2）
2. **256K Prefill 在 6/26 单点反超 H200 2.14x**：需要 repeated-run 验证
3. **Decode 同口径（SIMULATE_ACC_LEN=3）下 Median TPOT 差距仅 1.11-1.43x**：BS≥128 时只差 11%，基本打平。H200 表的 accept_rate=0.75 是用 `SGLANG_SIMULATE_ACC_LEN=3` 模拟固定的（来源：AMD 工程师孙霞克 2026-06-26 微信确认），不是真实 draft model 预测准确率
4. **Decode 吞吐差距主因是单 decode service 已饱和**：这次 MI300X 没有跑多 DP/EP，BS≥64 时吞吐封顶 ~1852 tok/s；继续提升需要新的多路 decode/EP 拓扑，而不是单纯加并发
5. **CUDA Graph 对 decode 性能至关重要**：decode server 禁用 = 5× 性能退化

---

## 参考资料

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` 分支（6/26 最新）](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [AMD SGLang Fork — `Mimo_mtp_enable` 分支（6/18 历史）](https://github.com/TianHao65/sglang/tree/Mimo_mtp_enable)
- [AMD MI308X PD Disaggregation Guide](https://github.com/TianHao65/sglang/blob/Mimo_Swa_Eable/MiMo-V2-Flash-MI308X_1P1D_Disaggregated_Inference_Guide.md)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

## 复现 2026-06-26 结果

所有脚本、环境信息和原始日志都在本 repo 的 [`scripts/20260626-amd-stack/`](scripts/20260626-amd-stack/) 下。

### 前置条件

- 2× Azure `Standard_ND96isr_MI300X_v5` 节点（VMSS，相同 placement group 保证 IB）
- Docker 镜像：`rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510`（SHA: `bb9d2e5ab1a6`）
- 模型：[XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) 下载到 `/data/models/MiMo-V2.5-Pro`
- SGLang：`sammysun0711/sglang` 分支 `mimo_aiter_attn`，commit `db840d935`
- aiter：`ROCm/aiter`，commit `7a8ff7dd4`

### 容器运行时要求

AMD reference 路径依赖容器级 RDMA 访问能力。以下要求是复现 recipe 的一部分，不是可选优化：

| 要求 | 为什么重要 | 验证方式 |
|---|---|---|
| `--privileged`、`/dev/mem`、`CAP_SYS_ADMIN` | 让 Mooncake 能发现并使用 RDMA HCA 进行 KV-cache transfer | 容器内执行 `ls /dev/infiniband/uverbs0 && ls /dev/mem` |
| 不存在旧同名源码目录，尤其是 `/sgl-workspace/aiter` | 避免 Python import 抢占 `/sgl-workspace/aiter_0625` | `test ! -d /sgl-workspace/aiter` |
| benchmark 显式指定 source tree | 避免 benchmark client 解析到错误 namespace package | 设置 `PYTHONPATH=/sgl-workspace/sglang_0625/python` 并验证 `sglang.benchmark.datasets` |

AMD original 的 BS16/32/64/128 fixed-acceptance 完整矩阵已经归档在本 repo。下面步骤说明如何在新的 MI300X VM 上重建环境，并运行同一套 AMD benchmark 脚本。

### Clean-room 运行门禁

以下门禁必须执行。此前出错主要集中在旧 `sglang.launch_server` 进程残留、router circuit breaker 状态残留、只看 `/health` 不做 worker registry 验证、以及 benchmark 日志被覆盖。

### 执行步骤

```bash
# 1. 两个节点启动干净容器
#    每次 clean-room 复现建议使用新的容器名。
CONTAINER=sglang
docker run -d --name $CONTAINER \
  --privileged \
  --ipc=host --network=host --shm-size=256g \
  --device=/dev/kfd --device=/dev/dri --device=/dev/mem \
  --group-add video \
  --cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined --security-opt label=disable \
  -v /data:/data rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 sleep infinity

# 1a. RDMA gate（两个节点都做，安装前先确认）
#    这一步必须通过；否则 Mooncake 会 fallback 到 TCP，BS64 吞吐会掉约 3 倍。
docker exec $CONTAINER bash -c "ls /dev/infiniband/uverbs0 && ls /dev/mem && echo RDMA_DEVICE_OK"

# 2. 容器内 clone 源码（两个节点都做）
docker exec -it $CONTAINER bash
mkdir -p /sgl-workspace && cd /sgl-workspace
git clone https://github.com/sammysun0711/sglang.git sglang_0625
cd sglang_0625 && git checkout db840d935
cd /sgl-workspace
git clone https://github.com/ROCm/aiter.git aiter_0625
cd aiter_0625 && git checkout 7a8ff7dd4

# 3. 安装 SGLang + aiter + Mooncake（两个节点）
#    重要：SGLang 必须使用 --no-deps，保留基础镜像的 ROCm torch/sglang-kernel 栈。
#    不加 --no-deps 会从 PyPI 拉 CUDA 版 torch、sglang-kernel 和 torch_c_dlpack_ext，破坏 ROCm 环境。
#    AITER 0625 需要 flydsl >=0.1.8；AMD 原始容器使用 flydsl 0.2.0。
#    先安装 flydsl，再给 aiter 使用 --no-deps，避免改动其他包。
cd /sgl-workspace/sglang_0625 && pip install -e "python[all_hip]" --no-deps
pip install flydsl==0.2.0 --no-deps
cd /sgl-workspace/aiter_0625 && pip install -e . --no-deps
pip install mooncake-transfer-engine==0.3.7.post2 --no-deps

# 3a. kernel parity gate（分节点处理）
# AMD 原始 runtime 的有效 sglang-kernel import path 是分节点的：
# - Prefill/router 节点：sglang-kernel 0.4.3
# - Decode 节点：sglang-kernel 0.4.2.post1 优先进入 sys.path
# 所以如果目标是性能 parity，不要在两个节点都无脑执行 setup_rocm.py。
# 只在 prefill/router 节点执行：
cd /sgl-workspace/sglang_0625/sgl-kernel && python3 setup_rocm.py install
# 在 decode 节点先检查当前 import path：
python3 - <<'PY'
import sgl_kernel
print(sgl_kernel.__file__)
PY

# 3b. benchmark client import gate
# benchmark 必须解析到预期 source tree，避免 namespace package 漂移。
export PYTHONPATH=/sgl-workspace/sglang_0625/python:${PYTHONPATH:-}
python3 - <<'PY'
import sglang.benchmark.datasets as datasets
print(datasets.__file__)
PY

# 3c. 源码目录污染门禁
# 旧 /sgl-workspace/aiter 会抢占 /sgl-workspace/aiter_0625；AMD original 没有这个旧目录。
test ! -d /sgl-workspace/aiter || { echo "ERROR: stale /sgl-workspace/aiter shadows aiter_0625"; exit 1; }

# 4. 下载模型（两个节点或共享存储）
huggingface-cli download XiaomiMiMo/MiMo-V2.5-Pro --local-dir /data/models/MiMo-V2.5-Pro

# 5. 部署 benchmark 脚本到容器工作目录
#    在宿主机 clone 本 repo，然后 docker cp 脚本进容器：
docker exec $CONTAINER mkdir -p /data/xisun
git clone https://github.com/david-xinyuwei/david-share.git
DIR=david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/20260626-amd-stack
docker cp $DIR/launch_tp8_noep_prefill_aiter_mtp.sh $CONTAINER:/data/xisun/
docker cp $DIR/launch_tp8_noep_decode_aiter_mtp.sh $CONTAINER:/data/xisun/
docker cp $DIR/launch_router.sh $CONTAINER:/data/xisun/
docker cp $DIR/run_benchmark_mimo_pro_decode.sh $CONTAINER:/data/xisun/
docker cp $DIR/run_benchmark_mimo_pro_prefill.sh $CONTAINER:/data/xisun/

# 6. 查找你的两个节点的 IB IP
#    在每个节点执行：ibdev2netdev | grep mlx5
export PREFILL_IB_IP=<你的 prefill 节点 IB IP>   # 例如 172.16.1.26
export DECODE_IB_IP=<你的 decode 节点 IB IP>      # 例如 172.16.1.122

# 7. 启动前清理旧进程和端口（两个节点都做）
#    每次 clean-room run 前都要做；旧 router/worker 状态会让 /health 误导你。
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|sglang_router.launch_router|bench_serving' || true"
docker exec $CONTAINER bash -c "ss -ltnp | grep -E ':(30000|30001|40000)' || true"
docker exec $CONTAINER bash -c "ps -eo pid,stat,cmd | grep defunct | grep -v grep || true"

# 8. 启动 server（每个 server 在独立终端/tmux pane 中运行，它们是前台常驻进程）
# 终端 A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/xisun && LOG_DIR=/data/xisun/cleanroom_logs bash launch_tp8_noep_prefill_aiter_mtp.sh"
# 终端 B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/xisun && LOG_DIR=/data/xisun/cleanroom_logs bash launch_tp8_noep_decode_aiter_mtp.sh"
# 终端 C — Node 1 (router, 等两个 server 打印 'ready' 后再启动):
docker exec $CONTAINER bash -c "cd /data/xisun && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP LOG_DIR=/data/xisun/cleanroom_logs bash launch_router.sh"

# 9. health + router registry smoke
#    只看 /health 不够，必须发一个小请求，确认 router 已注册 prefill/decode worker。
curl -fsS http://127.0.0.1:30000/health                 # prefill 节点
ssh <decode-node> "curl -fsS http://127.0.0.1:30001/health"  # decode 节点
curl -fsS http://127.0.0.1:40000/health                 # router 节点

docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. 跑 benchmark（Node 1，通过 router 端口 40000）
#     每次用唯一目录保存 stdout 和 rc，避免覆盖旧证据。
RUN_DIR=/data/xisun/verify-cleanroom-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/bench_decode && cd /data/xisun && LOG_DIR=$RUN_DIR/bench_decode bash run_benchmark_mimo_pro_decode.sh > $RUN_DIR/decode_full.out 2>&1; echo \$? > $RUN_DIR/decode_full.rc"
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/bench_prefill && cd /data/xisun && LOG_DIR=$RUN_DIR/bench_prefill bash run_benchmark_mimo_pro_prefill.sh > $RUN_DIR/prefill_full.out 2>&1; echo \$? > $RUN_DIR/prefill_full.rc"

# 必须满足的通过条件：decode rc=0、prefill rc=0；decode 有 4 个 Successful requests 汇总；prefill 有 3 个。
docker exec $CONTAINER bash -c "cat $RUN_DIR/decode_full.rc $RUN_DIR/prefill_full.rc"
docker exec $CONTAINER bash -c "grep -c 'Successful requests' $RUN_DIR/decode_full.out"    # 期望 4
docker exec $CONTAINER bash -c "grep -c 'Successful requests' $RUN_DIR/prefill_full.out"   # 期望 3
docker exec $CONTAINER bash -c "grep -c ClientPayloadError $RUN_DIR/decode_full.out $RUN_DIR/prefill_full.out || true"  # 期望均为 0

# 11.（可选）同口径 decode：模拟 accept_length=3
#    在 decode server 启动时加这两个环境变量，重启后重跑 decode benchmark：
#    export SGLANG_SIMULATE_ACC_LEN=3
#    export SGLANG_SIMULATE_ACC_METHOD=match-expected
```

> **关于 `--dataset-path`**：benchmark 脚本引用了 `/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json`。使用 `--dataset-name random` 时实际 prompt 是随机生成的，该文件仅用于 tokenizer 词表。可从 [HuggingFace](https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/tree/main) 下载，或直接删除 `--dataset-path` 行（SGLang ≥ 0.5.x 内置随机生成器）。

### 环境快照（2026-06-26）

```
Docker: rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510
SGLang: 0.0.0.dev14146+gdb840d935.d20260626 (sammysun0711/sglang@mimo_aiter_attn)
aiter:  amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4
torch:  2.9.1+rocm7.2.0.lw.git7e1940d4
triton: 3.6.0+git42270451
sglang-kernel: prefill/router 节点 0.4.3；decode 节点在 AMD 原始 runtime 中为 0.4.2.post1 优先
mooncake: 0.3.7.post2
```

---

*最后更新: 2026-06-27*
