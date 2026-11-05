#!/bin/bash
set -Eeuo pipefail

RUN_ROOT="${RUN_ROOT:?set the frozen run directory}"
HEAD_IP="${HEAD_IP:?set the node-0 private address}"
WORKER_IP="${WORKER_IP:?set the node-1 private address}"
SSH_USER="${SSH_USER:?set the existing peer login}"
KNOWN_HOSTS="${KNOWN_HOSTS:?set the verified peer host-key file}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
SSH_PORT="${SSH_PORT:-33901}"
IMAGE="${IMAGE:-vllm-muse-ray:fiveway-20261103}"
LAYOUTS="${LAYOUTS:-tep,tp,dp,pd}"
PYTHON="${PYTHON:-/usr/bin/python3}"
MODEL_FAMILY="${MODEL_FAMILY:-qwen}"
case "$MODEL_FAMILY" in
  qwen) launcher=11_serve_qwen_fiveway.sh; container_prefix=qwen_fiveway; served_model=qwen-fiveway-bf16 ;;
  muse) launcher=08_serve_muse_2node.sh; container_prefix=muse_selectable; served_model=muse-spark-open-bf16 ;;
  *) printf 'Unsupported model family: %s\n' "$MODEL_FAMILY" >&2; exit 2 ;;
esac
SSH=(ssh -p "$SSH_PORT" -o BatchMode=yes -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=$KNOWN_HOSTS" -o ConnectTimeout=20
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -i "$SSH_KEY"
  "$SSH_USER@$WORKER_IP")
IFS=, read -r -a layout_order <<< "$LAYOUTS"
for layout in "${layout_order[@]}"; do
  case "$layout" in tp|pp|tep|dp|pd) ;; *) printf 'Unsupported layout: %s\n' "$layout" >&2; exit 2 ;; esac
  if [ "$MODEL_FAMILY" = muse ] && { [ "$layout" = dp ] || [ "$layout" = pd ]; }; then
    printf 'Muse %s is outside this two-node runner: DP is disabled and the website P/D selection requires four nodes.\n' "$layout" >&2
    exit 2
  fi
done

peer() {
  local command
  printf -v command '%q ' "$@"
  "${SSH[@]}" "$command"
}

