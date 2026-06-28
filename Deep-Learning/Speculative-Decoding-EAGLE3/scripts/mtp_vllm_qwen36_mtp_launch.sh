#!/usr/bin/env bash
set -euo pipefail

WORKDIR=/root/mtp-dflash-repro
LOGDIR="$WORKDIR/logs"
mkdir -p "$LOGDIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOGDIR/vllm_qwen36_mtp_${TS}.log"
PIDFILE="$WORKDIR/vllm_qwen36_mtp.pid"
MAX_NUM_SEQS=${MAX_NUM_SEQS:-256}
VLLM_DEEP_GEMM_WARMUP=${VLLM_DEEP_GEMM_WARMUP:-skip}
export VLLM_DEEP_GEMM_WARMUP

echo "log=$LOG"
echo "pidfile=$PIDFILE"
echo "max_num_seqs=$MAX_NUM_SEQS"
echo "vllm_deep_gemm_warmup=$VLLM_DEEP_GEMM_WARMUP"

if [[ -s "$PIDFILE" ]]; then
  old_pid=$(cat "$PIDFILE")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "existing_vllm_pid=$old_pid"
    echo "Refusing to start another vLLM server. Stop it explicitly if needed."
    exit 2
  fi
fi

cat > "$LOGDIR/vllm_qwen36_mtp_command_${TS}.txt" <<'CMD'
vllm serve Qwen/Qwen3.6-27B --host 127.0.0.1 --max-model-len 262144 --max-num-seqs ${MAX_NUM_SEQS:-256} --reasoning-parser qwen3 --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":5}'
CMD

nohup vllm serve Qwen/Qwen3.6-27B \
  --host 127.0.0.1 \
  --max-model-len 262144 \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --reasoning-parser qwen3 \
  --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":5}' \
  > "$LOG" 2>&1 &

pid=$!
echo "$pid" > "$PIDFILE"
echo "started_pid=$pid"
echo "started_at=$(date -Is)"