#!/usr/bin/env bash
# Training-memory probe: the smallest training setting (micro-batch 1 x accum 8, bf16, gradient checkpointing,
# max_state 768) on the 64 longest training records, 1 epoch (8 optimizer steps), for each size. The fine-tunes used
# 1 x 8 (0.8B) and 4 x 2 (4B); this measures what a smaller GPU would need for the same recipe at micro-batch 1.
# Runs after the other GPU jobs (waits for the given PID) so the GPU is not shared. Output: state/memory-probe.status
# Usage: remote_memory_probe.sh <pid to wait for>
set -uo pipefail
source "$(dirname "$0")/remote_env.sh"
WAIT_PID="${1:-}"
STATUS="$META/state/memory-probe.status"
P="$WORK/runs/memory-probe"
mkdir -p "$P"
if [ -n "$WAIT_PID" ]; then while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done; fi
"$PY" - "$WORK/data/contoso/train.jsonl" "$P/longest64.jsonl" <<'PY'
import json, sys
rows = [l for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
rows.sort(key=lambda l: len(json.dumps(json.loads(l)["state"], ensure_ascii=False)), reverse=True)
open(sys.argv[2], "w", encoding="utf-8").writelines(rows[:64])
print("longest64 state chars", len(json.dumps(json.loads(rows[0])["state"], ensure_ascii=False)), "->", len(json.dumps(json.loads(rows[63])["state"], ensure_ascii=False)))
PY
cd "$KEV"
for SIZE in 0.8b 4b; do
  case "$SIZE" in
    0.8b) BASE=Qwen/Qwen3.5-0.8B-Base; REV=dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 ;;
    4b)   BASE=Qwen/Qwen3.5-4B-Base;   REV=1001bb4d826a52d1f399e183466143f4da7b741b ;;
  esac
  rm -rf "$P/$SIZE"
  nvidia-smi --query-gpu=timestamp,memory.used --format=csv,noheader -l 1 > "$P/gpu-$SIZE.csv" & mon=$!
  start=$SECONDS
  "$PY" -m kev.train --data "$P/longest64.jsonl" --base "$BASE" --base_revision "$REV" --init_from "jaredpalmer/kev-$SIZE@v1.0" \
    --epochs 1 --lr 2e-5 --batch 1 --accum 8 --dtype bf16 --checkpointing 1 --max_state 768 --device cuda --seed 1 \
    --out "$P/$SIZE" > "$P/train-$SIZE.log" 2>&1
  rc=$?
  kill "$mon" 2>/dev/null
  peak=$(cut -d, -f2 "$P/gpu-$SIZE.csv" | tr -dc '0-9\n' | sort -n | tail -1)
  idle=$(head -n 1 "$P/gpu-$SIZE.csv" | cut -d, -f2 | tr -dc '0-9')
  echo "PROBE $SIZE batch=1 accum=8 records=64 rc=$rc wall_s=$((SECONDS - start)) peak_gpu_mib=$peak gpu_mib_before=$idle $(date -Is)" | tee -a "$STATUS"
done
echo "PROBE_DONE $(date -Is)" | tee -a "$STATUS"
