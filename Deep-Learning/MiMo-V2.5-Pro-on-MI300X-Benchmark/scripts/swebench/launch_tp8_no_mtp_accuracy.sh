#!/usr/bin/env bash
# MiMo-V2.5-Pro single-node TP8 accuracy server with speculative decoding disabled.
#
# Sanitized copy of the launcher that served the "MTP off" SWE-bench run recorded in
# data/swebench/summary.json (run xiaomi-nomtp-full499-20260808T152848Z): same AITER +
# FP8 KV + FlyDSL Paged Attention stack as launch_tp8_noep_aiter_mtp_accuracy.sh,
# with every --speculative-* flag removed. Only the node-name check and the fixed log
# path of the original were replaced by environment variables; no flag was changed.
#
# Run inside the serving container (see runtime-recipe/). The recorded run started it
# with `docker exec <container> /bin/bash launch_tp8_no_mtp_accuracy.sh`.
set -euo pipefail

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-30001}"
SGLANG_ROOT="${SGLANG_ROOT:-/sgl-workspace/sglang_0625}"
MODEL_LOG="${MODEL_LOG:-./logs/no_mtp_accuracy_$(date -u +%Y%m%dT%H%M%SZ)/server.log}"

mkdir -p "$(dirname "$MODEL_LOG")"
: > "$MODEL_LOG"
exec >> "$MODEL_LOG" 2>&1

export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_SET_CPU_AFFINITY=1
export HSA_NO_SCRATCH_RECLAIM=1
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_SPEC_NAN_DETECTION=1
export SGLANG_SPEC_OOB_DETECTION=1
export SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1
export TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=1
export SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d
export SGLANG_AITER_PA_DECODE_IMPL=flydsl
export SGLANG_FLYDSL_PA_NUM_PARTITIONS=16
# Never simulate acceptance in an accuracy run.
unset SGLANG_SIMULATE_ACC_LEN SGLANG_SIMULATE_ACC_METHOD

echo "mode=no-mtp started_at=$(date -u +%FT%TZ) sglang_root=$SGLANG_ROOT"

cd "$SGLANG_ROOT"
exec python3 -u -m sglang.launch_server \
  --model-path "$MODEL" \
  --tp-size 8 \
  --max-running-requests 96 \
  --host "$HOST" \
  --port "$PORT" \
  --trust-remote-code \
  --reasoning-parser mimo \
  --tool-call-parser mimo \
  --mem-fraction-static 0.95 \
  --swa-full-tokens-ratio 0.01 \
  --context-length 1048576 \
  --chunked-prefill-size 65536 \
  --max-prefill-tokens 1048576 \
  --attention-backend aiter \
  --kv-cache-dtype fp8_e4m3 \
  --page-size 64
