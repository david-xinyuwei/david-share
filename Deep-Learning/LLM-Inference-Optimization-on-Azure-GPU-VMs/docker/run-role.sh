#!/usr/bin/env bash
# Start one serving role as its own container. The rendered launch script is the
# container's main process, so `docker logs`, the restart policy and the exit code
# belong to the server itself; nothing is started by hand inside the container.
#
#   bash docker/run-role.sh server  run/server.sh       # one VM
#   bash docker/run-role.sh prefill run/prefill.sh      # 1P1D, VM A
#   bash docker/run-role.sh decode  run/decode.sh       # 1P1D, VM B
#   bash docker/run-role.sh router  run/router.sh       # 1P1D, VM A, after both servers are ready
#   CONCURRENCY=64 bash docker/run-role.sh bench run/bench-decode.sh   # benchmark client, runs in the foreground
#
# Settings come from docker/mimo.env (copy docker/mimo.env.example), including IMAGE, the pushed
# image pinned by digest. Every role except the router also needs MODELS, the host directory
# that holds the model.
#
# Restart policy: on-failure:3 restarts a crashed server. It does not restart the roles after a
# VM or Docker daemon restart and does not detect a hung server; for unattended operation, run
# these commands from systemd or an orchestrator that also checks readiness.
#
# SECURITY: GPU roles run with --privileged, host IPC, /dev/mem and CAP_SYS_ADMIN because
# RDMA (Mooncake) and the AITER path need them; without them Mooncake silently falls back
# to TCP. Run them only on dedicated GPU VMs.
set -euo pipefail

usage="usage: run-role.sh <server|prefill|decode|router|bench> <rendered launch script>"
ROLE="${1:?$usage}"
SCRIPT="$(realpath "${2:?$usage}")"
ENV_FILE="$(realpath "${ENV_FILE:-$(dirname "$0")/mimo.env}")"

case "$ROLE" in server|prefill|decode|router|bench) ;; *) echo "$usage" >&2; exit 2 ;; esac
[ -f "$SCRIPT" ] || { echo "missing launch script: $SCRIPT" >&2; exit 2; }
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE; copy docker/mimo.env.example and fill it in" >&2; exit 2; }
IMAGE="${IMAGE:-$(sed -n 's/^IMAGE=//p' "$ENV_FILE" | tail -n 1)}"
[ -n "$IMAGE" ] || { echo "IMAGE is empty; set it in $ENV_FILE to the pushed image digest" >&2; exit 2; }

base=(--network host --env-file "$ENV_FILE" -v "$SCRIPT":/opt/mimo/launch.sh:ro)

if [ "$ROLE" = bench ]; then
  MODELS="${MODELS:?set MODELS to the host directory that holds the model (the client reads its tokenizer)}"
  exec docker run --rm "${base[@]}" \
    -e CONCURRENCY -e INPUT_LEN -e INPUT_IDS \
    -v "$MODELS":/models:ro \
    "$IMAGE" bash /opt/mimo/launch.sh
fi

service=(--detach --name "mimo-$ROLE" --restart on-failure:3
         --log-opt max-size=200m --log-opt max-file=5)

if [ "$ROLE" = router ]; then
  exec docker run "${service[@]}" "${base[@]}" "$IMAGE" bash /opt/mimo/launch.sh
fi

MODELS="${MODELS:?set MODELS to the host directory that holds the model}"
exec docker run "${service[@]}" "${base[@]}" \
  --privileged --ipc host --shm-size 32g \
  --cap-add CAP_SYS_ADMIN --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined --security-opt label=disable \
  --device /dev/kfd --device /dev/dri --device /dev/mem --group-add video \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -v "$MODELS":/models:ro \
  "$IMAGE" bash /opt/mimo/launch.sh
