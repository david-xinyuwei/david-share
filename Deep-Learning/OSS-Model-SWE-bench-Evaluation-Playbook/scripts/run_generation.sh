#!/bin/bash
set -euo pipefail

: "${OUTPUT_DIR:?Set OUTPUT_DIR}"
: "${MODEL_API_BASE:?Set MODEL_API_BASE, including /v1}"
: "${MODEL_NAME:?Set MODEL_NAME}"

MODEL_API_KEY="${MODEL_API_KEY:-${HOSTED_VLLM_API_KEY:-EMPTY}}"
export HOSTED_VLLM_API_KEY="$MODEL_API_KEY"
WORKERS="${WORKERS:-8}"
CONFIG="${CONFIG:-configs/oss-model.yaml}"
SUBSET="${SUBSET:-verified}"
SPLIT="${SPLIT:-test}"
INSTANCE_FILTER="${INSTANCE_FILTER:-}"

args=(
  python -m minisweagent.run.benchmarks.swebench
  --subset "$SUBSET"
  --split "$SPLIT"
  --output "$OUTPUT_DIR"
  --workers "$WORKERS"
  -c swebench.yaml
  -c "$CONFIG"
  -c "model.model_name=$MODEL_NAME"
  -c "model.model_kwargs.api_base=$MODEL_API_BASE"
)

if test -n "$INSTANCE_FILTER"; then
  args+=(--filter "$INSTANCE_FILTER")
fi

printf 'GENERATION_START output=%s workers=%s subset=%s split=%s\n' \
  "$OUTPUT_DIR" "$WORKERS" "$SUBSET" "$SPLIT"
exec "${args[@]}"
