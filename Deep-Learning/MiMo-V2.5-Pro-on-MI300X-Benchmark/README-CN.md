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

**2026-07-07 最新 CK 复现**：AMD 将 triton A8W8 blockwise GEMM 路径替换为 **CK A8W8 blockwise GEMM bpreshuffle** 后，我们按 AMD 原始脚本严格复现，`decode_full.rc=0`、`prefill_full.rc=0`。Decode mean TPOT 与 AMD CK 表差异不超过 1.2%；Prefill input throughput 与脚本实际 `--chunked-prefill-size 32768` 对应的 CK 32K 列差异不超过 1.2%。

**2026-07-08 CK 并发扩展**：在不改动 7/7 严格复现证据的基础上，新增更宽的并发 sweep。Decode 8K/1K 跑到 concurrency 256，并从 concurrency 64 开始稳定在约 2,200 output tok/s；Prefill 8K/64K 跑到 concurrency 8，256K 只跑通 concurrency 1/2，concurrency 4/8 在 warmup 阶段因为没有健康 prefill worker 失败。

证据文件：

- 7/7 CK 严格复现原始日志：[`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/)
- 7/7 CK 结果摘要：[`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md)
- 7/7 CK 脚本快照：[`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/)
- 7/8 CK 并发扩展原始日志：[`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/)
- 7/8 CK 并发扩展结果摘要：[`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md)
- 7/8 CK 并发扩展脚本快照：[`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/)
- 同口径 Decode 原始日志：[`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/)

### 对口倍数结论

- **Prefill**：MI300X/H200 吞吐比例为 8K 51.1%、64K 54.9%、256K 长上下文单点 214.1%。
- **Decode**：两边都固定 `SIMULATE_ACC_LEN=3` 后，MI300X 的 TPOT latency 接近 H200；output tok/s 也按同一 visible-BS-row 口径展示。
- **关键发现**：H200 的 `accept_rate=0.75` 是通过 `SGLANG_SIMULATE_ACC_LEN=3` 模拟固定出来的，不是真实 draft model accuracy。

**Prefill throughput（output=1；越高越好）**

| Context | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|
| 8K | 16,323 | 31,950 | 51.1% |
| 64K | 15,047 | 27,400 | 54.9% |
| 256K | 37,252 | 17,400 | **214.1%** |

Prefill 不展示 TPOT，因为这个测试是 `output=1`：首 token 之后没有稳定的 decode-token 阶段。Prefill 用 input-token throughput（`tok/s`）对比；TPOT 放在下面 Decode 表里。

**Decode 8K/1K，同口径（两边都 `SIMULATE_ACC_LEN=3`）**

| BS | MI300X Median TPOT | MI300X P99 | H200 TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 14.75 ms | 15.32 ms | 11.59 ms | 1.27x | 973 | 1,381 | 70.5% |
| 32 | 17.82 ms | 18.39 ms | 12.56 ms | 1.42x | 1,518 | 2,549 | 59.6% |
| 64 | 20.42 ms | 20.62 ms | 14.28 ms | 1.43x | 1,852 | 4,483 | 41.3% |
| 128 | 20.31 ms | 20.52 ms | 18.25 ms | **1.11x** | 1,852 | 7,013 | 26.4% |

TPOT 越低越好；output tok/s 越高越好。

**指标来源说明**：MI300X 的 TPOT 和 output tok/s 来自 SGLang `bench_serving` 原始日志，是本次 MI300X 实测值。H200 的 TPOT 和 output tok/s 来自小米 H200 reference sheet；H200 output tok/s 列等于 `BS × 1000 / TPOT`，这里按 H200 表自己的 visible-BS-row throughput 展示。

---

## 2026-07-07 AMD CK A8W8 GEMM 严格复现

本轮严格执行 AMD `测试步骤.txt` 中的原始流程：启动 Prefill、启动 Decode、启动 Router、运行 Decode benchmark、运行 Prefill benchmark。没有修改 AMD launch 或 benchmark 脚本；唯一变化是把这些前台常驻命令放到独立会话中执行，避免 router/server 前台进程阻塞后续步骤。

### Decode 8K/1K — AMD 原始脚本严格复现

N = 256 requests/BS 点；target concurrency = 16/32/64/128；`decode_full.rc=0`；benchmark 输出中没有 `ClientPayloadError`、`Traceback`、`Exception`、`ERROR`、`No available`、`unhealthy`、`TimedOut` 等错误标记。

| BS | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | AMD CK mean TPOT ms | 相对 AMD CK 差异 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,299.18 | 10.64 | 10.83 | 11.57 | 10.59 | +0.5% |
| 32 | 256 | 1,910.75 | 13.50 | 13.73 | 14.25 | 13.43 | +0.5% |
| 64 | 256 | 2,188.05 | 15.10 | 15.53 | 16.58 | 14.92 | +1.2% |
| 128 | 256 | 2,209.43 | 14.52 | 14.83 | 15.82 | 14.55 | -0.2% |

**解读**：严格复现结果与 AMD 2026-07-07 CK decode 表在 mean TPOT 上差异约 1.2% 以内，output throughput 差异约 0.4% 以内。这说明 CK GEMM 路径确实显著改善了 MI300X decode TPOT。

### Prefill — AMD 原始脚本严格复现

N = 16 requests/input length；target concurrency = 4；`prefill_full.rc=0`；benchmark 输出中没有错误标记。实测脚本启动参数是 `--chunked-prefill-size 32768`，虽然日志文件名里写了 `chunk_128k`，所以最干净的对比对象是 AMD CK 32K chunk 列。

| ISL/OSL | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms | AMD CK 32K input tok/s | 相对 AMD CK 差异 |
|---:|---:|---:|---:|---:|---:|---:|
| 8K/1 | 16 | 16,715.80 | 1,849.62 | 2,709.97 | 16,924.08 | -1.2% |
| 64K/1 | 16 | 17,254.14 | 14,107.62 | 16,674.08 | 17,223.51 | +0.2% |
| 256K/1 | 16 | 37,492.80 | 19,278.17 | 86,264.51 | 37,241.84 | +0.7% |

**注意**：Router 在 64K 长 Prefill 阶段出现过短暂 `/health` timeout warning，但 `/generate` 请求继续返回 HTTP 200，decode 和 prefill benchmark 脚本均正常完成。

---

## 2026-07-08 CK A8W8 并发扩展测试

本轮不修改 2026-07-07 AMD CK 严格复现的原始证据，只新增更宽的并发矩阵，用来确认 CK 路径的 saturation 和长上下文并发边界。

- 原始证据：[`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/)
- 结果摘要：[`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md)
- 脚本快照：[`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/)

