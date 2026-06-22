#!/bin/bash
# launch_tp16_dp2_node1.sh - Node 1 for MiMo-V2.5-Pro TP16/DP2 DP-attention topology probe.
# Run after or alongside node0 with the same DIST_INIT_ADDR.
#
# Author: Xinyu Wei (Microsoft AI GBB)
set -euo pipefail

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
export SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK="${SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK:-16384}"
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

MODEL_PATH="${MODEL_PATH:-/data/models/MiMo-V2.5-Pro}"
DIST_INIT_ADDR="${DIST_INIT_ADDR:?Set DIST_INIT_ADDR to node0_ib_ip:20000}"
LOG_DIR="${LOG_DIR:-/data/bench_tp16_dp2}"
IB_DEVICES="${IB_DEVICES:-mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7}"
CONTEXT_LENGTH="${CONTEXT_LENGTH:-786432}"
MAX_RUNNING_REQUESTS="${MAX_RUNNING_REQUESTS:-96}"
CHUNKED_PREFILL_SIZE="${CHUNKED_PREFILL_SIZE:-32768}"
PAGE_SIZE="${PAGE_SIZE:-64}"
EXTRA_SERVER_ARGS="${EXTRA_SERVER_ARGS:-}"

mkdir -p "$LOG_DIR"

echo "=== Launch MiMo-V2.5-Pro TP16 DP2 node1 ==="
echo "effective_attn_tp should be 16 / 2 = 8"
echo "dist-init: $DIST_INIT_ADDR"
echo "context=$CONTEXT_LENGTH max_running=$MAX_RUNNING_REQUESTS chunked_prefill=$CHUNKED_PREFILL_SIZE page_size=$PAGE_SIZE"
echo "extra args: ${EXTRA_SERVER_ARGS:-<none>}"

python3 -u -m sglang.launch_server \
  --model-path "$MODEL_PATH" \
  --tp-size 16 \
  --dp-size 2 \
  --enable-dp-attention \
  --enable-dp-lm-head \
  --moe-a2a-backend mori \
  --nnodes 2 \
  --node-rank 1 \
  --dist-init-addr "$DIST_INIT_ADDR" \
  --host 0.0.0.0 --port 30000 \
  --trust-remote-code \
  --disable-radix-cache \
  --disable-cuda-graph \
  --mem-fraction-static 0.75 \
  --context-length "$CONTEXT_LENGTH" \
  --max-running-requests "$MAX_RUNNING_REQUESTS" \
  --chunked-prefill-size "$CHUNKED_PREFILL_SIZE" \
  --page-size "$PAGE_SIZE" \
  --attention-backend triton \
  --disaggregation-ib-device "$IB_DEVICES" \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  $EXTRA_SERVER_ARGS \
  2>&1 | tee "$LOG_DIR/node1_server.log"