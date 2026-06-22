#!/bin/bash
# launch_decode_ep8_v2.sh — Decode server with AMD-standard PD infrastructure
# Changes from v1: AMD full-PD infrastructure (etcd/UCX/OpenMPI) plus stable page-size=1 default.
# page-size=64 and chunked-prefill-size=32768 triggered MORI/long-context instability in this workload.
# Run on DECODE node (VM10) container
#
# Author: Xinyu Wei (Microsoft AI GBB)

# AMD ROCm / aiter
export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export NCCL_DMABUF_ENABLE=0
export TORCH_NCCL_BLOCKING_WAIT=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Mooncake / PD disaggregation
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_DISAGGREGATION_THREAD_POOL_SIZE=12
export SGLANG_DISAGGREGATION_BOOTSTRAP_TIMEOUT=5000
export SGLANG_DISAGGREGATION_WAITING_TIMEOUT=5000

# MORI expert parallelism
export SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK=16384

# MTP/EAGLE layer=3 alignment
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

# UCX (if installed)
if [ -d /opt/ucx ]; then
  export PATH=/opt/ucx/bin:$PATH
  export LD_LIBRARY_PATH=/opt/ucx/lib:${LD_LIBRARY_PATH:-}
  echo "[INFO] UCX enabled: $(ucx_info -v 2>&1 | head -1)"
fi
if [ -d /opt/ompi ]; then
  export PATH=/opt/ompi/bin:$PATH
  export LD_LIBRARY_PATH=/opt/ompi/lib:${LD_LIBRARY_PATH:-}
  echo "[INFO] OpenMPI enabled: $(ompi_info --version 2>&1 | head -1)"
fi

mkdir -p /data/bench_ep8_v2

IB_DEVICES="mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7"

echo "=== Launching DECODE server v2 (AMD-standard PD config) ==="
echo "  page-size=1(default), chunked-prefill=16384, AMD full-PD infra"
echo "  TP=8, EP=8 MORI, MTP=3, context=262144"

python3 -u -m sglang.launch_server \
  --model-path /data/models/MiMo-V2.5-Pro \
  --tp-size 8 \
  --ep-size 8 \
  --moe-a2a-backend mori \
  --host 0.0.0.0 --port 30001 \
  --trust-remote-code \
  --disable-radix-cache \
  --mem-fraction-static 0.85 \
  --context-length 262144 \
  --max-running-requests 128 \
  --chunked-prefill-size 16384 \
  --attention-backend triton \
  --disaggregation-mode decode \
  --disaggregation-transfer-backend mooncake \
  --disaggregation-ib-device $IB_DEVICES \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  2>&1 | tee /data/bench_ep8_v2/decode_server.log
