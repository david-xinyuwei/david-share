#!/bin/bash
# bench_amd_pd_separated_profile.sh — AMD guide style PD-separated profiling
#
# Run inside VM8 container after the prefill and decode SGLang servers are ready.
# This follows the SGLang bench_serving PD-separated profiling mode:
#   - Prefill workers are profiled with --profile-prefill-url
#   - Decode workers are profiled with --profile-decode-url
# These two modes are intentionally separate and cannot be passed together.
#
# Author: Xinyu Wei (Microsoft AI GBB)
set +e

DIR=/data/bench_amd_pd_profile
LOG=$DIR/results.log
SUMMARY=$DIR/summary.tsv
MODEL=/data/models/MiMo-V2.5-Pro
PREFILL_URL=${PREFILL_URL:-http://127.0.0.1:30000}
DECODE_URL=${DECODE_URL:-http://172.16.1.122:30001}
COMMON="--backend sglang --model $MODEL --tokenizer $MODEL --dataset-name random --random-range-ratio 1.0 --seed 12345 --pd-separated --flush-cache"

mkdir -p "$DIR"
rm -f "$DIR"/*.log "$SUMMARY" "$LOG"
printf "case\tmode\tinput_len\toutput_len\tbs\tnum_prompts\ttimeout_s\texit_code\tstatus\tsuccess\tinput_tps\toutput_tps\tmedian_ttft_ms\tmedian_tpot_ms\n" > "$SUMMARY"

echo "============================================================" | tee "$LOG"
echo "AMD-style PD-separated profiling — MiMo-V2.5-Pro MI300X"     | tee -a "$LOG"
echo "Started at $(date -u)"                                      | tee -a "$LOG"
echo "Prefill profile URL: $PREFILL_URL"                          | tee -a "$LOG"
echo "Decode profile URL: $DECODE_URL"                            | tee -a "$LOG"
echo "Dataset: random, fixed length, seed=12345"                  | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

metric() {
  local file=$1 pattern=$2
  grep -E "$pattern" "$file" 2>/dev/null | tail -1 | awk -F: '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' | awk '{print $1}'
}

health_check() {
  curl -fsS --max-time 10 "$PREFILL_URL/v1/models" >/dev/null 2>&1 && echo "[health] prefill OK" | tee -a "$LOG" || echo "[health] prefill FAIL" | tee -a "$LOG"
  curl -fsS --max-time 10 "$DECODE_URL/v1/models" >/dev/null 2>&1 && echo "[health] decode OK" | tee -a "$LOG" || echo "[health] decode FAIL" | tee -a "$LOG"
}

run_prefill() {
  local label=$1 input_len=$2 bs=$3 num_prompts=$4 timeout_s=$5
  local outfile="$DIR/${label}.log"
  echo "" | tee -a "$LOG"
  echo "--- $label | AMD-PD prefill profile in=$input_len out=1 BS=$bs n=$num_prompts timeout=${timeout_s}s | $(date -u) ---" | tee -a "$LOG"
  health_check
  timeout "$timeout_s" python3 -m sglang.bench_serving $COMMON \
    --profile-prefill-url "$PREFILL_URL" \
    --random-input-len "$input_len" \
    --random-output-len 1 \
    --max-concurrency "$bs" \
    --num-prompts "$num_prompts" \
    2>&1 | tee "$outfile"
  record_result "$label" "prefill" "$input_len" 1 "$bs" "$num_prompts" "$timeout_s" "$outfile" "${PIPESTATUS[0]}"
}

run_decode() {
  local label=$1 input_len=$2 bs=$3 num_prompts=$4 timeout_s=$5
  local outfile="$DIR/${label}.log"
  echo "" | tee -a "$LOG"
  echo "--- $label | AMD-PD decode profile in=$input_len out=1024 BS=$bs n=$num_prompts timeout=${timeout_s}s | $(date -u) ---" | tee -a "$LOG"
  health_check
  timeout "$timeout_s" python3 -m sglang.bench_serving $COMMON \
    --profile-decode-url "$DECODE_URL" \
    --random-input-len "$input_len" \
    --random-output-len 1024 \
    --max-concurrency "$bs" \
    --num-prompts "$num_prompts" \
    2>&1 | tee "$outfile"
  record_result "$label" "decode" "$input_len" 1024 "$bs" "$num_prompts" "$timeout_s" "$outfile" "${PIPESTATUS[0]}"
}

record_result() {
  local label=$1 mode=$2 input_len=$3 output_len=$4 bs=$5 num_prompts=$6 timeout_s=$7 outfile=$8 rc=$9
  local status="OK"
  if [[ "$rc" == "124" ]]; then
    status="TIMEOUT"
  elif grep -qE 'Traceback|Exception|ERROR|ClientPayloadError|TransferEncodingError' "$outfile"; then
    status="ERROR_SEEN"
  elif ! grep -q 'Successful requests' "$outfile"; then
    status="NO_SUMMARY"
  fi

  local success input_tps output_tps ttft tpot
  success=$(metric "$outfile" 'Successful requests')
  input_tps=$(metric "$outfile" 'Input token throughput')
  output_tps=$(metric "$outfile" 'Output token throughput')
  ttft=$(metric "$outfile" 'Median TTFT')
  tpot=$(metric "$outfile" 'Median TPOT')

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$label" "$mode" "$input_len" "$output_len" "$bs" "$num_prompts" "$timeout_s" "$rc" "$status" \
    "${success:-}" "${input_tps:-}" "${output_tps:-}" "${ttft:-}" "${tpot:-}" >> "$SUMMARY"

  grep -E 'Successful|Failed|Output token throughput|Input token throughput|Median TPOT|Median TTFT|Traceback|ERROR|Exception|ClientPayloadError|TransferEncodingError' "$outfile" 2>/dev/null | tee -a "$LOG"
  echo "CASE_STATUS: $status exit=$rc" | tee -a "$LOG"
  sleep 15
}

# Quick first pass: H200 prefill lengths and decode context representative points.
run_prefill prefill_8k_amd_pd 8192 4 16 900
run_prefill prefill_64k_amd_pd 65536 4 16 1800
run_prefill prefill_256k_amd_pd_single 262144 1 1 1800

for bs in 16 32 64 128 192 256; do
  run_decode "decode_ctx8k_bs${bs}_amd_pd" 8192 "$bs" "$bs" 1800
done
for bs in 16 32 64 96; do
  run_decode "decode_ctx64k_bs${bs}_amd_pd" 65536 "$bs" "$bs" 3600
done
run_decode decode_ctx256k_bs16_amd_pd 262144 16 16 5400
run_decode decode_ctx256k_bs32_amd_pd 262144 32 32 7200

echo "" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
echo "DONE at $(date -u)" | tee -a "$LOG"
echo "Summary: $SUMMARY" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
