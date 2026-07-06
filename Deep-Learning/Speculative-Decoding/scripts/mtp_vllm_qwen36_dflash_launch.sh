#!/usr/bin/env bash
set -euo pipefail

WORKDIR=/root/mtp-dflash-repro
LOGDIR="$WORKDIR/logs"
mkdir -p "$LOGDIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOGDIR/vllm_qwen36_dflash_${TS}.log"
PIDFILE="$WORKDIR/vllm_qwen36_dflash.pid"
TARGET_MODEL=${TARGET_MODEL:-Qwen/Qwen3.6-27B}
DFLASH_MODEL=${DFLASH_MODEL:-z-lab/Qwen3.6-27B-DFlash}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-262144}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-256}
NUM_SPECULATIVE_TOKENS=${NUM_SPECULATIVE_TOKENS:-15}
VLLM_DEEP_GEMM_WARMUP=${VLLM_DEEP_GEMM_WARMUP:-skip}
export VLLM_DEEP_GEMM_WARMUP

echo "log=$LOG"
echo "pidfile=$PIDFILE"
echo "target_model=$TARGET_MODEL"
echo "dflash_model=$DFLASH_MODEL"
echo "max_model_len=$MAX_MODEL_LEN"
echo "max_num_seqs=$MAX_NUM_SEQS"
echo "num_speculative_tokens=$NUM_SPECULATIVE_TOKENS"
echo "vllm_deep_gemm_warmup=$VLLM_DEEP_GEMM_WARMUP"

if [[ -s "$PIDFILE" ]]; then
  old_pid=$(cat "$PIDFILE")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "existing_vllm_pid=$old_pid"
    echo "Refusing to start another DFlash vLLM server. Stop it explicitly if needed."
    exit 2
  fi
fi

speculative_config=$(printf '{"method":"dflash","model":"%s","num_speculative_tokens":%s}' "$DFLASH_MODEL" "$NUM_SPECULATIVE_TOKENS")

printf 'VLLM_DEEP_GEMM_WARMUP=%s vllm serve %s --host 127.0.0.1 --max-model-len %s --max-num-seqs %s --reasoning-parser qwen3 --speculative-config %s\n' \
  "$VLLM_DEEP_GEMM_WARMUP" "$TARGET_MODEL" "$MAX_MODEL_LEN" "$MAX_NUM_SEQS" "$speculative_config" \
  > "$LOGDIR/vllm_qwen36_dflash_command_${TS}.txt"

nohup vllm serve "$TARGET_MODEL" \
  --host 127.0.0.1 \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --reasoning-parser qwen3 \
  --speculative-config "$speculative_config" \
  > "$LOG" 2>&1 &

pid=$!
echo "$pid" > "$PIDFILE"
echo "started_pid=$pid"
echo "started_at=$(date -Is)"