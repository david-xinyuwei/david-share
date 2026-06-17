#!/bin/bash
# launch_single_node_mtp.sh — Single-node MiMo-V2.5-Pro with MTP/EAGLE on MI300X
#
# Run inside the container on a single ND96isr_MI300X_v5 VM.
#
# Author: Xinyu Wei (Microsoft AI GBB)

# ============== EDIT THESE ==============
MODEL_PATH="/data/models/MiMo-V2.5-Pro"
LOG_DIR="/data/single_node_mtp"
# ========================================

export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export NCCL_DMABUF_ENABLE=0
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

mkdir -p "$LOG_DIR"

echo "=== Launching Single-Node MTP Server ==="

python3 -u -m sglang.launch_server \
  --model-path "$MODEL_PATH" \
  --tp-size 8 \
  --host 0.0.0.0 --port 30000 \
  --trust-remote-code \
  --disable-radix-cache \
  --cuda-graph-max-bs 32 \
  --mem-fraction-static 0.80 \
  --context-length 32768 \
  --max-total-tokens 65536 \
  --max-running-requests 64 \
  --chunked-prefill-size 32768 \
  --attention-backend triton \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --enable-draft-weights-cpu-backup \
  2>&1 | tee "$LOG_DIR/server.log"
