#!/bin/bash
# bench_targeted_256k_recovery.sh — targeted fallback pass for H200 256K-aligned cases
# Run inside VM8 container after prefill/decode/router are ready.
#
# This script avoids the monolithic full matrix. Each long-context case has a timeout
# so a stuck 256K request cannot block the remaining cases indefinitely.
#
# Author: Xinyu Wei (Microsoft AI GBB)
set +e

DIR=/data/bench_ep8_recovery_256k
LOG=$DIR/results.log
mkdir -p "$DIR"
rm -f "$DIR"/*.log

MODEL=/data/models/MiMo-V2.5-Pro
BASE="--backend sglang --host 127.0.0.1 --port 40000 --model $MODEL --tokenizer $MODEL --dataset-name random --random-range-ratio 1.0 --flush-cache --seed 12345"

echo "============================================================" | tee "$LOG"
echo "Targeted 256K Recovery Benchmark — PD + MTP + EP=8"          | tee -a "$LOG"
echo "Started at $(date -u)"                                        | tee -a "$LOG"
echo "Endpoint: http://127.0.0.1:40000 (PD router)"                 | tee -a "$LOG"
echo "Config: TP=8, EP=8, MORI, MTP/EAGLE layer=3, chunk=16384"     | tee -a "$LOG"
echo "Dataset: random (fixed length), seed=12345"                  | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

run_case() {
  local LABEL=$1
  local INPUT=$2
  local OUTPUT=$3
  local BS=$4
  local NPROMPTS=$5
  local SECONDS=$6
  local OUTFILE="$DIR/${LABEL}.log"

  echo "" | tee -a "$LOG"
  echo "--- $LABEL | in=$INPUT out=$OUTPUT BS=$BS n=$NPROMPTS timeout=${SECONDS}s | $(date -u) ---" | tee -a "$LOG"

  timeout "$SECONDS" python3 -m sglang.bench_serving $BASE \
    --random-input-len "$INPUT" \
    --random-output-len "$OUTPUT" \
    --max-concurrency "$BS" \
    --num-prompts "$NPROMPTS" \
    2>&1 | tee "$OUTFILE"

  local RC=${PIPESTATUS[0]}
  echo "EXIT_CODE: $RC" | tee -a "$LOG"
  if [[ "$RC" == "124" ]]; then
    echo "STATUS: TIMEOUT" | tee -a "$LOG"
  fi

  grep -E "Successful|Failed|Output token throughput|Input token throughput|Median TPOT|Median TTFT|Traceback|ERROR|Exception" \
    "$OUTFILE" 2>/dev/null | tee -a "$LOG"

  sleep 15
}

# Prefill fallback points: lower concurrency to get stable 256K numbers.
run_case "prefill_256k_bs1_n4" 262144 1 1 4 2400
run_case "prefill_256k_bs2_n8" 262144 1 2 8 3600

# Decode H200 256K points: keep H200 batch sizes, reduce prompts to one full batch.
run_case "decode_ctx256k_bs16_n16" 262144 1024 16 16 5400
run_case "decode_ctx256k_bs32_n32" 262144 1024 32 32 7200

echo "" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
echo "DONE at $(date -u)" | tee -a "$LOG"
echo "Results in $DIR/" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
