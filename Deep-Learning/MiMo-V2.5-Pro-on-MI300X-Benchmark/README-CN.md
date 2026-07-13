# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + [`aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9) 的模型专用 fused-MoE tuning，与小米 H200 参考数据做 benchmark 对比。

本 repo 提供完整的复现脚本、启动命令、benchmark 结果和 server 日志。使用 2 台 Azure ND96isr_MI300X_v5 和指定 Docker 镜像，可以按下面步骤从 clean-room 容器重建 MI300X 环境，并运行 AMD benchmark 脚本。PD-separated decode 必须把 RDMA 设备暴露给容器（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`），否则 Mooncake 会 fallback 到 TCP，高并发吞吐结果无效。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

[English](README.md) | 中文

---

## 架构

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## 核心结论

**Prefill throughput（2026-07-13 corrected single-full run，1P1D prefill 阶段，output=1；越高越好）**

| Context | Concurrency | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 8K | 4 | 18,161.81 | 31,950 | 56.8% |
| 64K | 4 | 18,763.17 | 27,400 | 68.5% |
| 256K | 4 | 12,389.64 | 17,400 | 71.2% |

全部 12 个 1P1D Prefill 点均完成 16/16 requests，`rc=0`、context length 262151，且 Prefill、Decode、router 三类日志 fatal marker 均为 0。上表展示 concurrency 4 以便与 H200 reference 对比；下文给出完整 concurrency 1/2/4/8 矩阵。

**Decode 8K/1K（2026-07-13 tuned fused-MoE 复测，`SIMULATE_ACC_LEN=3`；TPOT 越低越好）**

| BS | Concurrency | MI300X Median TPOT | H200 Median TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 16 | 10.79 ms | 11.59 ms | **0.93x** | 1,303.44 | 1,381 | 94.3% |
| 32 | 32 | 13.91 ms | 12.56 ms | 1.11x | 1,930.10 | 2,549 | 75.7% |
| 64 | 64 | 17.82 ms | 14.28 ms | 1.25x | 2,462.83 | 4,483 | 54.9% |
| 128 | 128 | 16.93 ms | 18.25 ms | **0.93x** | 2,468.95 | 7,013 | 35.2% |

Decode 表里 `BS` 等于 target concurrency，和 H200 reference 的 load shape 对齐。

### 关键发现

- **修正后的 1P1D Prefill 覆盖全部 12 点：**8K/64K/256K 的 concurrency 1/2/4/8 均为 16/16 requests。256K 在 context length 262151 下已有效，整个并发 sweep 稳定在约 12.4K tok/s。
- **核心 Decode 可在 fresh services 间复现：** concurrency 16/32/64/128 的两次 run 中，output throughput 最大偏差 2.14%，mean TPOT 最大偏差 1.02%。
- **Decode median TPOT 在 BS=16 和 BS=128 仍低于 H200 reference**（均为 0.93x）。扩展 sweep 接受 concurrency 8–192；256 因 Prefill watchdog dump 被拒绝。
- **修正后的 DP=2 Prefill 接受 14/15 点：**8K/64K 的 concurrency 1/2/4/8/16，以及 256K 的 concurrency 1/2/4/8，均完成 32/32 requests 并有有效的双 worker distribution。256K/concurrency-16 因 node 1 GPU memory-aperture fault 被拒绝。
- **单轮扩展矩阵最终结论：**共测量 35 点，33 点接受，2 个 rejected boundaries 分别是 Decode concurrency 256 和 DP=2 256K/concurrency 16。另一次 fresh-service DP=2 256K/concurrency-2 attempt 也发生双节点 GPU memory-aperture fault；虽然 targeted retry 成功，该归档证据仍保留在 robustness verdict 中。

### 方法论说明

公开 aiter commit 增加的是模型专用 fused-MoE tuning CSV，不是 kernel 源码改动。`--speculative-num-draft-tokens=4` 表示 3 个 proposed draft tokens 加 1 个 bonus target token。`accept length=3` 包含该 bonus token，因此实际接受 2 个 draft tokens，reported draft accept rate 为 `2/3=0.67`。MI300X 使用真实 expert routing，H200 reference 使用理想均衡路由。AMD 报告的单-kernel latency 降低 37.6% 没有独立 microbenchmark log，因此不纳入我们的实测结论。

---

## Decode — 详细结果

### Decode 8K/1K — 扩展并发

每点 requests = 256；input length = 8,192；output length = 1,024；warmup = 32；target concurrency = 8/16/32/64/96/128/192/256。所有 client 都以 `0` 退出并报告 256/256 responses；但 server evidence 因 Prefill service 出现 watchdog thread dumps 而拒绝 concurrency 256。

| Concurrency | Successful requests | Output tok/s | Mean TTFT ms | P99 TTFT ms | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | 状态 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 8 | 256 | 930.00 | 863.69 | 3,041.31 | 7.65 | 7.61 | 8.11 | 已接受 |
| 16 | 256 | 1,303.44 | 1,398.73 | 5,864.28 | 10.72 | 10.79 | 11.55 | 已接受 |
| 32 | 256 | 1,930.10 | 2,296.89 | 11,931.01 | 13.68 | 13.91 | 14.36 | 已接受 |
| 64 | 256 | 2,462.83 | 7,406.18 | 23,962.77 | 17.08 | 17.82 | 18.49 | 已接受 |
| 96 | 256 | 2,497.69 | 18,273.38 | 35,014.59 | 15.89 | 16.25 | 17.96 | 已接受 |
| 128 | 256 | 2,468.95 | 27,128.38 | 47,023.69 | 16.45 | 16.93 | 18.09 | 已接受 |
| 192 | 256 | 2,500.54 | 40,956.57 | 70,422.68 | 15.98 | 16.78 | 17.75 | 已接受 |
| 256 | 256 | 729.98 | 29,013.34 | 196,140.78 | 108.58 | 16.79 | 350.94 | 已拒绝：Prefill watchdog |

**解读**：concurrency 64–192 的 throughput 稳定在约 2.47–2.50K tok/s，而 TTFT 随 queue depth 上升。concurrency 256 超出本轮可接受 operating envelope；只看 client exit code 会掩盖 service failure。

#### 核心 Decode Fresh-Service 可复现性

AMD headline concurrencies 在两次独立 fresh-service run 中测量。Throughput 最大偏差为 2.14%，mean TPOT 最大偏差为 1.02%。

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | Throughput delta | Mean TPOT delta |
|---:|---:|---:|---:|---:|
| 16 | 1,331.98 | 1,303.44 | -2.14% | -1.02% |
| 32 | 1,936.24 | 1,930.10 | -0.32% | +0.22% |
| 64 | 2,457.73 | 2,462.83 | +0.21% | +0.47% |
| 128 | 2,486.89 | 2,468.95 | -0.72% | -0.66% |

- 原始证据：[`data/raw-logs/20260713-amd-tuned-moe-retest/decode/`](data/raw-logs/20260713-amd-tuned-moe-retest/decode/)
- 详细报告：[`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md)
- 复现 bundle：[`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/)

---

## Prefill — 详细结果

### Prefill — 扩展并发与修正后的 Context

每点 requests = 16；output length = 1；target concurrency = 1/2/4/8；context length = 262151。

| Input | Concurrency | Successful requests | Input tok/s | Mean TTFT ms | 状态 |
|---:|---:|---:|---:|---:|---|
| 8K | 1 | 16 | 16,835.22 | 485.70 | 已接受 |
| 8K | 2 | 16 | 19,618.25 | 829.40 | 已接受 |
| 8K | 4 | 16 | 18,161.81 | 1,612.03 | 已接受 |
| 8K | 8 | 16 | 21,004.97 | 2,817.91 | 已接受 |
| 64K | 1 | 16 | 18,057.01 | 3,628.49 | 已接受 |
| 64K | 2 | 16 | 19,860.45 | 6,481.41 | 已接受 |
| 64K | 4 | 16 | 18,763.17 | 12,970.83 | 已接受 |
| 64K | 8 | 16 | 18,765.43 | 22,530.68 | 已接受 |
| 256K | 1 | 16 | 12,381.87 | 21,170.66 | 已接受 |
| 256K | 2 | 16 | 12,378.06 | 41,208.61 | 已接受 |
| 256K | 4 | 16 | 12,389.64 | 77,254.06 | 已接受 |
| 256K | 8 | 16 | 12,402.23 | 133,251.83 | 已接受 |

**解读**：8K 在 concurrency 8 达到最高值，64K 在 concurrency 2–8 基本持平。修正后的 256K 路径稳定在约 12.4K tok/s；提高 concurrency 主要增加 TTFT。由于 output length = 1，持续 GPU 压力集中在 Prefill；Decode 只完成 transferred-KV handoff 和 1-token generation。

- 复现 bundle：[`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/)

