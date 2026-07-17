#!/bin/bash
# Sustained fixed-batch long-context Decode benchmark (single MI300X node, TP8).
# Reproduces the 2026-07-18 matched-batch points: 64K base context at fixed
# batch 16/8/4 plus the 8K internal scaling reference, each with 8,192 output
# tokens so that every request decodes concurrently at the full client batch.
#
# Start the server first with launch_single_node_decode.sh, wait for
# http://127.0.0.1:30001/health, then run this script on the same node.
set -euo pipefail

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
DATASET_PATH="${DATASET_PATH:-/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json}"
LOG_DIR="${LOG_DIR:-/data/mimo-fixedbatch/points}"
mkdir -p "$LOG_DIR"

run_point() {
  local input="$1" output="$2" bs="$3" timeout_s="$4"
  local stem="$LOG_DIR/benchmark_${input}_out${output}_bs${bs}"
  rm -f "${stem}.rc"
  timeout --signal=TERM --kill-after=30s "${timeout_s}s" \
    python3 -m sglang.bench_serving \
      --backend sglang \
      --model "$MODEL" \
      --host 127.0.0.1 --port 30001 \
      --dataset-name random \
      --random-input-len "$input" \
      --random-output-len "$output" \
      --random-range-ratio 1.0 \
      --dataset-path "$DATASET_PATH" \
      --flush-cache \
      --seed 12345 \
      --num-prompts "$bs" \
      --warmup-requests 1 \
      --max-concurrency "$bs" \
      2>&1 | tee "${stem}.log"
  local rc="${PIPESTATUS[0]}"
  printf '%s\n' "$rc" > "${stem}.rc"
  grep -Eq "Successful requests:[[:space:]]+${bs}([[:space:]]*)$" "${stem}.log"
  ! grep -Eqi "Traceback|ClientPayloadError|No available|TimedOut|Exception:" "${stem}.log"
  return "$rc"
}

run_point 8192 8192 16 1500
run_point 65536 8192 16 2400
run_point 65536 8192 8 2400
run_point 65536 8192 4 2400
