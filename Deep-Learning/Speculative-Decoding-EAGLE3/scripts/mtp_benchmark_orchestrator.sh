#!/usr/bin/env bash
set -euo pipefail
#
# Orchestrate all 3 notebook routes: start server → wait ready → benchmark → stop → next.
# Run on H100 VM:  bash /root/mtp_benchmark_orchestrator.sh
#
WORKDIR=/root/mtp-dflash-repro
LOGDIR="$WORKDIR/logs"
RESULTDIR="$WORKDIR/benchmark_results"
CLIENT="$WORKDIR/mtp_benchmark_client.py"
RUNS=${RUNS:-3}
WARMUP=${WARMUP:-1}
TS=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULTDIR"

wait_for_port() {
  local port=$1 timeout=$2
  echo "  waiting for port $port (max ${timeout}s)..."
  for i in $(seq 1 "$timeout"); do
    if ss -ltnp | grep -q ":${port} "; then
      echo "  port $port ready after ${i}s"
      return 0
    fi
    sleep 1
  done
  echo "  ERROR: port $port not ready after ${timeout}s"
  return 1
}

stop_server() {
  local pidfile=$1
  if [[ -s "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  stopping pid=$pid ..."
      kill "$pid" || true
      sleep 3
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
  sleep 2
  echo "  GPU after stop: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) MiB"
}

echo "=========================================="
echo "MTP / DFlash Benchmark Orchestrator"
echo "timestamp=$TS  runs=$RUNS  warmup=$WARMUP"
echo "=========================================="

############################################################
# Route 1: vLLM native MTP
############################################################
echo ""
echo ">>> Route 1: vLLM native MTP (num_speculative_tokens=5)"
export VLLM_DEEP_GEMM_WARMUP=skip
MAX_NUM_SEQS=256 bash /root/mtp_vllm_qwen36_mtp_launch.sh
wait_for_port 8000 600

python3 "$CLIENT" \
  --base-url http://127.0.0.1:8000 \
  --label "vllm-native-mtp" \
  --runs "$RUNS" --warmup "$WARMUP" --no-stream \
  --output "$RESULTDIR/vllm_native_mtp_${TS}.json"

stop_server "$WORKDIR/vllm_qwen36_mtp.pid"

############################################################
# Route 2: vLLM DFlash
############################################################
echo ""
echo ">>> Route 2: vLLM DFlash (z-lab/Qwen3.6-27B-DFlash, num_speculative_tokens=15)"
export VLLM_DEEP_GEMM_WARMUP=skip
MAX_MODEL_LEN=252000 MAX_NUM_SEQS=256 bash /root/mtp_vllm_qwen36_dflash_launch.sh
wait_for_port 8000 600

python3 "$CLIENT" \
  --base-url http://127.0.0.1:8000 \
  --label "vllm-dflash" \
  --runs "$RUNS" --warmup "$WARMUP" --no-stream \
  --output "$RESULTDIR/vllm_dflash_${TS}.json"

stop_server "$WORKDIR/vllm_qwen36_dflash.pid"

############################################################
# Route 3: llama.cpp MTP GGUF
############################################################
echo ""
echo ">>> Route 3: llama.cpp MTP GGUF (UD-Q4_K_XL, draft-mtp, 5 tokens)"
bash /root/mtp_llamacpp_qwen36_mtp_launch.sh
wait_for_port 8080 600

python3 "$CLIENT" \
  --base-url http://127.0.0.1:8080 \
  --label "llamacpp-mtp-q4kxl" \
  --runs "$RUNS" --warmup "$WARMUP" --no-stream \
  --output "$RESULTDIR/llamacpp_mtp_q4kxl_${TS}.json"

stop_server "$WORKDIR/llamacpp_qwen36_mtp.pid"

############################################################
# Summary
############################################################
echo ""
echo "=========================================="
echo "All 3 routes benchmarked. Results in:"
ls -lh "$RESULTDIR"/*_${TS}.json
echo "=========================================="