---

## Prefill Scaling — AMD 2-Node DP=2/TP=8

我们使用相同 Docker image 和 tuned fused-MoE configuration 独立复测了 2-node DP=2/TP=8 prefill-only server 路径。这个测试**不包含** P→D KV-cache 传输开销；如果要做 2P1D E2E 测试，需要 3 nodes。

### 测试方法

```bash
# 跑 DP=2, TP=8 的 2-node prefill benchmark。
./launch_dp2_node0.sh       # node 0, port 30000
./launch_dp2_node1.sh       # node 1, port 30001
./launch_dp2_router.sh      # node 0
./benchmark_dp2_prefill.sh  # node 0
```

### 结果

| ISL/OSL | Concurrency | Successful requests | Aggregate input tok/s | Worker request deltas | 状态 |
|---:|---:|---:|---:|---:|---|
| 8K/1 | 1 | 32 | 20,751.73 | 17/16 | 已接受 |
| 8K/1 | 2 | 32 | 41,201.86 | 16/17 | 已接受 |
| 8K/1 | 4 | 32 | 43,401.70 | 17/16 | 已接受 |
| 8K/1 | 8 | 32 | 46,113.92 | 16/17 | 已接受 |
| 8K/1 | 16 | 32 | 46,747.01 | 17/16 | 已接受 |
| 64K/1 | 1 | 32 | 19,695.02 | 16/17 | 已接受 |
| 64K/1 | 2 | 32 | 38,984.45 | 17/16 | 已接受 |
| 64K/1 | 4 | 32 | 38,382.03 | 16/17 | 已接受 |
| 64K/1 | 8 | 32 | 38,204.80 | 17/16 | 已接受 |
| 64K/1 | 16 | 32 | 38,155.28 | 16/17 | 已接受 |
| 256K/1 | 1 | 32 | 12,783.28 | 17/16 | 已接受 |
| 256K/1 | 2 | 32 | 25,063.73 | 17/16 | targeted retry 后接受 |
| 256K/1 | 4 | 32 | 24,923.63 | 16/17 | 已接受 |
| 256K/1 | 8 | 32 | 24,765.29 | 17/16 | 已接受 |
| 256K/1 | 16 | 24 | 18,742.17 | 未生成 | 已拒绝：GPU memory-aperture fault |

