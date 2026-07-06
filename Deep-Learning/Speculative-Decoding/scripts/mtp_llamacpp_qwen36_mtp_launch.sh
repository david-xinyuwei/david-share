#!/usr/bin/env bash
set -euo pipefail

WORKDIR=/root/mtp-dflash-repro
LOGDIR="$WORKDIR/logs"
LLAMA_DIR="$WORKDIR/llama.cpp"
SERVER="$LLAMA_DIR/build/bin/llama-server"
mkdir -p "$LOGDIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOGDIR/llamacpp_qwen36_mtp_${TS}.log"
PIDFILE="$WORKDIR/llamacpp_qwen36_mtp.pid"
HF_REPO=${HF_REPO:-unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL}
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8080}
N_GPU_LAYERS=${N_GPU_LAYERS:-99}
CTX_SIZE=${CTX_SIZE:-262000}
PARALLEL=${PARALLEL:-1}
SPEC_DRAFT_N_MAX=${SPEC_DRAFT_N_MAX:-5}

echo "log=$LOG"
echo "pidfile=$PIDFILE"
echo "server=$SERVER"
echo "hf_repo=$HF_REPO"
echo "host=$HOST"
echo "port=$PORT"
echo "ctx_size=$CTX_SIZE"
echo "spec_draft_n_max=$SPEC_DRAFT_N_MAX"

if [[ ! -x "$SERVER" ]]; then
  echo "missing_server_binary=$SERVER"
  exit 2
fi

if [[ -s "$PIDFILE" ]]; then
  old_pid=$(cat "$PIDFILE")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "existing_llama_server_pid=$old_pid"
    echo "Refusing to start another llama-server. Stop it explicitly if needed."
    exit 2
  fi
fi

printf '%s -hf %s -ngl %s -c %s -fa on -np %s --spec-type draft-mtp --spec-draft-n-max %s --host %s --port %s\n' \
  "$SERVER" "$HF_REPO" "$N_GPU_LAYERS" "$CTX_SIZE" "$PARALLEL" "$SPEC_DRAFT_N_MAX" "$HOST" "$PORT" \
  > "$LOGDIR/llamacpp_qwen36_mtp_command_${TS}.txt"

nohup "$SERVER" \
  -hf "$HF_REPO" \
  -ngl "$N_GPU_LAYERS" \
  -c "$CTX_SIZE" \
  -fa on \
  -np "$PARALLEL" \
  --spec-type draft-mtp \
  --spec-draft-n-max "$SPEC_DRAFT_N_MAX" \
  --host "$HOST" \
  --port "$PORT" \
  > "$LOG" 2>&1 &

pid=$!
echo "$pid" > "$PIDFILE"
echo "started_pid=$pid"
echo "started_at=$(date -Is)"