#!/usr/bin/env bash
set -uo pipefail

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-40000}"
DATASET_PATH="${DATASET_PATH:-/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json}"
TOKEN_LIST="${TOKEN_LIST:-8192}"
OUTPUT_TOKENS="${OUTPUT_TOKENS:-1024}"
CONCURRENCY_LIST="${CONCURRENCY_LIST:-16 32 64 96 128 192 256}"
NUM_PROMPTS="${NUM_PROMPTS:-256}"
WARMUP_REQUESTS="${WARMUP_REQUESTS:-32}"
SEED="${SEED:-12345}"
LOG_DIR="${LOG_DIR:-/data/xisun/ck_a8w8_concurrency_sweep/decode}"

mkdir -p "$LOG_DIR"
SUMMARY="$LOG_DIR/summary.tsv"
printf 'input_tokens\toutput_tokens\tconcurrency\trc\tsuccessful_requests\toutput_tok_s\tmean_tpot_ms\tmedian_tpot_ms\tp99_tpot_ms\tmean_ttft_ms\tp99_ttft_ms\tlog\n' > "$SUMMARY"

overall_rc=0

metric_value() {
  local label="$1"
  local file="$2"
  grep -m1 "$label" "$file" | awk -F: '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' | awk '{print $1}'
}

for input_tokens in $TOKEN_LIST; do
  for concurrency in $CONCURRENCY_LIST; do
    log="$LOG_DIR/decode_${input_tokens}_out${OUTPUT_TOKENS}_con${concurrency}.log"
    rc_file="$LOG_DIR/decode_${input_tokens}_out${OUTPUT_TOKENS}_con${concurrency}.rc"

    echo
    echo "============================================================"
    echo "Decode sweep: input=${input_tokens}, output=${OUTPUT_TOKENS}, concurrency=${concurrency}"
    echo "Log file: $log"
    echo "============================================================"

    python3 -m sglang.bench_serving \
      --backend sglang \
      --model "$MODEL" \
      --host "$HOST" \
      --port "$PORT" \
      --dataset-name random \
      --random-input-len "$input_tokens" \
      --random-output-len "$OUTPUT_TOKENS" \
      --random-range-ratio 1.0 \
      --dataset-path "$DATASET_PATH" \
      --flush-cache \
      --seed "$SEED" \
      --num-prompts "$NUM_PROMPTS" \
      --warmup-requests "$WARMUP_REQUESTS" \
      --max-concurrency "$concurrency" \
      --pd-separated \
      2>&1 | tee "$log"
    rc=$?
    echo "$rc" > "$rc_file"
    if [[ "$rc" -ne 0 ]]; then
      overall_rc=1
    fi

    successful_requests="$(metric_value 'Successful requests' "$log")"
    output_tok_s="$(metric_value 'Output token throughput' "$log")"
    mean_tpot_ms="$(metric_value 'Mean TPOT' "$log")"
    median_tpot_ms="$(metric_value 'Median TPOT' "$log")"
    p99_tpot_ms="$(metric_value 'P99 TPOT' "$log")"
    mean_ttft_ms="$(metric_value 'Mean TTFT' "$log")"
    p99_ttft_ms="$(metric_value 'P99 TTFT' "$log")"

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$input_tokens" "$OUTPUT_TOKENS" "$concurrency" "$rc" \
      "${successful_requests:-NA}" "${output_tok_s:-NA}" "${mean_tpot_ms:-NA}" \
      "${median_tpot_ms:-NA}" "${p99_tpot_ms:-NA}" "${mean_ttft_ms:-NA}" \
      "${p99_ttft_ms:-NA}" "$log" >> "$SUMMARY"

    echo "Finished decode concurrency=${concurrency}, rc=${rc}"
  done
done

echo "Decode concurrency sweep complete. Summary: $SUMMARY"
exit "$overall_rc"