所有 accepted points 都通过 exact request count、context、client、双 worker distribution 和 service evidence gates。被拒绝的 concurrency-16 client 仍以 `0` 退出，再次证明只看 client exit status 不足以验收。这些是双节点 aggregate capacity，不能直接与单节点 H200 对比。

### 256K Correctness Guard

当 `random_input_len=262144` 时，HTTP 200 error payload 可能被 client-only success counter 误判。后续 262149 retry 同样撤回，因为该 runtime 只暴露 `max_req_input_len=262143`。修正后的入口使用 `--context-length 262151`，采集两个 worker 的 `/server_info`，并要求测量前 `max_req_input_len>=262145`。正确的 context gate 仍不等于 runtime stability：clean session 在 256K/concurrency 2 上双节点失败，targeted fresh-service retry 又在 concurrency 16 上发生 node 1 failure，两次 incident 均明确披露。

- 当前脱敏证据：[`data/raw-logs/20260713-amd-tuned-moe-expanded-concurrency/`](data/raw-logs/20260713-amd-tuned-moe-expanded-concurrency/)
- 当前报告：[`reports/20260713-amd-tuned-moe-expanded-concurrency.md`](reports/20260713-amd-tuned-moe-expanded-concurrency.md)
- 历史撤回证据：[`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/)

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
| Docker 镜像 | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | AMD 0510 build, SHA `bb9d2e5ab1a6` |
| SGLang | AMD fork: [sammysun0711/sglang](https://github.com/sammysun0711/sglang) branch `mimo_aiter_attn`, commit `db840d935` | CK A8W8 blockwise GEMM bpreshuffle + AITER INT8 quick-reduce |
| ROCm | 7.2.0 | |
| aiter | [sammysun0711/aiter](https://github.com/sammysun0711/aiter) commit [`d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9) | MiMo 模型专用 fused-MoE tuning CSV；runtime-local 等价 commit `00e94abf1` |
| GEMM 路径 | **CK A8W8 blockwise bpreshuffle** | `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` |
| Mooncake | `0.3.7.post2` | PD 分离 KV cache 传输 |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm backend |

