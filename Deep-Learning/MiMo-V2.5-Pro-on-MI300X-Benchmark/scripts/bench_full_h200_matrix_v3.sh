#!/bin/bash
# bench_full_h200_matrix_v3.sh — Complete H200-aligned 6-scenario matrix
# EP8/DP1, page-size=1 (default), AMD full-PD infra (etcd/UCX/OpenMPI installed)
# Runs against PD router on localhost:40000
# Output: /data/bench_ep8_v3/full_matrix_v3_summary.tsv
#
# Author: Xinyu Wei (Microsoft AI GBB)
set -euo pipefail

MODEL="/data/models/MiMo-V2.5-Pro"
OUTDIR="/data/bench_ep8_v3"
SUMMARY="$OUTDIR/full_matrix_v3_summary.tsv"
WARMUP=16
SEED=12345
mkdir -p "$OUTDIR"

echo -e "case\tinput_len\toutput_len\tbs\tsuccess\tinput_tps\toutput_tps\tmedian_ttft_ms\tmedian_tpot_ms\th200_reference\tnote" > "$SUMMARY"

parse_metric() {
  local pattern="$1" file="$2"
  grep -E "$pattern" "$file" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A"
}

run_case() {
  local CASE=$1 INPUT=$2 OUTPUT=$3 BS=$4 NUM=$5 H200_REF=$6 TIMEOUT=${7:-900}
  local LOG="$OUTDIR/${CASE}.log"
  echo ""
  echo "======================================================================"
  echo "  $CASE: input=$INPUT output=$OUTPUT bs=$BS num=$NUM timeout=${TIMEOUT}s"
  echo "  H200 ref: $H200_REF"
  echo "======================================================================"

  set +e
  timeout "$TIMEOUT" python3 -m sglang.bench_serving \
    --backend sglang \
    --model "$MODEL" \
    --host 0.0.0.0 --port 40000 \
    --dataset-name random \
    --random-input-len "$INPUT" \
    --random-output-len "$OUTPUT" \
    --random-range-ratio 1.0 \
    --flush-cache \
    --seed "$SEED" \
    --num-prompts "$NUM" \
    --warmup-requests "$WARMUP" \
    --max-concurrency "$BS" \
    --pd-separated \
    2>&1 | tee "$LOG"
  local RC=${PIPESTATUS[0]}
  set -e

  local SUCCESS_RAW INPUT_TPS OUTPUT_TPS TTFT TPOT NOTE
  SUCCESS_RAW=$(parse_metric "Successful requests" "$LOG")
  INPUT_TPS=$(parse_metric "Input token throughput" "$LOG")
  OUTPUT_TPS=$(parse_metric "Output token throughput" "$LOG")
  TTFT=$(parse_metric "Median TTFT" "$LOG")
  TPOT=$(parse_metric "Median TPOT" "$LOG")
  NOTE="clean"
  if [[ "$RC" -ne 0 ]]; then
    NOTE="failed_or_timeout_rc_${RC}"
  fi
  echo -e "${CASE}\t${INPUT}\t${OUTPUT}\t${BS}\t${SUCCESS_RAW}/${NUM}\t${INPUT_TPS}\t${OUTPUT_TPS}\t${TTFT}\t${TPOT}\t${H200_REF}\t${NOTE}" >> "$SUMMARY"
  echo "[RESULT] $CASE rc=$RC success=$SUCCESS_RAW/$NUM input_tps=$INPUT_TPS output_tps=$OUTPUT_TPS tpot=$TPOT note=$NOTE"
  sleep 5
}

echo "============================================================"
echo "Full H200-aligned matrix v3 (EP8, page-size=1, AMD full-PD infra)"
echo "Start: $(date)"
echo "============================================================"

# === PREFILL (output=1, BS=4) ===
run_case "prefill_8k"   8192   1 4 30 "H200 EP16/DP2 31950; EP32/DP4 27500" 300
run_case "prefill_64k"  65536  1 4 30 "H200 EP16/DP2 27400; EP32/DP4 23000" 900
run_case "prefill_256k" 262144 1 4 20 "H200 EP16/DP2 17400; EP32/DP4 13425" 1800
run_case "prefill_768k" 786432 1 4 20 "H200 EP16/DP2 8000; EP32/DP4 6788" 2400

# === DECODE 8K (output=1024) ===
run_case "decode_ctx8k_bs16"  8192 1024 16  200 "H200 TPOT 11.59 ms" 600
run_case "decode_ctx8k_bs32"  8192 1024 32  200 "H200 TPOT 12.56 ms" 600
run_case "decode_ctx8k_bs64"  8192 1024 64  200 "H200 TPOT 14.28 ms" 600
run_case "decode_ctx8k_bs128" 8192 1024 128 200 "H200 TPOT 18.25 ms" 900
run_case "decode_ctx8k_bs192" 8192 1024 192 200 "H200 TPOT 23.29 ms" 900
run_case "decode_ctx8k_bs256" 8192 1024 256 200 "H200 TPOT 27.38 ms" 900

# === DECODE 64K (output=1024) ===
run_case "decode_ctx64k_bs16" 65536 1024 16 200 "H200 TPOT 11.99 ms" 1200
run_case "decode_ctx64k_bs32" 65536 1024 32 200 "H200 TPOT 14.31 ms" 1200
run_case "decode_ctx64k_bs64" 65536 1024 64 200 "H200 TPOT 16.33 ms" 1200
run_case "decode_ctx64k_bs96" 65536 1024 96 200 "H200 TPOT 19.63 ms" 1200

# === DECODE 256K (output=1024) ===
run_case "decode_ctx256k_bs16" 262144 1024 16 100 "H200 TPOT 13.93 ms" 1800
run_case "decode_ctx256k_bs32" 262144 1024 32 100 "H200 TPOT 16.94 ms" 1800

echo ""
echo "============================================================"
echo "ALL DONE at $(date)"
echo "============================================================"
cat "$SUMMARY"
