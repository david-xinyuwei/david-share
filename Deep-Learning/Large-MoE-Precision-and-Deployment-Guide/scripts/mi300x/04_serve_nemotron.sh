#!/bin/bash
# 04_serve_nemotron.sh — Nemotron 3 Ultra BF16 on one node (8x MI300X), vLLM ROCm, TP8 + expert parallel.
#   sudo -E bash scripts/mi300x/04_serve_nemotron.sh
# Follow with:  tail -f $MOE_ROOT/logs/05_serve_nemotron.log ; ready when `curl -s localhost:8000/health` returns 200
# (observed 2026-11-02: weights 136.51 GiB/GPU, first load 443 s from cold page cache, 112 s warm; init engine 120 s).
#
# Mirrors the publisher's vLLM example (model card N1) minus CUDA-only flags. Two flags differ from that example
# because of what the ROCm image actually does (see VALIDATION.md, "Nemotron 3 Ultra BF16, one node, 8 GPUs"):
#   VLLM_ROCM_USE_AITER_MOE=0   attempt 1 failed: "Unquantized MoE backend ROCm AITER does not support ... no act_and_mul
#                               MLP layer" — Nemotron's LatentMoE experts are non-gated relu2, the AITER fused MoE kernel
#                               requires gated (SwiGLU-style) experts. Triton MoE is used instead. AITER stays on elsewhere.
#   no --enable-mamba-cache-stochastic-rounding
#                               attempt 2 failed in Mamba2 kernel warm-up: Triton selective_state_update with PHILOX
#                               rounding -> "LLD failed to link hsaco ... target emulation unknown" on this Triton 3.8 /
#                               ROCm 10.1 image. Set STOCH_ROUND=1 to re-test it on a newer image.
set -u
. "$(dirname "$0")/00_env.sh"
MAXLEN="${MAXLEN:-65536}"
SR_FLAG=""; [ "${STOCH_ROUND:-0}" = "1" ] && SR_FLAG="--enable-mamba-cache-stochastic-rounding"
LOG="$MOE_ROOT/logs/05_serve_nemotron.log"
docker rm -f vllm_nemotron >/dev/null 2>&1
echo "SERVE_START=$(date -u +%FT%TZ) IMG=$VLLM_IMAGE MID=$NEMOTRON_ID REV=$NEMOTRON_REV MAXLEN=$MAXLEN AITER_MOE=${AITER_MOE:-0} STOCH_ROUND=${STOCH_ROUND:-0}" | tee "$LOG"
docker run -d --name vllm_nemotron $DOCKER_COMMON \
  -e VLLM_ROCM_USE_AITER="${AITER:-1}" -e VLLM_ROCM_USE_AITER_MOE="${AITER_MOE:-0}" \
  "$VLLM_IMAGE" vllm serve "$NEMOTRON_ID" --revision "$NEMOTRON_REV" \
    --host 0.0.0.0 --port 8000 --served-model-name nemotron-3-ultra-bf16 \
    --trust-remote-code --dtype bfloat16 \
    --tensor-parallel-size 8 --enable-expert-parallel \
    --max-model-len "$MAXLEN" --gpu-memory-utilization 0.90 \
    --max-num-seqs 16 --max-num-batched-tokens 16384 \
    --enable-chunked-prefill --enable-prefix-caching \
    --mamba-ssm-cache-dtype float16 $SR_FLAG \
    --reasoning-parser nemotron_v3 >> "$LOG" 2>&1
echo "CONTAINER=$(docker ps -q -f name=vllm_nemotron)" | tee -a "$LOG"
nohup docker logs -f vllm_nemotron >> "$LOG" 2>&1 &
echo "FOLLOW_PID=$!" | tee -a "$LOG"