### 模型

| 属性 | 值 | 来源 |
|------|---|------|
| 模型 | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| 总参数 | 1.02 T | HF Model Card |
| 活跃参数 | 42 B / token | HF Model Card |
| Routed experts | 384，每 token 8 个活跃 | HF Model Card |
| Attention | 混合：10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3 层 multi-layer EAGLE | HF Model Card |
| 量化 | FP8 E4M3 | HF Model Card |
| Checkpoint 大小 | 963 GB (34 safetensors) | 实测 |

---

## 复现步骤

当前修正后的 launch、扩展并发、validation 和 parser bundle 位于 [`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/)。旧的 [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/) bundle 及其 raw logs 仅作为历史证据保留；当前 256K 复现不得继续使用其中的 262149 launch 设置。

### 前置条件

- 2× Azure `Standard_ND96isr_MI300X_v5` 节点（VMSS，相同 placement group 保证 IB）
- Docker 镜像：`rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510`（SHA: `bb9d2e5ab1a6`）
- 模型：[XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) 下载到 `/data/models/MiMo-V2.5-Pro`
- SGLang：`sammysun0711/sglang` 分支 `mimo_aiter_attn`，commit `db840d935`
- aiter：`sammysun0711/aiter`，commit `d725746a0f8c233d8e46e2771a7c8dbcd06e40d9`

### 容器运行时要求

| 要求 | 为什么重要 | 验证方式 |
|---|---|---|
| `--privileged`、`/dev/mem`、`CAP_SYS_ADMIN` | 让 Mooncake 能发现并使用 RDMA HCA 进行 KV-cache transfer | 容器内执行 `ls /dev/infiniband/uverbs0 && ls /dev/mem` |
| 不存在旧 `/sgl-workspace/aiter` | 避免 Python import 抢占 `/sgl-workspace/aiter_0625` | `test ! -d /sgl-workspace/aiter` |
| benchmark 显式指定 source tree | 避免 benchmark client namespace package 漂移 | `PYTHONPATH=/sgl-workspace/sglang_0625/python` |

### 执行步骤

```bash
# 1. 两个节点启动干净容器
CONTAINER=sglang
docker run -d --name $CONTAINER \
  --privileged \
  --ipc=host --network=host --shm-size=256g \
  --device=/dev/kfd --device=/dev/dri --device=/dev/mem \
  --group-add video \
  --cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined --security-opt label=disable \
  -v /data:/data rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 sleep infinity

# 1a. RDMA gate（两个节点，必须通过再继续）
docker exec $CONTAINER bash -c "ls /dev/infiniband/uverbs0 && ls /dev/mem && echo RDMA_DEVICE_OK"

# 2. 容器内 clone 源码（两个节点）
docker exec -it $CONTAINER bash
mkdir -p /sgl-workspace && cd /sgl-workspace
git clone https://github.com/sammysun0711/sglang.git sglang_0625
cd sglang_0625 && git checkout db840d935
cd /sgl-workspace
git clone https://github.com/sammysun0711/aiter.git aiter_0625
cd aiter_0625 && git checkout d725746a0f8c233d8e46e2771a7c8dbcd06e40d9

# 3. 安装（两个节点，--no-deps 保留 ROCm torch 栈）
cd /sgl-workspace/sglang_0625 && pip install -e "python[all_hip]" --no-deps
pip install flydsl==0.2.0 --no-deps
cd /sgl-workspace/aiter_0625 && pip install -e . --no-deps
pip install mooncake-transfer-engine==0.3.7.post2 --no-deps

# 3a. 只在 prefill/router 节点构建 sglang-kernel
cd /sgl-workspace/sglang_0625/sgl-kernel && python3 setup_rocm.py install

# 3b. 验证 import
export PYTHONPATH=/sgl-workspace/sglang_0625/python:${PYTHONPATH:-}
python3 -c "import torch, sglang, sgl_kernel, aiter; print('IMPORT_OK')"
test ! -d /sgl-workspace/aiter || { echo "ERROR: stale aiter shadows aiter_0625"; exit 1; }

# 4. 下载模型
huggingface-cli download XiaomiMiMo/MiMo-V2.5-Pro --local-dir /data/models/MiMo-V2.5-Pro

# 5. 把当前修正后的 bundle 复制进容器
# scripts/20260713-amd-tuned-moe-expanded-concurrency/ -> /data/mimo-tuned-expanded/

# 6. 查 IB IP
export PREFILL_IB_IP=<prefill 节点 IB IP>
export DECODE_IB_IP=<decode 节点 IB IP>

# 7. 清理旧进程（两个节点）
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|bench_serving' || true; pkill -f '[s]glang::router|sglang_router' || true"

# 8. 启动 server（每个在独立终端，前台常驻）
# 终端 A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded && bash launch_pd_prefill.sh"
# 终端 B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded && bash launch_pd_decode.sh"
# 终端 C — Node 1 (router, 等两个 server 打印 ready):
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_pd_router.sh"

# 9. health + smoke test
curl -fsS http://127.0.0.1:40000/health
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. 跑 benchmark
RUN_DIR=/data/mimo-tuned-expanded/run-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/decode $RUN_DIR/prefill; cd /data/mimo-tuned-expanded; LOG_DIR=$RUN_DIR/decode bash benchmark_decode.sh > $RUN_DIR/decode/full.out 2>&1; echo \$? > $RUN_DIR/decode/full.rc"
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded; LOG_DIR=$RUN_DIR/prefill bash benchmark_1p_prefill.sh > $RUN_DIR/prefill/full.out 2>&1; echo \$? > $RUN_DIR/prefill/full.rc"
```

### AMD DP=2/TP=8 双节点 Prefill 测试方法

修正后的 DP=2 复现使用相同 Docker image，并为 262,144-token request 设置 `--context-length 262151`。它通过 `/server_info` 验证两个 worker，并使用显式 round-robin routing。这个测试是 prefill-only server-mode benchmark，不包含 P→D KV-cache 传输。

```bash
cd /data/mimo-tuned-expanded
./launch_dp2_node0.sh       # node 0
./launch_dp2_node1.sh       # node 1
Node0_IP=<node0-ib-ip> Node1_IP=<node1-ib-ip> ./launch_dp2_router.sh
LOG_DIR=/data/mimo-tuned-expanded/rep-1/dp2 ./benchmark_dp2_prefill.sh
```

该 sweep 命令只是 client-only convenience。可接受的 DP=2 evidence 必须按 current bundle README 使用 `benchmark_dp2_point.sh` 逐点执行，并保存两个 worker 的 request delta。

### 归档证据

| 路径 | 内容 |
|------|------|
| [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/) | 历史证据：有效的 Decode 与 8K/64K Prefill，以及已撤回的 256K client summaries |
| [`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md) | Tuned fused-MoE 独立复测报告和 evidence map |
| [`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/) | 当前修正后的 launch、扩展并发、验证和 parser bundle |
| [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/) | 已被取代的历史 bundle；不能用于当前 256K 复现 |
| [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/) | CK A8W8 严格复现：benchmark 日志、环境门禁、脚本 SHA256 |
| [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md) | CK 严格复现结果摘要 |

---

## 已知问题

| 问题 | 状态 | 影响 |
|------|------|------|
| **Decode CUDA Graph** | ⚠️ 关键配置 | Decode server 禁止使用 `--disable-cuda-graph`，否则 TPOT 退化 5 倍。Prefill server 应禁用。 |
| **DP=2 256K request framing** | ✅ 已修正 | 使用 `--context-length 262151`；要求直接 worker `/server_info` 的 `max_req_input_len>=262145`、干净的 service logs 和双 worker distribution evidence。 |
| **Router health endpoint** | ✅ 已修正 | SGLang `/health` 会执行 synthetic generation，在长 Prefill 负载下可能失败。使用 bundle 中非生成型 `/server_info` endpoint 和 30 秒 timeout，并验证 worker/router logs。 |
| **Run-to-run variance** | ⚠️ 部分刻画 | 扩展矩阵每点运行一轮；Decode concurrency 16/32/64/128 另有第二次 fresh-service run。不声称 full-matrix standard deviation。 |

---

## 参考资料

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` 分支](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo 模型专用 fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*最后更新: 2026-07-13*
