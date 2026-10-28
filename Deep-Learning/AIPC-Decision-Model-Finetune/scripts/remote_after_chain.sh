#!/usr/bin/env bash
# Runs the FT-cf arm after the current driver (remote_after_08b.sh: 4B first recipe, then 0.8B out-of-distribution
# baselines) has exited, so the GPU is never shared and every training wall time stays a dedicated measurement.
# Usage: remote_after_chain.sh <pid of remote_after_08b.sh>
set -uo pipefail
cd "$(dirname "$0")"
WAIT_PID="$1"
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done
echo "WAITED pid=$WAIT_PID $(date -Is)"
for size in 0.8b 4b; do
  echo "CF_START $size $(date -Is)"
  bash remote_cf_round.sh "$size"
  echo "CF_EXIT $size rc=$? $(date -Is)"
done
echo "AFTER_CHAIN_DONE $(date -Is)"
