#!/usr/bin/env bash
# Environment acceptance: reproduce the published transfer-v4 development accuracy of Kev-0.8B (0.648) and Kev-4B (0.817).
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
cd "$KEV"
mkdir -p "$WORK/runs" "$WORK/logs"
for m in kev-0.8b kev-4b; do
  out="$WORK/runs/public-$m-transfer-v4-dev"
  if [ -f "$out/report.json" ]; then echo "SKIP $m (report exists)"; continue; fi
  rm -rf "$out"  # kev.benchmark refuses an existing --out; only an unfinished run reaches this line
  nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 2 > "$WORK/logs/gpu-public-$m.csv" &
  mon=$!
  start=$SECONDS
  echo "BENCH_START $m $(date -Is)"
  "$PY" -m kev.benchmark --run "jaredpalmer/$m@v1.0" --suite evals/v4/transfer-v4 --out "$out" --device cuda
  kill "$mon" || true
  echo "BENCH_DONE $m wall_s=$((SECONDS - start)) peak_gpu_mib=$(cut -d, -f2 "$WORK/logs/gpu-public-$m.csv" | tr -dc '0-9\n' | sort -n | tail -1) $(date -Is)"
done
echo "PUBLIC_BASELINE_DONE $(date -Is)"
