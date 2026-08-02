#!/bin/bash
set -euo pipefail

: "${PREDICTIONS_PATH:?Set PREDICTIONS_PATH}"
: "${RUN_ID:?Set RUN_ID}"
: "${REPORT_DIR:?Set REPORT_DIR}"

test -f "$PREDICTIONS_PATH"
PREDICTIONS_PATH="$(realpath "$PREDICTIONS_PATH")"
RESUME="${RESUME:-false}"
if [[ "$RESUME" != "true" && "$RESUME" != "false" ]]; then
  echo "RESUME must be true or false: $RESUME" >&2
  exit 2
fi
if test -e "$REPORT_DIR" && ! test -d "$REPORT_DIR"; then
  echo "REPORT_DIR must be a directory: $REPORT_DIR" >&2
  exit 2
fi
if [[ "$RESUME" == "true" ]]; then
  if ! test -d "$REPORT_DIR" || test -z "$(find "$REPORT_DIR" -mindepth 1 -maxdepth 1 -print -quit)"; then
    echo "RESUME=true requires an existing nonempty REPORT_DIR: $REPORT_DIR" >&2
    exit 2
  fi
elif test -d "$REPORT_DIR" && test -n "$(find "$REPORT_DIR" -mindepth 1 -maxdepth 1 -print -quit)"; then
  echo "REPORT_DIR must be empty unless RESUME=true: $REPORT_DIR" >&2
  exit 2
fi
mkdir -p "$REPORT_DIR"
REPORT_DIR="$(realpath "$REPORT_DIR")"

DATASET_NAME="${DATASET_NAME:-princeton-nlp/SWE-Bench_Verified}"
SPLIT="${SPLIT:-test}"
MAX_WORKERS="${MAX_WORKERS:-4}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-1800}"
NAMESPACE="${NAMESPACE:-swebench}"
CACHE_LEVEL="${CACHE_LEVEL:-env}"
CLEAN="${CLEAN:-false}"

if [[ "$CLEAN" != "true" && "$CLEAN" != "false" ]]; then
  echo "CLEAN must be true or false: $CLEAN" >&2
  exit 2
fi

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
  --clean "$CLEAN" \
  --report_dir "$REPORT_DIR"
