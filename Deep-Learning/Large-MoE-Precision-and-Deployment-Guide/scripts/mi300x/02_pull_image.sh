#!/bin/bash
# 02_pull_image.sh — pull the ROCm vLLM image and record its digest. Run with sudo (Docker).
#   sudo -E bash scripts/mi300x/02_pull_image.sh
# The pull is ~30 GB and runs in the background; follow it with:  tail -f $MOE_ROOT/logs/02_pull.log
# Expected final lines: PULL_EXIT=0, DIGEST=rocm/vllm@sha256:..., PULL_DONE=<time>.
set -u
. "$(dirname "$0")/00_env.sh"
LOG="$MOE_ROOT/logs/02_pull.log"
echo "PULL_START=$(date -u +%FT%TZ) IMG=$VLLM_IMAGE" | tee -a "$LOG"
nohup bash -c "docker pull '$VLLM_IMAGE' >> '$LOG' 2>&1; echo PULL_EXIT=\$? >> '$LOG'; \
  docker image inspect '$VLLM_IMAGE' --format 'DIGEST={{index .RepoDigests 0}} IMAGEID={{.Id}} SIZE={{.Size}}' >> '$LOG' 2>&1; \
  echo PULL_DONE=\$(date -u +%FT%TZ) >> '$LOG'" >/dev/null 2>&1 &
echo "PULL_PID=$!" | tee -a "$LOG"
