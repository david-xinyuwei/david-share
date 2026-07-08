#!/usr/bin/env bash
set -uo pipefail

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-40000}"
DATASET_PATH="${DATASET_PATH:-/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json}"
TOKEN_LIST="${TOKEN_LIST:-8192 65536 262144}"
OUTPUT_TOKENS="${OUTPUT_TOKENS:-1}"
CONCURRENCY_LIST="${CONCURRENCY_LIST:-1 2 4 8}"
NUM_PROMPTS="${NUM_PROMPTS:-16}"
WARMUP_REQUESTS="${WARMUP_REQUESTS:-1}"
SEED="${SEED:-12345}"
LOG_DIR="${LOG_DIR:-/data/xisun/ck_a8w8_concurrency_sweep/prefill}"

mkdir -p "$LOG_DIR"
SUMMARY="$LOG_DIR/summary.tsv"
printf 'input_tokens\toutput_tokens\tconcurrency\trc\tsuccessful_requests\tinput_tok_s\tmean_ttft_ms\tp99_ttft_ms\tobserved_concurrency\tlog\n' > "$SUMMARY"

overall_rc=0

metric_value() {
  local label="$1"
  local file="$2"
  grep -m1 "$label" "$file" | awk -F: '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' | awk '{print $1}'
}

for input_tokens in $TOKEN_LIST; do
  for concurrency in $CONCURRENCY_LIST; do
    log="$LOG_DIR/prefill_${input_tokens}_out${OUTPUT_TOKENS}_con${concurrency}.log"
    rc_file="$LOG_DIR/prefill_${input_tokens}_out${OUTPUT_TOKENS}_con${concurrency}.rc"

    echo
    echo "============================================================"
    echo "Prefill sweep: input=${input_tokens}, output=${OUTPUT_TOKENS}, concurrency=${concurrency}"
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
    input_tok_s="$(metric_value 'Input token throughput' "$log")"
    mean_ttft_ms="$(metric_value 'Mean TTFT' "$log")"
    p99_ttft_ms="$(metric_value 'P99 TTFT' "$log")"
    observed_concurrency="$(metric_value '^Concurrency' "$log")"

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$input_tokens" "$OUTPUT_TOKENS" "$concurrency" "$rc" \
      "${successful_requests:-NA}" "${input_tok_s:-NA}" "${mean_ttft_ms:-NA}" \
      "${p99_ttft_ms:-NA}" "${observed_concurrency:-NA}" "$log" >> "$SUMMARY"

    echo "Finished prefill input=${input_tokens}, concurrency=${concurrency}, rc=${rc}"
  done
done

echo "Prefill concurrency sweep complete. Summary: $SUMMARY"
exit "$overall_rc"