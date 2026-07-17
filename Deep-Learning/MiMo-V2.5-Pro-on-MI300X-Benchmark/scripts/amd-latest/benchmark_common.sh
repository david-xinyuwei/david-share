#!/usr/bin/env bash
set -Eeuo pipefail

export PYTHONPATH="/sgl-workspace/sglang_0625/python${PYTHONPATH:+:$PYTHONPATH}"

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
ROUTER_HOST="${ROUTER_HOST:-0.0.0.0}"
ROUTER_PORT="${ROUTER_PORT:-40000}"
DATASET_PATH="${DATASET_PATH:?Set DATASET_PATH to the benchmark dataset JSON}"
CONTEXT_LENGTH="${CONTEXT_LENGTH:-262151}"
LOG_DIR="${LOG_DIR:?Set LOG_DIR}"

mkdir -p "$LOG_DIR"

run_point() {
  local input_tokens="$1"
  local output_tokens="$2"
  local concurrency="$3"
  local num_prompts="$4"
  local warmup_requests="$5"
  local timeout_seconds="$6"
  local metric_label="$7"
  local input_mode="${8:-text}"
  local stem="$LOG_DIR/benchmark_${input_tokens}_out${output_tokens}_con${concurrency}"
  local rc
  local tokenize_args=()

  if [[ "$input_mode" == "token_ids" ]]; then
    tokenize_args+=(--tokenize-prompt)
  fi

  rm -f "${stem}.rc"
  printf '%s\n' "$CONTEXT_LENGTH" >"${stem}.context_length"
  set +e
  timeout --signal=TERM --kill-after=30s "${timeout_seconds}s" \
    python3 -m sglang.bench_serving \
      --backend sglang \
      --model "$MODEL" \
      --host "$ROUTER_HOST" \
      --port "$ROUTER_PORT" \
      --dataset-name random \
      "${tokenize_args[@]}" \
      --random-input-len "$input_tokens" \
      --random-output-len "$output_tokens" \
      --random-range-ratio 1.0 \
      --dataset-path "$DATASET_PATH" \
      --flush-cache \
      --seed 12345 \
      --num-prompts "$num_prompts" \
      --warmup-requests "$warmup_requests" \
      --max-concurrency "$concurrency" \
      --pd-separated \
      2>&1 | tee "${stem}.log"
  rc="${PIPESTATUS[0]}"
  set -e
  printf '%s\n' "$rc" >"${stem}.rc"

  test "$rc" -eq 0
  grep -Eq "Successful requests:[[:space:]]+${num_prompts}([[:space:]]*)$" "${stem}.log"
  grep -q "$metric_label" "${stem}.log"
  if [[ "$input_mode" == "token_ids" ]]; then
    grep -Eq "Total input tokens:[[:space:]]+$((input_tokens * num_prompts))([[:space:]]*)$" "${stem}.log"
    grep -Eq "Total generated tokens \(retokenized\):[[:space:]]+${num_prompts}([[:space:]]*)$" "${stem}.log"
  fi
  ! grep -Eqi 'Traceback|ClientPayloadError|No available .*worker|TimedOut|Exception:|Failed requests:[[:space:]]+[1-9]' "${stem}.log"
}