### Decode 8K/1K — 高并发 sweep

N = 256 requests/并发点；output length = 1024；warmup requests = 32；`decode_full.rc=0`。

| Concurrency | Successful requests | Output tok/s | Mean TPOT ms | P99 TPOT ms | Mean TTFT ms |
|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,321.50 | 10.79 | 11.65 | 1,191.13 |
| 32 | 256 | 1,914.27 | 13.37 | 14.26 | 2,847.33 |
| 64 | 256 | 2,198.77 | 15.49 | 17.08 | 11,853.11 |
| 96 | 256 | 2,200.63 | 15.06 | 16.31 | 23,666.92 |
| 128 | 256 | 2,203.65 | 14.83 | 16.22 | 33,429.51 |
| 192 | 256 | 2,202.57 | 14.72 | 16.28 | 47,910.53 |
| 256 | 256 | 2,207.97 | 14.60 | 16.36 | 55,466.82 |

**解读**：Decode throughput 在 concurrency 64 左右进入 plateau，并一直稳定到 concurrency 256。更高并发主要增加排队时间和 TTFT，不再明显提升 output-token throughput。

### Prefill — 并发 sweep

N = 16 requests/点；output length = 1；warmup requests = 1。由于 256K/con4 和 256K/con8 在 warmup 阶段失败，完整 prefill 矩阵的 `prefill_full.rc=1`。

| Input tokens | Concurrency | rc | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms |
|---:|---:|---:|---:|---:|---:|---:|
| 8192 | 1 | 0 | 16 | 14,811.18 | 552.33 | 589.05 |
| 8192 | 2 | 0 | 16 | 16,982.94 | 958.32 | 1,368.64 |
| 8192 | 4 | 0 | 16 | 16,783.88 | 1,840.95 | 2,680.40 |
| 8192 | 8 | 0 | 16 | 18,617.41 | 3,210.75 | 4,690.96 |
| 65536 | 1 | 0 | 16 | 16,602.69 | 3,946.37 | 4,869.77 |
| 65536 | 2 | 0 | 16 | 18,077.28 | 7,122.69 | 9,003.76 |
| 65536 | 4 | 0 | 16 | 16,904.74 | 14,231.93 | 16,774.44 |
| 65536 | 8 | 0 | 16 | 17,252.39 | 24,482.37 | 31,726.89 |
| 262144 | 1 | 0 | 16 | 35,452.56 | 6,995.06 | 22,647.57 |
| 262144 | 2 | 0 | 16 | 37,429.63 | 12,417.08 | 47,335.03 |
| 262144 | 4 | 1 | NA | NA | NA | NA |
| 262144 | 8 | 1 | NA | NA | NA | NA |

**边界**：256K/con4 和 256K/con8 都是在正式测量前的 warmup 阶段失败，错误为 `No available prefill workers (all circuits open or unhealthy)`。这应写作“长上下文高 prefill 并发下的 worker/circuit-health 边界”，不是一个已经测得的吞吐退化点。

