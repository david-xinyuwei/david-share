#!/usr/bin/env bash
# Start the cached coding matrix through a LiteLLM gateway.
# Build problems.json first: python3 build_swebench_problems.py --out problems.json (needs pyarrow).
# Usage: GATEWAY_URL=https://<gateway> bash run.sh <run-name> [aca_cache_matrix.py options]
# The gateway key is read from .gateway_key (mode 600) next to this file, never from the command line.
# FOREGROUND=1 waits for the run; otherwise it runs under nohup and prints its PID.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
RUN=${1:?run name}
shift
: "${GATEWAY_URL:?set GATEWAY_URL to the gateway's https origin}"
SOURCE_DIR=${SOURCE_DIR:-$ROOT/../coding-matrix}
PROBLEMS=${PROBLEMS:-$ROOT/problems.json}
PROBE_SUMMARY=${PROBE_SUMMARY:-$ROOT/../evidence/coding-matrix-20261026/matrix/probe_summary.json}
PYTHON=${PYTHON:-python3}
OUT="$ROOT/runs/$RUN"
mkdir -p "$OUT"
CLAUDE_GATEWAY_KEY=$(cat "$ROOT/.gateway_key")
export CLAUDE_GATEWAY_KEY
export CLAUDE_GATEWAY_BUDGET_ROOT="$ROOT/runs"
ARGS=(--run-dir "$OUT" --source "$SOURCE_DIR" --gateway-url "$GATEWAY_URL"
      --problems "$PROBLEMS" --probe-summary "$PROBE_SUMMARY" "$@")
if [ "${FOREGROUND:-0}" = 1 ]; then
  "$PYTHON" -u "$ROOT/aca_cache_matrix.py" "${ARGS[@]}" > "$OUT/stdout.log" 2>&1
  echo "EXIT=$?"
else
  nohup "$PYTHON" -u "$ROOT/aca_cache_matrix.py" "${ARGS[@]}" > "$OUT/stdout.log" 2>&1 &
  echo $! > "$OUT/pid"
  echo "PID=$!"
fi
