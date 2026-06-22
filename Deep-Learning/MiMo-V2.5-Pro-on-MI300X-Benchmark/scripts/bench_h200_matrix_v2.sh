#!/bin/bash
# bench_h200_matrix_v2.sh — Full H200-aligned 6-scenario benchmark (AMD PD v2)
# Runs against PD router on localhost:40000
# Output: /data/bench_ep8_v2/h200_matrix_v2_summary.tsv
#
# Author: Xinyu Wei (Microsoft AI GBB)
set -euo pipefail

ROUTER="http://localhost:40000"
MODEL="/data/models/MiMo-V2.5-Pro"
OUTDIR="/data/bench_ep8_v2"
SUMMARY="$OUTDIR/h200_matrix_v2_summary.tsv"
WARMUP=16
SEED=12345

mkdir -p "$OUTDIR"

# Header
echo -e "case\tinput_len\toutput_len\tbs\tsuccess\tinput_tps\toutput_tps\tmedian_ttft_ms\tmedian_tpot_ms\th200_reference\tmi300x_vs_h200\tnote" > "$SUMMARY"

run_case() {
  local CASE=$1 INPUT=$2 OUTPUT=$3 BS=$4 NUM=$5 H200_REF=$6 TIMEOUT=${7:-600}
  local LOG="$OUTDIR/${CASE}.log"
  echo ""
  echo "======================================================================"
  echo "  $CASE: input=$INPUT output=$OUTPUT bs=$BS num=$NUM"
  echo "  H200 ref: $H200_REF"
  echo "  Timeout: ${TIMEOUT}s"
  echo "======================================================================"

  set +e
  timeout ${TIMEOUT} python3 -m sglang.bench_serving \
    --backend sglang \
    --model "$MODEL" \
    --host 0.0.0.0 --port 40000 \
    --dataset-name random \
    --random-input-len $INPUT \
    --random-output-len $OUTPUT \
    --random-range-ratio 1.0 \
    --flush-cache \
    --seed $SEED \
    --num-prompts $NUM \
    --warmup-requests $WARMUP \
    --max-concurrency $BS \
    --pd-separated \
    2>&1 | tee "$LOG"
  local RC=${PIPESTATUS[0]}
  set -e

  # Parse results
  local INPUT_TPS=$(grep -E "Input token throughput|Input throughput" "$LOG" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
  local OUTPUT_TPS=$(grep -E "Output token throughput|Output throughput" "$LOG" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
  local TTFT=$(grep -E "Median TTFT|Median time to first token" "$LOG" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
  local TPOT=$(grep -E "Median TPOT|Median time per output token" "$LOG" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
  local SUCC_RAW=$(grep -E "Successful requests|Successful" "$LOG" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
  local SUCC="$SUCC_RAW/$NUM"

  local NOTE="clean"
  if [[ "$RC" -ne 0 ]]; then
    NOTE="failed_or_timeout_rc_${RC}"
  fi

  echo -e "${CASE}\t${INPUT}\t${OUTPUT}\t${BS}\t${SUCC}\t${INPUT_TPS}\t${OUTPUT_TPS}\t${TTFT}\t${TPOT}\t${H200_REF}\t\t${NOTE}" >> "$SUMMARY"
  echo "[RESULT] $CASE: rc=$RC input_tps=$INPUT_TPS output_tps=$OUTPUT_TPS ttft=$TTFT tpot=$TPOT note=$NOTE"
  sleep 5
}

echo "Starting H200-aligned 6-scenario matrix benchmark (v2 - AMD PD)"
echo "Router: $ROUTER"
echo "Output: $SUMMARY"
echo "Start time: $(date)"

# ============================================================
# Scenario 1: Prefill throughput (output=1)
# H200 EP16/DP2: 8K=31950, 64K=27400, 256K=17400, 768K=8000
# H200 EP32/DP4: 8K=27500, 64K=23000, 256K=13425, 768K=6788
# ============================================================
echo ""
echo "##########################################"
echo "# PREFILL SCENARIOS (output=1, BS=4)    #"
echo "##########################################"

run_case "prefill_8k"   8192   1 4 30 "H200 EP16/DP2 31950; H200 EP32/DP4 27500" 300
run_case "prefill_64k"  65536  1 4 30 "H200 EP16/DP2 27400; H200 EP32/DP4 23000" 600
run_case "prefill_256k" 262144 1 4 20 "H200 EP16/DP2 17400; H200 EP32/DP4 13425" 1200
run_case "prefill_768k" 786432 1 4 20 "H200 EP16/DP2 8000; H200 EP32/DP4 6788" 2400

# ============================================================
# Scenario 2: Decode TPOT context=8K (H200 EP32/DP4)
# H200: BS16=11.59 BS32=12.56 BS64=14.28 BS128=18.25 BS192=23.29 BS256=27.38
# ============================================================
echo ""
echo "##########################################"
echo "# DECODE 8K SCENARIOS (output=1024)     #"
echo "##########################################"

run_case "decode_ctx8k_bs16"  8192 1024 16  200 "H200 TPOT 11.59 ms" 600
run_case "decode_ctx8k_bs32"  8192 1024 32  200 "H200 TPOT 12.56 ms" 600
run_case "decode_ctx8k_bs64"  8192 1024 64  200 "H200 TPOT 14.28 ms" 600
run_case "decode_ctx8k_bs128" 8192 1024 128 200 "H200 TPOT 18.25 ms" 600
run_case "decode_ctx8k_bs192" 8192 1024 192 200 "H200 TPOT 23.29 ms" 600
run_case "decode_ctx8k_bs256" 8192 1024 256 200 "H200 TPOT 27.38 ms" 600

# ============================================================
# Scenario 3: Decode TPOT context=64K (H200 EP32/DP4)
# H200: BS16=11.99 BS32=14.31 BS64=16.33 BS96=19.63
# ============================================================
echo ""
echo "##########################################"
echo "# DECODE 64K SCENARIOS (output=1024)    #"
echo "##########################################"

run_case "decode_ctx64k_bs16" 65536 1024 16  200 "H200 TPOT 11.99 ms" 1200
run_case "decode_ctx64k_bs32" 65536 1024 32  200 "H200 TPOT 14.31 ms" 1200
run_case "decode_ctx64k_bs64" 65536 1024 64  200 "H200 TPOT 16.33 ms" 1200
run_case "decode_ctx64k_bs96" 65536 1024 96  200 "H200 TPOT 19.63 ms" 1200

# ============================================================
# Scenario 4: Decode TPOT context=256K (H200 EP32/DP4)
# H200: BS16=13.93 BS32=16.94
# ============================================================
echo ""
echo "##########################################"
echo "# DECODE 256K SCENARIOS (output=1024)   #"
echo "##########################################"

run_case "decode_ctx256k_bs16" 262144 1024 16 100 "H200 TPOT 13.93 ms" 1800
run_case "decode_ctx256k_bs32" 262144 1024 32 100 "H200 TPOT 16.94 ms" 1800

echo ""
echo "======================================================================"
echo "ALL DONE at $(date)"
echo "Summary: $SUMMARY"
echo "======================================================================"
cat "$SUMMARY"
