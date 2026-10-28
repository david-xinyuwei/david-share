#!/usr/bin/env bash
# Replaces remote_run_all.sh after the 0.8B run started: waits for that run, then trains 4B with batch 4 x accum 2
# (same effective batch 8, about twice the throughput on the H100), then re-runs 0.8B to score the late OOD files.
set -uo pipefail
cd "$(dirname "$0")"
WAIT_PID="$1"
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done
echo "WAITED pid=$WAIT_PID $(date -Is)"
for args in "4b 4 2" "0.8b 1 8"; do
  set -- $args
  echo "PIPELINE_START $1 batch=$2 accum=$3 $(date -Is)"
  BATCH="$2" ACCUM="$3" bash remote_pipeline_v2.sh "$1"
  echo "PIPELINE_EXIT $1 rc=$? $(date -Is)"
done
echo "AFTER_08B_DONE $(date -Is)"
