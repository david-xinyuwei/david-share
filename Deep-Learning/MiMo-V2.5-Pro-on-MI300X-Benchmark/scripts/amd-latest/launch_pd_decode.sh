#!/bin/bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/onep/service}"
MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
SERVER_HOST="${SERVER_HOST:?Set SERVER_HOST to this node private or IB address}"

case "$SERVER_HOST" in
  0.0.0.0|::|\[::\])
    printf 'SERVER_HOST must be a concrete private or IB address, not %s\n' "$SERVER_HOST" >&2
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
#export NCCL_DMABUF_ENABLE=0
#export TORCH_NCCL_BLOCKING_WAIT=1
#export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_DISAGGREGATION_THREAD_POOL_SIZE=12
export SGLANG_DISAGGREGATION_BOOTSTRAP_TIMEOUT=5000
export SGLANG_DISAGGREGATION_WAITING_TIMEOUT=5000
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SPEC_NAN_DETECTION=1
export SGLANG_SPEC_OOB_DETECTION=1
#export SGLANG_AITER_UNIFIED_VERIFY=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected
#--skip-server-warmup
#--disable-overlap-schedule \
#--disable-radix-cache \
python3 -u -m sglang.launch_server \
  --model-path "$MODEL" \
  --tp-size 8 \
  --host "$SERVER_HOST" --port 30001 \
  --trust-remote-code \
  --mem-fraction-static 0.85 \
  --disable-radix-cache \
  --context-length 262151 \
  --max-running-requests 128 \
  --chunked-prefill-size 16384 \
  --attention-backend aiter \
  --kv-cache-dtype fp8_e4m3 \
  --page-size 32 \
  --disaggregation-mode decode \
  --disaggregation-transfer-backend mooncake \
  --disaggregation-ib-device mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7 \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --disable-overlap-schedule \
  2>&1 | tee "$LOG_DIR/decode_outer.log"