### Prefill 吞吐 — 2026-06-26

| Input | MI300X aiter+MTP3 tok/s | H200 EP16/DP2 tok/s | MI300X/H200 EP16/DP2 | H200 EP32/DP4 tok/s | MI300X/H200 EP32/DP4 |
|---:|---:|---:|---:|---:|---:|
| 8K | 16,323.45 | 31,950 | 51.1% | 27,500 | 59.4% |
| 64K | 15,047.08 | 27,400 | 54.9% | 23,000 | 65.4% |
| 256K | 37,251.55 | 17,400 | 214.1% | 13,425 | 277.5% |

本节只报告 Prefill 吞吐。因为运行只生成 1 个 token（`output=1`），这里没有可用于计算稳定 TPOT 的 decode 阶段。

### 关键发现：H200 的 accept_rate = 0.75 是模拟值，不是真实值

小米 H200 参考表使用了 `SGLANG_SIMULATE_ACC_LEN=3` + `SGLANG_SIMULATE_ACC_METHOD=match-expected` 来**固定 MTP accept_length = 3.0**。这一点来自 AMD/SGLang 技术复核，并且可以从 SGLang 源码（`sglang/srt/speculative/eagle_utils.py` L519-530）直接验证：当 `SIMULATE_ACC_LEN > 0` 时，真实 verification 结果会被**完全替换**为模拟值（`predict.fill_(100)`, `num_correct_drafts.fill_(simulate_acc_len - 1)`）。H200 表中所有场景的 accept_rate 恒定为 0.75（零方差）与此一致。

这意味着 H200 的 TPOT 数字反映的是**理想 MTP 加速下的纯 kernel 延迟**，不是真实 draft model 预测准确率。正确的同口径对比需要 MI300X 也使用相同的 `SIMULATE_ACC_LEN=3` 设置。

### Decode 8K/1K — 同口径对比（两边都固定 accept_length=3）

原始日志：[`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/)  
N = 256 requests/BS 点；input=8192, output=1024, seed=12345, warmup=32。

| BS | MI300X Median TPOT (ms) | MI300X P99 (ms) | H200 TPOT (ms) | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 14.75 | 15.32 | 11.59 | 1.27x | 973.06 | 1,380.71 | 70.5% |
| 32 | 17.82 | 18.39 | 12.56 | 1.42x | 1,518.15 | 2,548.66 | 59.6% |
| 64 | 20.42 | 20.62 | 14.28 | 1.43x | 1,852.16 | 4,482.93 | 41.3% |
| 128 | 20.31 | 20.52 | 18.25 | **1.11x** | 1,851.63 | 7,013.05 | 26.4% |

**核心结论**：在同口径（`SIMULATE_ACC_LEN=3`，和 H200 测试方法一致）下，MI300X decode Median TPOT 是 H200 的 **1.11-1.43x**。BS=128 时 MI300X 只差 H200 单路 decode 延迟 11%（N=256，P99 波动 <1ms）。output tok/s 比例较低，因为它除了 per-token latency，还受 serving topology 和 scheduler 影响。

### 关键配置发现：CUDA Graph

> **⚠️ 2026-06-19 发现**：Decode server **禁止**使用 `--disable-cuda-graph`。禁用后 TPOT 退化 5 倍（23ms → 120ms）。仅 Prefill server 应禁用 CUDA Graph（长序列需要动态内存分配）。

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
| **Decode CUDA Graph** | **⚠️ 关键配置** | Decode 禁用 CUDA Graph 导致 5× TPOT 退化 |
| TP16/DP2 DP-attention | ❌ 阻塞 | MORI dispatch heap OOM |
| 跨节点 MORI-EP=16 | ❌ 阻塞 | RCCL 不稳定 |
| 256K PD router drain | ⚠️ 调查中 | 并发 256K 请求触发 router 错误 |

---

## 结论

1. **Prefill 8K/64K 达到 H200 EP16/DP2 的 51-55%**：H200 仍快约 1.8-2.0x，主因是拓扑差异（EP8/DP1 vs EP16/DP2）
2. **256K Prefill 在 6/26 单点反超 H200 2.14x**：需要 repeated-run 验证
3. **Decode 同口径（SIMULATE_ACC_LEN=3）下 Median TPOT 差距仅 1.11-1.43x**：BS≥128 时只差 11%，基本打平。H200 表的 accept_rate=0.75 是用 `SGLANG_SIMULATE_ACC_LEN=3` 模拟固定的（来源：AMD 工程师孙霞克 2026-06-26 微信确认），不是真实 draft model 预测准确率
4. **CUDA Graph 对 decode 性能至关重要**：decode server 禁用 = 5× 性能退化

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

*最后更新: 2026-07-07*
