#!/bin/bash
set -euo pipefail

: "${PREDICTIONS_PATH:?Set PREDICTIONS_PATH}"
: "${RUN_ID:?Set RUN_ID}"
: "${REPORT_DIR:?Set REPORT_DIR}"

test -f "$PREDICTIONS_PATH"
PREDICTIONS_PATH="$(realpath "$PREDICTIONS_PATH")"
mkdir -p "$REPORT_DIR"
REPORT_DIR="$(realpath "$REPORT_DIR")"

DATASET_NAME="${DATASET_NAME:-princeton-nlp/SWE-Bench_Verified}"
SPLIT="${SPLIT:-test}"
MAX_WORKERS="${MAX_WORKERS:-4}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-1800}"
NAMESPACE="${NAMESPACE:-swebench}"
CACHE_LEVEL="${CACHE_LEVEL:-env}"

cd "$REPORT_DIR"
exec python -m swebench.harness.run_evaluation \
  --dataset_name "$DATASET_NAME" \
  --split "$SPLIT" \
  --predictions_path "$PREDICTIONS_PATH" \
  --max_workers "$MAX_WORKERS" \
  --timeout "$TIMEOUT_SECONDS" \
  --run_id "$RUN_ID" \
  --namespace "$NAMESPACE" \
  --cache_level "$CACHE_LEVEL" \
  --clean true \
  --report_dir "$REPORT_DIR"
