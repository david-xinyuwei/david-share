#!/bin/bash
set -euo pipefail

: "${OUTPUT_DIR:?Set OUTPUT_DIR}"
: "${MODEL_NAME:?Set MODEL_NAME}"

ENDPOINT_MODE="${ENDPOINT_MODE:-openai_compatible}"
EVALUATION_SCENARIO="${EVALUATION_SCENARIO:-single_endpoint}"
RUN_LABEL="${RUN_LABEL:-$ENDPOINT_MODE}"
WORKERS="${WORKERS:-8}"
CONFIG="${CONFIG:-configs/oss-model.yaml}"
SUBSET="${SUBSET:-verified}"
SPLIT="${SPLIT:-test}"
INSTANCE_FILTER="${INSTANCE_FILTER:-}"
INSTANCE_MANIFEST="${INSTANCE_MANIFEST:-}"
MODEL_API_KEY="${MODEL_API_KEY:-}"
DOCKER_EXECUTABLE="${MSWEA_DOCKER_EXECUTABLE:-docker}"
PYTHON_EXECUTABLE="${PYTHON_EXECUTABLE:-python3}"

if test -n "$INSTANCE_FILTER" && test -n "$INSTANCE_MANIFEST"; then
  echo "Set only one of INSTANCE_FILTER or INSTANCE_MANIFEST" >&2
  exit 2
fi
INSTANCE_SELECTOR=all
INSTANCE_MANIFEST_SHA256=""
if test -n "$INSTANCE_MANIFEST"; then
  if ! test -f "$INSTANCE_MANIFEST"; then
    echo "INSTANCE_MANIFEST not found: $INSTANCE_MANIFEST" >&2
    exit 2
  fi
  selector="$({ python3 - "$INSTANCE_MANIFEST" <<'PY'
import csv
import hashlib
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open(newline="") as stream:
    reader = csv.DictReader(stream, delimiter="\t")
    if not reader.fieldnames or "instance_id" not in reader.fieldnames:
        raise SystemExit("INSTANCE_MANIFEST must be TSV with an instance_id column")
    instance_ids = [row.get("instance_id", "") for row in reader]
if not instance_ids or any(not instance_id for instance_id in instance_ids):
    raise SystemExit("INSTANCE_MANIFEST contains no instances or an empty ID")
if len(instance_ids) != len(set(instance_ids)):
    raise SystemExit("INSTANCE_MANIFEST contains duplicate instance IDs")
pattern = "^(?:" + "|".join(re.escape(value) for value in sorted(instance_ids)) + ")$"
print(pattern)
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
  } 2>&1)" || {
    echo "$selector" >&2
    exit 2
  }
  INSTANCE_FILTER="$(printf '%s\n' "$selector" | sed -n '1p')"
  INSTANCE_MANIFEST_SHA256="$(printf '%s\n' "$selector" | sed -n '2p')"
  INSTANCE_SELECTOR=manifest
elif test -n "$INSTANCE_FILTER"; then
  INSTANCE_SELECTOR=filter
fi

if ! command -v "$DOCKER_EXECUTABLE" >/dev/null 2>&1; then
  echo "Docker executable not found: $DOCKER_EXECUTABLE" >&2
  exit 2
fi
if ! "$DOCKER_EXECUTABLE" version >/dev/null 2>&1; then
  echo "Docker daemon is not reachable through: $DOCKER_EXECUTABLE" >&2
  exit 2
fi

case "$EVALUATION_SCENARIO" in
  single_endpoint|onprem_to_managed|cloud_to_managed|base_vs_finetuned) ;;
  *)
    echo "Unsupported EVALUATION_SCENARIO: $EVALUATION_SCENARIO" >&2
    exit 2
    ;;
esac

