#!/usr/bin/env bash
# remote_pipeline.sh with the micro-batch configurable (BATCH x ACCUM, effective batch 8 by default).
# Separate file because remote_pipeline.sh was executing when this change was needed (bash reads a running script by offset).
# One model size end to end on the Contoso data: released baselines -> fine-tune -> temperature on calib -> evaluate -> compare.
# Usage: BATCH=4 ACCUM=2 remote_pipeline_v2.sh 0.8b|4b      (re-running skips stages whose report already exists)
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
SIZE="$1"
BATCH="${BATCH:-1}"
ACCUM="${ACCUM:-8}"
case "$SIZE" in
  0.8b) BASE=Qwen/Qwen3.5-0.8B-Base; REV=dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 ;;
  4b)   BASE=Qwen/Qwen3.5-4B-Base;   REV=1001bb4d826a52d1f399e183466143f4da7b741b ;;
  *) echo "size must be 0.8b or 4b"; exit 2 ;;
esac
REL="jaredpalmer/kev-$SIZE@v1.0"  # the tag whose transfer-v4 numbers were reproduced on this VM
D="$WORK/data/contoso"
R="$WORK/runs/$SIZE"
FT="$R/ft"
STATUS="$META/state/pipeline-$SIZE.status"
mkdir -p "$R" "$META/state"
cd "$KEV"
stage() { echo "$1 $(date -Is)" | tee -a "$STATUS"; }
gpu_watch() { nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 2 > "$R/gpu-$1.csv" & echo $!; }
peak() { cut -d, -f2 "$R/gpu-$1.csv" | tr -dc '0-9\n' | sort -n | tail -1; }

bench() {  # name run data
  local out="$R/$1"
  [ -f "$out/report.json" ] && return 0
  [ -f "$3" ] || { echo "SKIP $1 (no $3 yet)" | tee -a "$STATUS"; return 0; }
  rm -rf "$out"
  "$PY" -m kev.benchmark --run "$2" --data "$3" --out "$out" --device cuda > "$R/$1.log" 2>&1
  "$PY" -c "import json,sys; c=json.load(open(sys.argv[1]))['clean']; print('BENCH', sys.argv[2], 'acc=%.4f brier=%.4f ece=%.4f n=%d' % (c['acc'], c['brier'], c['ece'], c['n']))" "$out/report.json" "$1" | tee -a "$STATUS"
}

SETS="test_support test_assistant ood_support ood_assistant dev_support dev_assistant"
stage "STAGE baseline_released"
for s in $SETS; do bench "b0-$s" "$REL" "$D/$s.jsonl"; done
for s in test_support test_assistant ood_support ood_assistant; do bench "b0policy-$s" "$REL" "$D/policy_$s.jsonl"; done

if [ ! -f "$FT/head.pt" ]; then
  stage "STAGE train batch=$BATCH accum=$ACCUM"
  mon=$(gpu_watch train); start=$SECONDS
  "$PY" -m kev.train --data "$D/train.jsonl" --suite evals/v7/decision-v7 --replay 1000 \
    --base "$BASE" --base_revision "$REV" --init_from "$REL" --epochs 2 --lr 2e-5 --batch "$BATCH" --accum "$ACCUM" \
    --dtype bf16 --checkpointing 1 --max_state 768 --device cuda --seed 1 --out "$FT" > "$R/train.log" 2>&1
  kill "$mon" || true
  echo "TRAIN_DONE wall_s=$((SECONDS - start)) peak_gpu_mib=$(peak train) batch=$BATCH accum=$ACCUM $(date -Is)" | tee -a "$STATUS"
  (cd "$FT" && sha256sum $(ls) > "$R/ft-raw.sha256" 2>/dev/null || true)
fi

stage "STAGE calibrate"
bench ft-calib-raw "$FT" "$D/calib.jsonl"
if ! grep -q CALIBRATED "$STATUS"; then
  "$PY" scripts/calibrate_checkpoint.py --run "$FT" --rows "$R/ft-calib-raw/rows.json" --allow-in-distribution > "$R/calibrate.log" 2>&1
  echo "CALIBRATED $(tail -n 3 "$R/calibrate.log" | tr '\n' ' ')" | tee -a "$STATUS"
  (cd "$FT" && sha256sum $(ls) > "$R/ft-calibrated.sha256" 2>/dev/null || true)
fi

stage "STAGE evaluate_finetuned"
for s in $SETS; do bench "ft-$s" "$FT" "$D/$s.jsonl"; done
if [ ! -f "$R/ft-public-transfer-v4-dev/report.json" ]; then
  rm -rf "$R/ft-public-transfer-v4-dev"
  "$PY" -m kev.benchmark --run "$FT" --suite evals/v4/transfer-v4 --out "$R/ft-public-transfer-v4-dev" --device cuda > "$R/ft-public.log" 2>&1
  "$PY" -c "import json,sys; c=json.load(open(sys.argv[1]))['clean']; print('BENCH ft-public-transfer-v4-dev acc=%.4f brier=%.4f' % (c['acc'], c['brier']))" "$R/ft-public-transfer-v4-dev/report.json" | tee -a "$STATUS"
fi

stage "STAGE compare"
for s in test_support test_assistant ood_support ood_assistant; do
  [ -f "$R/ft-$s/report.json" ] && [ -f "$R/b0-$s/report.json" ] || continue
  [ -d "$R/cmp-$s" ] || "$PY" -m kev.compare --candidate "$R/ft-$s" --reference "$R/b0-$s" --out "$R/cmp-$s" > "$R/cmp-$s.log" 2>&1 || echo "COMPARE_FAILED $s" | tee -a "$STATUS"
done
stage "PIPELINE_DONE"
