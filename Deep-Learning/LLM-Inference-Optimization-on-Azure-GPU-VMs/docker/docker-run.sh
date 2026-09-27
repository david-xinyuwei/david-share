#!/usr/bin/env bash
# Start the serving container with the host access the AITER / Mooncake path needs.
# Without --privileged, /dev/mem and CAP_SYS_ADMIN, RDMA silently falls back to TCP
# and the measured 1P1D throughput is not reachable.
#
# SECURITY: --privileged, host network/IPC, /dev/mem, CAP_SYS_ADMIN and SYS_PTRACE give
# the container near-host access. Use it only on a dedicated GPU VM that runs nothing else.
set -euo pipefail

IMAGE="${IMAGE:-mimo-mi300x:public}"
NAME="${NAME:-sglang}"
DATA="${DATA:?Set DATA to the host directory that holds the model weights}"

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
