#!/bin/bash
# Single-node Decode server for the exact 64K/1K fixed-batch point.
# Identical runtime flags to launch_pd_decode.sh except: no PD disaggregation
# (one node performs Prefill and Decode) and mem-fraction-static raised to 0.95
# (effective 0.8075 after the automatic EAGLE factor), which expands the
# full-attention KV pool from 554,880 to 1,442,464 tokens so that sixteen
# 64K-context requests decode concurrently. The optimized AITER CK A8W8
# bpreshuffle path is enabled explicitly and must be verified in the log.
set -euo pipefail

LOG_DIR="${LOG_DIR:-/data/mimo-fixedbatch/service}"
MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"

case "$SERVER_HOST" in
  0.0.0.0|::|\[::\])
    printf 'SERVER_HOST must be a concrete local or private address, not %s\n' "$SERVER_HOST" >&2
    exit 2
    ;;
esac

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
export SGLANG_AITER_UNIFIED_VERIFY=1
export SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

python3 -u -m sglang.launch_server \
  --model-path "$MODEL" \
  --tp-size 8 \
  --host "$SERVER_HOST" --port 30001 \
  --trust-remote-code \
  --mem-fraction-static 0.95 \
  --disable-radix-cache \
  --context-length 262151 \
  --max-running-requests 128 \
  --chunked-prefill-size 16384 \
  --attention-backend aiter \
  --kv-cache-dtype fp8_e4m3 \
  --page-size 32 \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --disable-overlap-schedule \
  2>&1 | tee "$LOG_DIR/decode_outer.log"
