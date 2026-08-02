#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

: "${ENDPOINT_MODE:?Set ENDPOINT_MODE}"
: "${MODEL_NAME:?Set MODEL_NAME}"
: "${OUTPUT_ROOT:?Set OUTPUT_ROOT to a new directory}"

MODEL_API_BASE="${MODEL_API_BASE:-}"
: "${MODEL_API_BASE:?Set MODEL_API_BASE}"

INSTANCE_ID="${INSTANCE_ID:-astropy__astropy-7166}"
RUN_LABEL="${RUN_LABEL:-$ENDPOINT_MODE-canary}"
EVALUATION_SCENARIO="${EVALUATION_SCENARIO:-single_endpoint}"

if test -e "$OUTPUT_ROOT"; then
  echo "OUTPUT_ROOT already exists: $OUTPUT_ROOT" >&2
  exit 2
fi
mkdir -p "$OUTPUT_ROOT"

cd "$REPO_ROOT"
python "$SCRIPT_DIR/preflight_provider.py" \
  --mode "$ENDPOINT_MODE" \
  --api-base "$MODEL_API_BASE" \
  --model "$MODEL_NAME" \
  | tee "$OUTPUT_ROOT/provider-preflight.json"

export OUTPUT_DIR="$OUTPUT_ROOT/generation"
export WORKERS=1
export INSTANCE_FILTER
INSTANCE_FILTER="$(python -c 'import re,sys; print("^" + re.escape(sys.argv[1]) + "$")' "$INSTANCE_ID")"
export RUN_LABEL EVALUATION_SCENARIO MODEL_API_BASE

bash "$SCRIPT_DIR/run_generation.sh" 2>&1 | tee "$OUTPUT_ROOT/generation.log"
python "$SCRIPT_DIR/validate_predictions.py" \
  --run-dir "$OUTPUT_DIR" \
  --expected-count 1 \
  --summary "$OUTPUT_ROOT/generation-summary.json"
python "$SCRIPT_DIR/audit_effective_configs.py" --run-dir "$OUTPUT_DIR" \
  > "$OUTPUT_ROOT/effective-config.json"

export PREDICTIONS_PATH="$OUTPUT_DIR/preds.json"
export RUN_ID="${RUN_LABEL//[^A-Za-z0-9_.-]/-}"
export REPORT_DIR="$OUTPUT_ROOT/official-eval"
export MAX_WORKERS=1
export TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-1800}"

bash "$SCRIPT_DIR/run_official_harness.sh" 2>&1 | tee "$OUTPUT_ROOT/official-eval.log"

python - "$REPORT_DIR" <<'PY'
import json
import sys
from pathlib import Path

from scripts.swebench_outcomes import canary_outcome, validate_scored_canary_counts

report_dir = Path(sys.argv[1])
reports = list(report_dir.glob("*.json"))
if len(reports) != 1:
    raise SystemExit(f"Expected one aggregate report, found {len(reports)}")
payload = json.loads(reports[0].read_text())
try:
  counts = validate_scored_canary_counts(payload)
except ValueError as error:
  raise SystemExit(str(error)) from error
print(
    "PIPELINE_CANARY=PASS "
  f"outcome={canary_outcome(counts)} "
  f"resolved={counts['resolved']} "
  f"unresolved={counts['unresolved']} "
  f"empty={counts['empty']} "
  f"errors={counts['errors']}"
)
PY