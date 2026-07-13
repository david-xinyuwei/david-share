#!/bin/bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-/data/xisun/bench_tp8_dp2_noep}"
MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
mkdir -p "$LOG_DIR"

export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SPEC_NAN_DETECTION=1
export SGLANG_SPEC_OOB_DETECTION=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected
export SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1
python3 -u -m sglang.launch_server \
  --model-path "$MODEL" \
  --tp-size 8 \
  --host 0.0.0.0 --port 30001 \
  --trust-remote-code \
  --mem-fraction-static 0.85 \
  --disable-radix-cache \
  --context-length 262149 \
  --max-running-requests 128 \
  --chunked-prefill-size 32768 \
  --attention-backend aiter \
  --kv-cache-dtype fp8_e4m3 \
  --page-size 32 \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --disable-overlap-schedule \
  2>&1 | tee "$LOG_DIR/tp8_server_aiter_mtp_ck_gemm_preshuffle_chunk_32k_node1.log"
