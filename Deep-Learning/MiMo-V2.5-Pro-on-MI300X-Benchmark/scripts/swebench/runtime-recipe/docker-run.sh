#!/usr/bin/env bash
# Start the serving container with the exact host configuration used for the
# 499-instance SWE-bench run. /dev/mem plus CAP_SYS_ADMIN are required by the
# AITER path; without them throughput drops to roughly one third.
set -euo pipefail

IMAGE="${IMAGE:-mimo-mi300x:20260810}"
NAME="${NAME:-sglang}"
DATA="${DATA:-/data}"

exec docker run -d --name "$NAME" \
  --privileged \
  --network host \
  --ipc host \
  --shm-size 32g \
  --cap-add CAP_SYS_ADMIN --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined --security-opt label=disable \
  --device /dev/kfd --device /dev/dri --device /dev/mem \
  --group-add video \
  -v "$DATA":/data \
  "$IMAGE" sleep infinity