extra_config=()
case "$ENDPOINT_MODE" in
  openai_compatible)
    : "${MODEL_API_BASE:?Set MODEL_API_BASE for openai_compatible mode}"
    case "$MODEL_NAME" in
      hosted_vllm/*) ;;
      *) MODEL_NAME="hosted_vllm/$MODEL_NAME" ;;
    esac
    export HOSTED_VLLM_API_KEY="${MODEL_API_KEY:-${HOSTED_VLLM_API_KEY:-EMPTY}}"
    AUTH_ENV_NAME=HOSTED_VLLM_API_KEY
    ;;
  azure_foundry)
    : "${MODEL_API_BASE:?Set MODEL_API_BASE for azure_foundry mode}"
    MODEL_API_BASE="${MODEL_API_BASE%/}"
    case "$MODEL_API_BASE" in
      */openai/v1) ;;
      *) MODEL_API_BASE="$MODEL_API_BASE/openai/v1" ;;
    esac
    case "$MODEL_NAME" in
      hosted_vllm/*) ;;
      azure/*) MODEL_NAME="hosted_vllm/${MODEL_NAME#azure/}" ;;
      *) MODEL_NAME="hosted_vllm/$MODEL_NAME" ;;
    esac
    AZURE_FOUNDRY_CREDENTIAL="${MODEL_API_KEY:-${AZURE_API_KEY:-${AZURE_OPENAI_API_KEY:-${AZURE_AD_TOKEN:-}}}}"
    if test -z "$AZURE_FOUNDRY_CREDENTIAL"; then
      echo "Set AZURE_API_KEY, AZURE_OPENAI_API_KEY, AZURE_AD_TOKEN, or MODEL_API_KEY" >&2
      exit 2
    fi
    export HOSTED_VLLM_API_KEY="$AZURE_FOUNDRY_CREDENTIAL"
    AUTH_ENV_NAME=HOSTED_VLLM_API_KEY
    extra_config+=("-c" "model.model_class=scripts.provider_model.FoundryOpenAIModel")
    ;;
  fireworks)
    MODEL_API_BASE="${MODEL_API_BASE:-https://api.fireworks.ai/inference/v1}"
    case "$MODEL_NAME" in
      fireworks_ai/*) ;;
      *) MODEL_NAME="fireworks_ai/$MODEL_NAME" ;;
    esac
    if test -n "$MODEL_API_KEY"; then
      export FIREWORKS_AI_API_KEY="$MODEL_API_KEY"
    fi
    if test -z "${FIREWORKS_AI_API_KEY:-}"; then
      echo "Set FIREWORKS_AI_API_KEY or MODEL_API_KEY" >&2
      exit 2
    fi
    export FIREWORKS_AI_API_BASE="$MODEL_API_BASE"
    AUTH_ENV_NAME=FIREWORKS_AI_API_KEY
    ;;
  *)
    echo "Unsupported ENDPOINT_MODE: $ENDPOINT_MODE" >&2
    exit 2
    ;;
esac

mkdir -p "$OUTPUT_DIR"
CONTRACT_PATH="$OUTPUT_DIR/provider-contract.json"
export CONTRACT_PATH ENDPOINT_MODE EVALUATION_SCENARIO RUN_LABEL MODEL_NAME MODEL_API_BASE
export AUTH_ENV_NAME WORKERS CONFIG SUBSET SPLIT
export INSTANCE_SELECTOR INSTANCE_MANIFEST_SHA256
"$PYTHON_EXECUTABLE" - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["CONTRACT_PATH"])
payload = {
    "schema_version": 1,
    "endpoint_mode": os.environ["ENDPOINT_MODE"],
    "evaluation_scenario": os.environ["EVALUATION_SCENARIO"],
    "run_label": os.environ["RUN_LABEL"],
    "model_name": os.environ["MODEL_NAME"],
    "api_base": os.environ["MODEL_API_BASE"],
    "auth_env_name": os.environ["AUTH_ENV_NAME"],
    "subset": os.environ["SUBSET"],
    "split": os.environ["SPLIT"],
    "workers": int(os.environ["WORKERS"]),
    "instance_selector": os.environ["INSTANCE_SELECTOR"],
    "instance_manifest_sha256": os.environ["INSTANCE_MANIFEST_SHA256"] or None,
    "config": os.environ["CONFIG"],
    "protocol": "openai_chat_completions_with_function_tools",
}
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
os.replace(temporary, path)
PY

args=(
  "$PYTHON_EXECUTABLE" -m minisweagent.run.benchmarks.swebench
  --subset "$SUBSET"
  --split "$SPLIT"
  --output "$OUTPUT_DIR"
  --workers "$WORKERS"
  -c swebench.yaml
  -c "$CONFIG"
  -c "model.model_name=$MODEL_NAME"
  -c "model.model_kwargs.api_base=$MODEL_API_BASE"
  "${extra_config[@]}"
)

if test -n "$INSTANCE_FILTER"; then
  args+=(--filter "$INSTANCE_FILTER")
fi

printf 'GENERATION_START output=%s mode=%s scenario=%s label=%s workers=%s subset=%s split=%s\n' \
  "$OUTPUT_DIR" "$ENDPOINT_MODE" "$EVALUATION_SCENARIO" "$RUN_LABEL" "$WORKERS" "$SUBSET" "$SPLIT"
exec "${args[@]}"
