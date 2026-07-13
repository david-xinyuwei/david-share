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

**Prefill throughput（2026-07-13 tuned fused-MoE 复测，1P1D prefill 阶段，output=1；越高越好）**

| Context | Concurrency | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 8K | 4 | 20,780.79 | 31,950 | 65.0% |
| 64K | 4 | 19,022.57 | 27,400 | 69.4% |
| 256K | 4 | 39,905.41 | 17,400 | **229.3%** |

三个点均完成 16/16 requests，client error marker 为 0。独立复测的 DP=2 结果见 [Prefill Scaling — AMD 2-Node DP=2/TP=8](#prefill-scaling--amd-2-node-dp2tp8)。

**Decode 8K/1K（2026-07-13 tuned fused-MoE 复测，`SIMULATE_ACC_LEN=3`；TPOT 越低越好）**

| BS | Concurrency | MI300X Median TPOT | H200 Median TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 16 | 10.97 ms | 11.59 ms | **0.95x** | 1,331.98 | 1,381 | 96.5% |
| 32 | 32 | 13.93 ms | 12.56 ms | 1.11x | 1,936.24 | 2,549 | 76.0% |
| 64 | 64 | 17.60 ms | 14.28 ms | 1.23x | 2,457.73 | 4,483 | 54.8% |
| 128 | 128 | 17.30 ms | 18.25 ms | **0.95x** | 2,486.89 | 7,013 | 35.5% |

Decode 表里 `BS` 等于 target concurrency，和 H200 reference 的 load shape 对齐。

### 关键发现

- **1P1D prefill 在三个长度均提升：**相对 2026-07-07 独立 strict CK baseline，8K +24.32%、64K +10.25%、256K +6.43%。
- **高并发 decode 是 throughput/latency trade-off：** BS=64/128 的 output throughput 分别提升 +12.33%/+12.56%，mean TPOT 同时增加 +12.58%/+14.05%。
- **Decode median TPOT 在 BS=16 和 BS=128 仍低于 H200 reference**（均为 0.95x）。Output throughput 因 serving topology 未归一化而单独呈现。
- **DP=2 prefill 六个点均完成独立复测：**8K aggregate throughput 最高 45,992.94 tok/s，256K 达到 78,613.96 tok/s。与 H200 对比时使用 MI300X per-node throughput，不使用 2-node aggregate。
- **所有验收矩阵均通过：**4 个 decode 点各 256/256、3 个 1P1D prefill 点各 16/16、6 个 DP=2 点各 32/32，client error marker 为 0。

### 方法论说明

公开 aiter commit 增加的是模型专用 fused-MoE tuning CSV，不是 kernel 源码改动。`--speculative-num-draft-tokens=4` 表示 3 个 proposed draft tokens 加 1 个 bonus target token。`accept length=3` 包含该 bonus token，因此实际接受 2 个 draft tokens，reported draft accept rate 为 `2/3=0.67`。MI300X 使用真实 expert routing，H200 reference 使用理想均衡路由。AMD 报告的单-kernel latency 降低 37.6% 没有独立 microbenchmark log，因此不纳入我们的实测结论。

---

## Decode — 详细结果

### Decode 8K/1K — Tuned Fused-MoE 独立复测

N = 256 requests/点；input length = 8,192；output length = 1,024；warmup = 32；target concurrency = 16/32/64/128；`full.rc=0`。

| Concurrency | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | Output vs strict baseline | Mean TPOT vs strict baseline |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,331.98 | 10.83 | 10.97 | 11.35 | +2.52% | +1.79% |
| 32 | 256 | 1,936.24 | 13.65 | 13.93 | 14.35 | +1.33% | +1.11% |
| 64 | 256 | 2,457.73 | 17.00 | 17.60 | 18.44 | +12.33% | +12.58% |
| 128 | 256 | 2,486.89 | 16.56 | 17.30 | 17.92 | +12.56% | +14.05% |

**解读**：BS=64/128 出现明显 throughput 增益，但 TPOT 同时增加。决策时必须分开看 throughput 和单 token latency。

- 原始证据：[`data/raw-logs/20260713-amd-tuned-moe-retest/decode/`](data/raw-logs/20260713-amd-tuned-moe-retest/decode/)
- 详细报告：[`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md)
- 复现 bundle：[`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/)

---

## Prefill — 详细结果

### Prefill — Tuned Fused-MoE 独立复测

N = 16 requests/input length；output length = 1；target concurrency = 4；`full.rc=0`。

| ISL/OSL | Concurrency | Successful requests | Input tok/s | vs strict baseline | MI300X / H200 |
|---:|---:|---:|---:|---:|---:|
| 8K/1 | 4 | 16 | 20,780.79 | +24.32% | 65.0% |
| 64K/1 | 4 | 16 | 19,022.57 | +10.25% | 69.4% |
| 256K/1 | 4 | 16 | 39,905.41 | +6.43% | 229.3% |

**解读**：tuned fused-MoE configuration 在三个请求长度都提升 1P1D prefill throughput，其中 8K 相对增益最大。

- 原始证据：[`data/raw-logs/20260713-amd-tuned-moe-retest/prefill/`](data/raw-logs/20260713-amd-tuned-moe-retest/prefill/)

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

| ISL/OSL | Concurrency | Aggregate input tok/s | Per-node input tok/s | Per-node / H200 |
|---:|---:|---:|---:|---:|
| 8K/1 | 4 | 43,221.12 | 21,610.56 | 67.6% |
| 8K/1 | 8 | 45,992.94 | 22,996.47 | 72.0% |
| 64K/1 | 4 | 38,374.65 | 19,187.33 | 70.0% |
| 64K/1 | 8 | 38,255.28 | 19,127.64 | 69.8% |
| 256K/1 | 4 | 74,611.25 | 37,305.62 | 214.4% |
| 256K/1 | 8 | 78,613.96 | 39,306.98 | 225.9% |

六个点均完成 32/32 requests。与 H200 对比时使用 per-node throughput；不能把 MI300X 2-node aggregate 直接和单节点 H200 对比。

### 256K Correctness Guard

当 `random_input_len=262144` 时，standard DP=2 server 路径在请求构造后实际看到 262,148 tokens。Server allowance 设为 262,144 会返回 HTTP 200 error payload，client-only success counter 可能误判。该无效 attempt 已排除。有效复测只把 server allowance 改为 `--context-length 262149`，两个 node log 的 context-overflow 计数均为 0。

- 原始证据：[`data/raw-logs/20260713-amd-tuned-moe-retest/dp2/`](data/raw-logs/20260713-amd-tuned-moe-retest/dp2/)
- 验收记录：[`data/raw-logs/20260713-amd-tuned-moe-retest/checks/validation.txt`](data/raw-logs/20260713-amd-tuned-moe-retest/checks/validation.txt)

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

验收通过的 launch、benchmark、configuration 和 parser bundle 归档在 [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/)。Client logs 和 deterministic summary 位于 [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/)。

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

# 5. 把 scripts/20260713-amd-tuned-moe-retest/ 复制到 /data/xisun/20260713-amd-tuned-moe-retest/

# 6. 查 IB IP
export PREFILL_IB_IP=<prefill 节点 IB IP>
export DECODE_IB_IP=<decode 节点 IB IP>

# 7. 清理旧进程（两个节点）
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|bench_serving' || true; pkill -f '[s]glang::router|sglang_router' || true"

# 8. 启动 server（每个在独立终端，前台常驻）
# 终端 A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest && bash launch_pd_prefill.sh"
# 终端 B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest && bash launch_pd_decode.sh"
# 终端 C — Node 1 (router, 等两个 server 打印 ready):
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_pd_router.sh"

# 9. health + smoke test
curl -fsS http://127.0.0.1:40000/health
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. 跑 benchmark
RUN_DIR=/data/xisun/benchmark-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/decode $RUN_DIR/prefill; cd /data/xisun/20260713-amd-tuned-moe-retest; LOG_DIR=$RUN_DIR/decode bash benchmark_decode.sh > $RUN_DIR/decode/full.out 2>&1; echo \$? > $RUN_DIR/decode/full.rc"
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest; LOG_DIR=$RUN_DIR/prefill bash benchmark_1p_prefill.sh > $RUN_DIR/prefill/full.out 2>&1; echo \$? > $RUN_DIR/prefill/full.rc"
```

### AMD DP=2/TP=8 双节点 Prefill 测试方法

验收通过的 DP=2 复现使用相同 Docker image，并为 262,144-token request 设置 262,149-token server allowance。这个测试是 prefill-only server-mode benchmark，不包含 P→D KV-cache 传输。

```bash
./launch_dp2_node0.sh       # node 0
./launch_dp2_node1.sh       # node 1
Node0_IP=<node0-ib-ip> Node1_IP=<node1-ib-ip> ./launch_dp2_router.sh
LOG_DIR=/data/xisun/dp2 ./benchmark_dp2_prefill.sh
```

### 归档证据

| 路径 | 内容 |
|------|------|
| [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/) | 验收通过的 4/3/6 矩阵：client logs、exit code、summary、JSON、SHA-256 manifest、context guard |
| [`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md) | Tuned fused-MoE 独立复测报告和 evidence map |
| [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/) | 验收通过的 launch、benchmark、tuning CSV 和 deterministic parser bundle |
| [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/) | CK A8W8 严格复现：benchmark 日志、环境门禁、脚本 SHA256 |
| [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md) | CK 严格复现结果摘要 |

---

## 已知问题

| 问题 | 状态 | 影响 |
|------|------|------|
| **Decode CUDA Graph** | ⚠️ 关键配置 | Decode server 禁止使用 `--disable-cuda-graph`，否则 TPOT 退化 5 倍。Prefill server 应禁用。 |
| **DP=2 256K request framing** | ✅ 已加 guard | `random_input_len=262144` 在 server 侧变成 262,148 tokens。必须使用 `--context-length 262149`，并检查 service-log overflow count，不能只看 client success。 |
| **Run-to-run variance** | ⚠️ 未刻画 | 每个公开 matrix point 只运行一轮。已报告 request count，但不声称 multi-run standard deviation。 |

---

## 参考资料

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` 分支](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo 模型专用 fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*最后更新: 2026-07-13*
