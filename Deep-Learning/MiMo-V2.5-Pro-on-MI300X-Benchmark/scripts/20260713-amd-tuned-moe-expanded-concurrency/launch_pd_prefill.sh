#!/bin/bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-/data/mimo-tuned-expanded/rep-1/onep/service}"
MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
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
#export SGLANG_USE_AITER_UNIFIED_ATTN=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected
export SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1
#--skip-server-warmup
#--disable-overlap-schedule \
#--disable-radix-cache \
#--chunked-prefill-size 16384 \
python3 -u -m sglang.launch_server \
  --model-path "$MODEL" \
  --tp-size 8 \
  --host 0.0.0.0 --port 30000 \
  --trust-remote-code \
  --disable-radix-cache \
  --disable-cuda-graph \
  --mem-fraction-static 0.85 \
  --context-length 262151 \
  --max-running-requests 128 \
  --chunked-prefill-size 32768 \
  --attention-backend aiter \
  --page-size 32 \
  --kv-cache-dtype fp8_e4m3 \
  --disaggregation-mode prefill \
  --disaggregation-transfer-backend mooncake \
  --disaggregation-ib-device mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7 \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --watchdog-time 1200 \
  --disable-overlap-schedule \
  2>&1 | tee "$LOG_DIR/prefill_outer.log"
