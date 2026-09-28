#!/usr/bin/env bash
# Test helper: run tests/load/gpu_load.py on a GPU VM as one or more OS users (Run Command, no SSH).
#
# Usage: ./run-load.sh -g <vm-resource-group> -n <vm-name> -u <user>[,<user>...] [-p "<gpu_load.py phases>"] [-D <delay-s>]
#   -u  users are created if missing (useradd -m); several users start -D seconds apart and overlap on the GPU
#   -p  phases passed to gpu_load.py, default "--phase full:180 --phase held:120 --phase partial:180:0.5"
# Remove test users afterwards with:  -x  (userdel -r for every user in -u, then exit)
set -euo pipefail
export MSYS_NO_PATHCONV=1

RG=""; VM=""; USERS=""; PHASES="--phase full:180 --phase held:120 --phase partial:180:0.5"; DELAY=0; REMOVE=0
while getopts "g:n:u:p:D:xh" opt; do
  case $opt in
    g) RG=$OPTARG ;; n) VM=$OPTARG ;; u) USERS=$OPTARG ;; p) PHASES=$OPTARG ;; D) DELAY=$OPTARG ;; x) REMOVE=1 ;;
    *) sed -n '2,8p' "$0"; exit 1 ;;
  esac
done
[[ -n "$RG" && -n "$VM" && -n "$USERS" ]] || { sed -n '2,8p' "$0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="run-load.$$.sh"

if [[ $REMOVE == 1 ]]; then
  printf '#!/bin/bash\nfor u in %s; do pkill -u "$u" -f gpu_load.py || true; userdel -r "$u" 2>/dev/null && echo "removed $u"; done\n' \
    "${USERS//,/ }" > "$SCRIPT"
else
  LOAD_B64=$(base64 < "$HERE/gpu_load.py" | tr -d '\n')
  {
    printf '#!/bin/bash\nset -e\necho %s | base64 -d > /opt/gpu_load.py && chmod 755 /opt/gpu_load.py\n' "$LOAD_B64"
    printf 'i=0\nfor u in %s; do\n' "${USERS//,/ }"
    printf '  id -u "$u" >/dev/null 2>&1 || useradd -m "$u"\n'
    printf '  sleep $(( i * %s )); i=$((i+1))\n' "$DELAY"
    printf '  systemd-run --unit="gpuload-$u" --uid="$u" --collect /usr/bin/python3 /opt/gpu_load.py %s\n' "$PHASES"
    printf 'done\nsleep 20\nnvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader\n'
    printf 'for u in %s; do systemctl is-active "gpuload-$u" || true; done\n' "${USERS//,/ }"
  } > "$SCRIPT"
fi
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "@$SCRIPT" --query "value[0].message" -o tsv
rm -f "$SCRIPT"
