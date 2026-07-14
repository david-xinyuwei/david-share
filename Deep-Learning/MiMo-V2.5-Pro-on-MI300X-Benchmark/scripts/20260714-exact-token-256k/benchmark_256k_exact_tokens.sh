#!/usr/bin/env bash
set -Eeuo pipefail

MODEL_PATH="${MODEL_PATH:-/data/models/MiMo-V2.5-Pro}"
DATASET_PATH="${DATASET_PATH:-/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-40000}"
LOG_DIR="${LOG_DIR:-/data/mimo-exact-token-256k}"
mkdir -p "$LOG_DIR"

python3 -m sglang.bench_serving \
  --backend sglang \
  --model "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  --dataset-name random \
  --tokenize-prompt \
  --random-input-len 262144 \
  --random-output-len 1 \
  --random-range-ratio 1.0 \
  --dataset-path "$DATASET_PATH" \
  --flush-cache \
  --seed 12345 \
  --num-prompts 16 \
  --warmup-requests 1 \
  --max-concurrency 4 \
  --pd-separated \
  2>&1 | tee "$LOG_DIR/benchmark_262144_con4.log"