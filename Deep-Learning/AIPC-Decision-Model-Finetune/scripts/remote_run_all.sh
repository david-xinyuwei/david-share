#!/usr/bin/env bash
# Both sizes, one after the other, so each size's training time and GPU memory are measured without contention.
set -uo pipefail
cd "$(dirname "$0")"
for size in 0.8b 4b; do
  echo "PIPELINE_START $size $(date -Is)"
  bash remote_pipeline.sh "$size"
  echo "PIPELINE_EXIT $size rc=$? $(date -Is)"
done
echo "RUN_ALL_DONE $(date -Is)"
