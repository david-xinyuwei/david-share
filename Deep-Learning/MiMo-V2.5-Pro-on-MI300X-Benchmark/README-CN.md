# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE，与小米 H200 参考数据做 benchmark 对比。

本 repo 提供完整的复现脚本、启动命令、benchmark 结果和 server 日志。使用 2 台 Azure ND96isr_MI300X_v5 和指定 Docker 镜像，可以按下面步骤从 clean-room 容器重建 MI300X 环境，并运行 AMD benchmark 脚本。PD-separated decode 必须把 RDMA 设备暴露给容器（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`），否则 Mooncake 会 fallback 到 TCP，高并发吞吐结果无效。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

[English](README.md) | 中文

---

## 核心结论

**Prefill throughput（CK A8W8，output=1；越高越好）**

| Context | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|
| 8K | 16,716 | 31,950 | 52.3% |
| 64K | 17,254 | 27,400 | 63.0% |
| 256K | 37,493 | 17,400 | **215.5%** |

**Decode 8K/1K（CK A8W8，两边都 `SIMULATE_ACC_LEN=3`；TPOT 越低越好）**

| BS | MI300X Median TPOT | MI300X P99 | H200 TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10.83 ms | 11.57 ms | 11.59 ms | **0.93x** | 1,299 | 1,381 | 94.1% |
| 32 | 13.73 ms | 14.25 ms | 12.56 ms | 1.09x | 1,911 | 2,549 | 74.9% |
| 64 | 15.53 ms | 16.58 ms | 14.28 ms | 1.09x | 2,188 | 4,483 | 48.8% |
| 128 | 14.83 ms | 15.82 ms | 18.25 ms | **0.81x** | 2,209 | 7,013 | 31.5% |

### 关键发现

- **Decode TPOT 在 BS=16 和 BS=128 反超 H200。** BS=16 时单 token 延迟是 H200 的 0.93 倍；BS=128 时是 0.81 倍。BS=32/64 差距仅 9%。
- **Prefill 256K 长上下文：MI300X 是 H200 的 2.15 倍**吞吐。8K/64K 达到 H200 的 52–63%。
- **Output tok/s 差距比 TPOT 大**，因为 output tok/s 还包含 serving 拓扑和 scheduler 差异（单 TP=8 decode path vs H200 多 DP/EP）。TPOT 对比更能反映 kernel 级性能。
- **Decode throughput 在 concurrency 64 饱和**（~2,200 output tok/s），到 concurrency 256 保持平稳。

### 方法论说明

MI300X 和 H200 两边都使用 `SGLANG_SIMULATE_ACC_LEN=3`（固定 MTP accept_length = 3.0）。MI300X 使用**真实 expert routing**（不用 `fake_topk_ids`），比 H200 理想路由基线多 5–15% overhead。H200 的 output tok/s 列取自小米参考表，等于 `BS × 1000 / TPOT`。

---

## Decode — 详细结果

### Decode 8K/1K — AMD CK 参考对齐（低并发）

本章节使用 AMD 2026-07-07 CK A8W8 原始脚本严格复现。"AMD CK"列是 AMD 自己发布的数字；我们的复现结果在 ~1.2% 以内。

N = 256 requests/BS 点；target concurrency = 16/32/64/128；`decode_full.rc=0`；无 benchmark 错误标记。

| BS | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | AMD CK mean TPOT ms | 相对 AMD CK |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,299.18 | 10.64 | 10.83 | 11.57 | 10.59 | +0.5% |
| 32 | 256 | 1,910.75 | 13.50 | 13.73 | 14.25 | 13.43 | +0.5% |
| 64 | 256 | 2,188.05 | 15.10 | 15.53 | 16.58 | 14.92 | +1.2% |
| 128 | 256 | 2,209.43 | 14.52 | 14.83 | 15.82 | 14.55 | -0.2% |

- 原始证据：[`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/)
- 结果摘要：[`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md)
- 脚本快照：[`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/)

### Decode 8K/1K — 高并发扩展（超出 AMD 测试范围）

AMD 的 benchmark 覆盖到 concurrency 128。我们把 sweep 扩展到 concurrency 256，确定饱和点。

N = 256 requests/并发点；output length = 1024；warmup = 32；`decode_full.rc=0`。

| Concurrency | Output tok/s | Mean TPOT ms | P99 TPOT ms | Mean TTFT ms |
|---:|---:|---:|---:|---:|
| 16 | 1,321.50 | 10.79 | 11.65 | 1,191 |
| 32 | 1,914.27 | 13.37 | 14.26 | 2,847 |
| 64 | 2,198.77 | 15.49 | 17.08 | 11,853 |
| 96 | 2,200.63 | 15.06 | 16.31 | 23,667 |
| 128 | 2,203.65 | 14.83 | 16.22 | 33,430 |
| 192 | 2,202.57 | 14.72 | 16.28 | 47,911 |
| 256 | 2,207.97 | 14.60 | 16.36 | 55,467 |

**解读**：throughput 在 concurrency 64 左右饱和（~2,200 output tok/s），到 concurrency 256 保持平稳。更高并发主要增加排队/TTFT，不再提升 output throughput。

