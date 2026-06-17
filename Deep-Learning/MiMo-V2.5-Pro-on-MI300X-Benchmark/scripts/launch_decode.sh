#!/bin/bash
# launch_decode.sh — Decode server for PD-disaggregated MiMo-V2.5-Pro with MTP/EAGLE
#
# Run this on the DECODE node container.
# The PREFILL node should be started first (launch_prefill.sh).
#
# Author: Xinyu Wei (Microsoft AI GBB)

# ============== EDIT THESE ==============
MODEL_PATH="/data/models/MiMo-V2.5-Pro"
LOG_DIR="/data/pd_mtp"
# ========================================

# --- Environment Variables ---
export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export NCCL_DMABUF_ENABLE=0
export TORCH_NCCL_BLOCKING_WAIT=1
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_DISAGGREGATION_THREAD_POOL_SIZE=12
export SGLANG_DISAGGREGATION_BOOTSTRAP_TIMEOUT=5000
export SGLANG_DISAGGREGATION_WAITING_TIMEOUT=5000
export SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK=16384
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

mkdir -p "$LOG_DIR"

# --- IB devices: use ALL 8 CX7 400G NICs ---
IB_DEVICES="mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7"

echo "=== Launching DECODE server ==="
echo "IB devices: $IB_DEVICES"
echo "Model: $MODEL_PATH"

# Note: Decode server does NOT use --disable-cuda-graph (cuda graph ON for decode)
python3 -u -m sglang.launch_server \
  --model-path "$MODEL_PATH" \
  --tp-size 8 \
  --host 0.0.0.0 --port 30001 \
  --trust-remote-code \
  --disable-radix-cache \
  --cuda-graph-max-bs 32 \
  --mem-fraction-static 0.85 \
  --context-length 262144 \
  --max-running-requests 128 \
  --chunked-prefill-size 16384 \
  --attention-backend triton \
  --disaggregation-mode decode \
  --disaggregation-transfer-backend mooncake \
  --disaggregation-ib-device "$IB_DEVICES" \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --enable-draft-weights-cpu-backup \
  2>&1 | tee "$LOG_DIR/decode_server.log"
