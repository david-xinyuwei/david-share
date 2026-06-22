#!/bin/bash
# bench_decode_matrix_v2.sh — Decode-first H200-aligned matrix for EP8 AMD full-PD setup
# Runs against the PD router on localhost:40000 and does not stop on failed cases.
# Output: /data/bench_ep8_v2/decode_matrix_v2_summary.tsv
#
# Author: Xinyu Wei (Microsoft AI GBB)
set -euo pipefail

MODEL="/data/models/MiMo-V2.5-Pro"
OUTDIR="/data/bench_ep8_v2"
SUMMARY="$OUTDIR/decode_matrix_v2_summary.tsv"
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
  echo "  $CASE: input=$INPUT output=$OUTPUT bs=$BS num=$NUM"
  echo "  H200 ref: $H200_REF"
  echo "  Timeout: ${TIMEOUT}s"
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
  SUCCESS_RAW=$(parse_metric "Successful requests|Successful" "$LOG")
  INPUT_TPS=$(parse_metric "Input token throughput|Input throughput" "$LOG")
  OUTPUT_TPS=$(parse_metric "Output token throughput|Output throughput" "$LOG")
  TTFT=$(parse_metric "Median TTFT|Median time to first token" "$LOG")
  TPOT=$(parse_metric "Median TPOT|Median time per output token" "$LOG")
  NOTE="clean"
  if [[ "$RC" -ne 0 ]]; then
    NOTE="failed_or_timeout_rc_${RC}"
  fi
  echo -e "${CASE}\t${INPUT}\t${OUTPUT}\t${BS}\t${SUCCESS_RAW}/${NUM}\t${INPUT_TPS}\t${OUTPUT_TPS}\t${TTFT}\t${TPOT}\t${H200_REF}\t${NOTE}" >> "$SUMMARY"
  echo "[RESULT] $CASE rc=$RC success=$SUCCESS_RAW/$NUM output_tps=$OUTPUT_TPS tpot=$TPOT note=$NOTE"
  sleep 5
}

echo "Starting decode-first H200 matrix benchmark (EP8 AMD full-PD) at $(date)"

# Decode context 8K, H200 EP32/DP4
run_case "decode_ctx8k_bs16"  8192 1024 16  200 "H200 TPOT 11.59 ms" 600
run_case "decode_ctx8k_bs32"  8192 1024 32  200 "H200 TPOT 12.56 ms" 600
run_case "decode_ctx8k_bs64"  8192 1024 64  200 "H200 TPOT 14.28 ms" 600
run_case "decode_ctx8k_bs128" 8192 1024 128 200 "H200 TPOT 18.25 ms" 600
run_case "decode_ctx8k_bs192" 8192 1024 192 200 "H200 TPOT 23.29 ms" 600
run_case "decode_ctx8k_bs256" 8192 1024 256 200 "H200 TPOT 27.38 ms" 600

# Decode context 64K, H200 EP32/DP4
run_case "decode_ctx64k_bs16" 65536 1024 16 200 "H200 TPOT 11.99 ms" 1200
run_case "decode_ctx64k_bs32" 65536 1024 32 200 "H200 TPOT 14.31 ms" 1200
run_case "decode_ctx64k_bs64" 65536 1024 64 200 "H200 TPOT 16.33 ms" 1200
run_case "decode_ctx64k_bs96" 65536 1024 96 200 "H200 TPOT 19.63 ms" 1200

# Decode context 256K last, because it may stress PD router/prefill response drain.
run_case "decode_ctx256k_bs16" 262144 1024 16 100 "H200 TPOT 13.93 ms" 1800
run_case "decode_ctx256k_bs32" 262144 1024 32 100 "H200 TPOT 16.94 ms" 1800

echo "ALL DONE at $(date)"
cat "$SUMMARY"