- 原始证据：[`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/)
- 结果摘要：[`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md)
- 脚本快照：[`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/)

---

## Prefill — 详细结果

### Prefill — AMD CK 参考对齐

N = 16 requests/input length；target concurrency = 4；`prefill_full.rc=0`；无错误标记。

| ISL/OSL | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms | AMD CK 32K input tok/s | 相对 AMD CK |
|---:|---:|---:|---:|---:|---:|---:|
| 8K/1 | 16 | 16,715.80 | 1,849.62 | 2,709.97 | 16,924.08 | -1.2% |
| 64K/1 | 16 | 17,254.14 | 14,107.62 | 16,674.08 | 17,223.51 | +0.2% |
| 256K/1 | 16 | 37,492.80 | 19,278.17 | 86,264.51 | 37,241.84 | +0.7% |

### Prefill — 多并发扩展（超出 AMD 测试范围）

AMD 的 prefill benchmark 使用 concurrency 4。我们扩展到 concurrency 1/2/4/8，覆盖 8K/64K/256K，验证并发 scaling 行为。

N = 16 requests/点；output = 1；warmup = 1。

| Input tokens | Concurrency | Input tok/s | Mean TTFT ms | P99 TTFT ms |
|---:|---:|---:|---:|---:|
| 8192 | 1 | 14,811.18 | 552 | 589 |
| 8192 | 2 | 16,982.94 | 958 | 1,369 |
| 8192 | 4 | 16,783.88 | 1,841 | 2,680 |
| 8192 | 8 | 18,617.41 | 3,211 | 4,691 |
| 65536 | 1 | 16,602.69 | 3,946 | 4,870 |
| 65536 | 2 | 18,077.28 | 7,123 | 9,004 |
| 65536 | 4 | 16,904.74 | 14,232 | 16,774 |
| 65536 | 8 | 17,252.39 | 24,482 | 31,727 |
| 262144 | 1 | 35,452.56 | 6,995 | 22,648 |
| 262144 | 2 | 37,429.63 | 12,417 | 47,335 |
| 262144 | 4 | — (warmup 失败) | — | — |
| 262144 | 8 | — (warmup 失败) | — | — |

256K/con4 和 256K/con8 在 warmup 阶段失败：`No available prefill workers (all circuits open or unhealthy)`。这是长上下文高并发下的 worker 可用性边界，不是已测得的吞吐退化。

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
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` | [ROCm/aiter](https://github.com/ROCm/aiter)，MoE/GEMM/FP8/LayerNorm/Attention 全部启用 |
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

所有脚本和原始日志归档在 [`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/) 和 [`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/) 下。

### 前置条件

- 2× Azure `Standard_ND96isr_MI300X_v5` 节点（VMSS，相同 placement group 保证 IB）
- Docker 镜像：`rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510`（SHA: `bb9d2e5ab1a6`）
- 模型：[XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) 下载到 `/data/models/MiMo-V2.5-Pro`
- SGLang：`sammysun0711/sglang` 分支 `mimo_aiter_attn`，commit `db840d935`
- aiter：`ROCm/aiter`，commit `7a8ff7dd4`

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
git clone https://github.com/ROCm/aiter.git aiter_0625
cd aiter_0625 && git checkout 7a8ff7dd4

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

# 5. 部署 benchmark 脚本（从 scripts/20260707-amd-ck-a8w8/ 复制到 /data/xisun/）

# 6. 查 IB IP
export PREFILL_IB_IP=<prefill 节点 IB IP>
export DECODE_IB_IP=<decode 节点 IB IP>

# 7. 清理旧进程（两个节点）
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|sglang_router|bench_serving' || true"

# 8. 启动 server（每个在独立终端，前台常驻）
# 终端 A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/xisun && bash launch_tp8_noep_prefill_aiter_mtp.sh"
# 终端 B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/xisun && bash launch_tp8_noep_decode_aiter_mtp.sh"
# 终端 C — Node 1 (router, 等两个 server 打印 ready):
docker exec $CONTAINER bash -c "cd /data/xisun && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_router.sh"

# 9. health + smoke test
curl -fsS http://127.0.0.1:40000/health
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. 跑 benchmark
RUN_DIR=/data/xisun/benchmark-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR && cd /data/xisun && bash run_benchmark_mimo_pro_decode.sh > $RUN_DIR/decode_full.out 2>&1; echo \$? > $RUN_DIR/decode_full.rc"
docker exec $CONTAINER bash -c "cd /data/xisun && bash run_benchmark_mimo_pro_prefill.sh > $RUN_DIR/prefill_full.out 2>&1; echo \$? > $RUN_DIR/prefill_full.rc"
```

### 归档证据

| 路径 | 内容 |
|------|------|
| [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/) | CK A8W8 严格复现：benchmark 日志、环境门禁、脚本 SHA256 |
| [`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/) | 高并发扩展：decode + prefill sweep 日志 |
| [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md) | CK 严格复现结果摘要 |
| [`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md) | 并发扩展结果摘要 |
| [`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/) | CK launch + benchmark 脚本 |
| [`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/) | 并发 sweep 脚本 |

---

## 已知问题

| 问题 | 状态 | 影响 |
|------|------|------|
| **Decode CUDA Graph** | ⚠️ 关键配置 | Decode server 禁止使用 `--disable-cuda-graph`，否则 TPOT 退化 5 倍。Prefill server 应禁用。 |
| **256K 高并发 prefill** | ⚠️ 边界 | 256K prefill concurrency ≥4 warmup 失败，无健康 prefill worker。Concurrency 1–2 正常。 |

---

## 参考资料

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` 分支](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*最后更新: 2026-07-08*
