#!/bin/bash
# launch_prefill_ep8.sh — Prefill server with EP=8 MORI + MTP
# Run on PREFILL node (VM8) container
#
# Author: Xinyu Wei (Microsoft AI GBB)

export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export NCCL_DMABUF_ENABLE=0
export TORCH_NCCL_BLOCKING_WAIT=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_DISAGGREGATION_THREAD_POOL_SIZE=12
export SGLANG_DISAGGREGATION_BOOTSTRAP_TIMEOUT=5000
export SGLANG_DISAGGREGATION_WAITING_TIMEOUT=5000
export SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK=16384
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

mkdir -p /data/bench_ep8_full

IB_DEVICES="mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7"

echo "=== Launching PREFILL server (TP=8, EP=8, MORI, MTP layer=3) ==="

python3 -u -m sglang.launch_server \
  --model-path /data/models/MiMo-V2.5-Pro \
  --tp-size 8 \
  --ep-size 8 \
  --moe-a2a-backend mori \
  --host 0.0.0.0 --port 30000 \
  --trust-remote-code \
  --disable-radix-cache \
  --disable-cuda-graph \
  --mem-fraction-static 0.75 \
  --context-length 786432 \
  --max-running-requests 128 \
  --chunked-prefill-size 16384 \
  --attention-backend triton \
  --disaggregation-mode prefill \
  --disaggregation-transfer-backend mooncake \
  --disaggregation-ib-device $IB_DEVICES \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  2>&1 | tee /data/bench_ep8_full/prefill_server.log