state() {
  "$PYTHON" - "$RUN_ROOT/batch-status.json" "$1" "$2" "${layout:-none}" <<'PY'
import datetime
import json
import os
import sys

path, status, phase, layout = sys.argv[1:]
record = {"status": status, "phase": phase, "layout": layout,
          "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
with open(path + ".tmp", "w", encoding="utf-8") as output:
    json.dump(record, output, indent=2)
os.replace(path + ".tmp", path)
print(json.dumps(record), flush=True)
PY
}

if [ "${DRY_RUN:-0}" = 1 ]; then
  printf 'ORDER=%s\nIMAGE=%s\nMODEL_FAMILY=%s\nLAUNCHER=%s\nSERVED_MODEL=%s\n' "$LAYOUTS" "$IMAGE" "$MODEL_FAMILY" "$launcher" "$served_model"
  for layout in "${layout_order[@]}"; do
    printf 'LAYOUT=%s HEAD=%s WORKER=%s MEASURER=10_measure_layout.sh\n' "$layout" "$HEAD_IP" "$WORKER_IP"
  done
  exit 0
fi

mkdir -p "$RUN_ROOT/logs"
phase=preflight
trap 'exit_code=$?; state FAILED "$phase"; printf "BATCH_FAILED phase=%s exit=%s\n" "$phase" "$exit_code"; exit "$exit_code"' ERR
test -s "$RUN_ROOT/source/$launcher"
test -s "$RUN_ROOT/source/10_measure_layout.sh"
test -s "$KNOWN_HOSTS"
test -r "$SSH_KEY"
if [ -n "${MODEL_SNAPSHOT:-}" ]; then
  phase=weights
  state IN_PROGRESS "$phase"
  snapshot_check='import json,sys; from pathlib import Path; root=Path(sys.argv[1]); index=root/"model.safetensors.index.json"; assert index.is_file(), "snapshot index missing"; names=set(json.loads(index.read_text())["weight_map"].values()); assert names and all((root/name).is_file() and (root/name).stat().st_size > 0 for name in names), "snapshot shards missing"; print("SNAPSHOT_READY shards="+str(len(names)), flush=True)'
  if ! "$PYTHON" -c "$snapshot_check" "$MODEL_SNAPSHOT" >/dev/null 2>&1; then
    test -n "${DOWNLOAD_UNIT_NODE0:-}"
    test "$(systemctl show "$DOWNLOAD_UNIT_NODE0" --property=ActiveState --value)" = active
    sudo -n systemctl --wait start "$DOWNLOAD_UNIT_NODE0"
  fi
  if ! peer "$PYTHON" -c "$snapshot_check" "$MODEL_SNAPSHOT" >/dev/null 2>&1; then
    test -n "${DOWNLOAD_UNIT_NODE1:-}"
    test "$(peer systemctl show "$DOWNLOAD_UNIT_NODE1" --property=ActiveState --value)" = active
    peer sudo -n systemctl --wait start "$DOWNLOAD_UNIT_NODE1"
  fi
  "$PYTHON" -c "$snapshot_check" "$MODEL_SNAPSHOT"
  peer "$PYTHON" -c "$snapshot_check" "$MODEL_SNAPSHOT"
fi
head_image=$(sudo -n docker image inspect --format '{{.Id}}' "$IMAGE")
worker_image=$(peer sudo -n docker image inspect --format '{{.Id}}' "$IMAGE")
test "$head_image" = "$worker_image"
overall=PASS

for layout in "${layout_order[@]}"; do
  output="$RUN_ROOT/$layout"
  container="${container_prefix}_$layout"
  phase=launch
  state IN_PROGRESS "$phase"
  test ! -e "$output/status.json"
  mkdir -p "$output"
  peer mkdir -p "$output"
  if [ "$MODEL_FAMILY" = muse ]; then
    if sudo -n docker container inspect "$container" >/dev/null 2>&1 || peer sudo -n docker container inspect "$container" >/dev/null 2>&1; then
      printf 'Existing Muse container must be preserved: %s\n' "$container" >&2
      exit 2
    fi
  fi
  launch_environment=(RUN_ROOT="$RUN_ROOT" LAYOUT="$layout" HEAD_IP="$HEAD_IP" IMAGE="$IMAGE"
    MOE_ROOT="$RUN_ROOT" MUSE_SERVE_IMAGE="$IMAGE" PP_EXECUTOR=mp CONTAINER_NAME="$container" GPU_UTIL="${GPU_UTIL:-0.95}")
  sudo -n env "${launch_environment[@]}" NODE_IP="$HEAD_IP" LOG="$output/launch-head.log" \
    bash "$RUN_ROOT/source/$launcher" head
  peer sudo -n env "${launch_environment[@]}" NODE_IP="$WORKER_IP" LOG="$output/launch-worker.log" \
    bash "$RUN_ROOT/source/$launcher" worker
  measure_environment=(RUN_ROOT="$RUN_ROOT" LAYOUT="$layout" CONTAINER_NAME="$container"
    SERVED_MODEL="$served_model" BASE_URL=http://127.0.0.1:8000
    CONCURRENCIES="${CONCURRENCIES:-1,2,4,8,16,32,64}" ROUNDS="${ROUNDS:-3}"
    SHORT_MAX_TOKENS="${SHORT_MAX_TOKENS:-512}" GUIDE_MAX_TOKENS="${GUIDE_MAX_TOKENS:-2048}")
  if [ "$layout" = pd ]; then
    sudo -n docker run -d --name qwen_fiveway_pd_proxy --network host \
      -v "$RUN_ROOT:/run-evidence:ro" -e PYTHONUNBUFFERED=1 --entrypoint /usr/bin/python3 "$IMAGE" \
      /run-evidence/source/mooncake_connector_proxy.py --host 0.0.0.0 --port 8000 \
      --prefill "http://$HEAD_IP:8001" 8998 --decode "http://$WORKER_IP:8002"
    measure_environment+=(CONTAINER_NAME=qwen_fiveway_pd_proxy MODEL_CONTAINER_NAME="$container"
      HEALTH_URL="http://$WORKER_IP:8002/health" METRICS_URL="http://$WORKER_IP:8002/metrics"
      PREFILL_METRICS_URL="http://$HEAD_IP:8001/metrics" READY_PATTERN="All prefiller instances are ready.")
  fi
  phase=measure
  state IN_PROGRESS "$phase"
  measure_exit=0
  sudo -n env "${measure_environment[@]}" bash "$RUN_ROOT/source/10_measure_layout.sh" \
    > "$output/measure.log" 2>&1 || measure_exit=$?
  phase=seal
  state IN_PROGRESS "$phase"
  peer sudo -n docker inspect --format '{{.Id}} {{.Image}} {{json .Config.Cmd}}' "$container" > "$output/worker-launch.txt"
  peer sudo -n docker logs "$container" > "$output/worker.log" 2>&1
  peer rocm-smi --showmeminfo vram --json > "$output/worker-gpu-after.json"
  if [ ! -s "$output/server.log" ]; then sudo -n docker logs "$container" > "$output/server.log" 2>&1; fi
  if [ -f "$output/SHA256SUMS" ]; then
    sudo -n sha256sum -c "$output/SHA256SUMS" > "$output/hash-verification.log"
  fi
  sha256sum "$output/worker-launch.txt" "$output/worker.log" "$output/worker-gpu-after.json" > "$output/WORKER_SHA256SUMS"
  test ! -e "$RUN_ROOT/$layout-sealed.tgz"
  sudo -n tar -czf "$RUN_ROOT/$layout-sealed.tgz" -C "$RUN_ROOT" "$layout"
  sha256sum "$RUN_ROOT/$layout-sealed.tgz" > "$RUN_ROOT/$layout-sealed.sha256"
  outcome=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$output/status.json")
  if [ "$measure_exit" != 0 ] || [ "$outcome" != PASS ]; then overall=COMPLETE_WITH_ERRORS; fi
  printf 'LAYOUT_SEALED layout=%s inference_status=%s measure_exit=%s\n' "$layout" "$outcome" "$measure_exit"
  phase=release_model_processes
  if [ "$layout" = pd ]; then sudo -n docker stop -t 30 qwen_fiveway_pd_proxy; fi
  sudo -n docker stop -t 30 "$container"
  peer sudo -n docker stop -t 30 "$container"
done

phase=complete
state "$overall" "$phase"
printf 'BATCH_COMPLETE status=%s VM_POWER_UNCHANGED\n' "$overall"