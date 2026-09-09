#!/usr/bin/env bash
set -euo pipefail

export MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-30001}"
export MAX_RUNNING_REQUESTS="${MAX_RUNNING_REQUESTS:-96}"
export PAGE_SIZE="${PAGE_SIZE:-64}"
export MEM_FRACTION_STATIC="${MEM_FRACTION_STATIC:-1.0}"
export SWA_FULL_TOKENS_RATIO="${SWA_FULL_TOKENS_RATIO:-0.01}"
export FLYDSL_PA_NUM_PARTITIONS="${FLYDSL_PA_NUM_PARTITIONS:-16}"

export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
#export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
#export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_SPEC_NAN_DETECTION=1
export SGLANG_SPEC_OOB_DETECTION=1
export SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1

export TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=1
export SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d
export SGLANG_AITER_PA_DECODE_IMPL=flydsl
export SGLANG_FLYDSL_PA_NUM_PARTITIONS="${FLYDSL_PA_NUM_PARTITIONS}"

# Real MTP acceptance for accuracy validation.
unset SGLANG_SIMULATE_ACC_LEN SGLANG_SIMULATE_ACC_METHOD

export RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export LOG_DIR="${LOG_DIR:-./logs/accuracy_${RUN_ID}}"
export LOG_FILE="${LOG_FILE:-server_tp8_flydsl_accuracy.log}"
mkdir -p "${LOG_DIR}"

echo "FlyDSL hybrid: full target-verify=FlyDSL, SWA/sink and decode=AITER"
echo "Configuration: max-running=${MAX_RUNNING_REQUESTS}, page=${PAGE_SIZE}, partitions=${FLYDSL_PA_NUM_PARTITIONS}, mem=${MEM_FRACTION_STATIC}, swa=${SWA_FULL_TOKENS_RATIO}, overlap=enabled"
echo "MTP acceptance: real"
echo "Server log: ${LOG_DIR}/${LOG_FILE}"

cd "${SGLANG_ROOT}"
python3 -u -m sglang.launch_server \
  --model-path "${MODEL}" \
  --tp-size 8 \
  --max-running-requests "${MAX_RUNNING_REQUESTS}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --trust-remote-code \
  --reasoning-parser mimo \
  --tool-call-parser mimo \
  --mem-fraction-static "${MEM_FRACTION_STATIC}" \
  --swa-full-tokens-ratio "${SWA_FULL_TOKENS_RATIO}" \
  --context-length 1048576 \
  --chunked-prefill-size 65536 \
  --max-prefill-tokens 1048576 \
  --attention-backend aiter \
  --kv-cache-dtype fp8_e4m3 \
  --page-size "${PAGE_SIZE}" \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  2>&1 | tee "${LOG_DIR}/${LOG_FILE}"
