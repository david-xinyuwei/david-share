#!/usr/bin/env bash
# Second fine-tuning arm "FT-cf": the first recipe plus counterfactual variants of the training cases
# (train_cf.jsonl from scripts/augment_counterfactual.py: same text, one policy field changed, label recomputed),
# micro-batch 4 x accum 2 (effective batch 8 as before). Added after the first fine-tune gave both records of most
# field-flip pairs the same answer. Scores B0, B0-policy and the first fine-tune on the variant-only sets, trains FT-cf,
# fits its temperature on the same calibration set, scores it everywhere and compares.
# Usage: remote_cf_round.sh 0.8b|4b      (re-running skips finished stages)
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
SIZE="$1"
case "$SIZE" in
  0.8b) BASE=Qwen/Qwen3.5-0.8B-Base; REV=dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 ;;
  4b)   BASE=Qwen/Qwen3.5-4B-Base;   REV=1001bb4d826a52d1f399e183466143f4da7b741b ;;
  *) echo "size must be 0.8b or 4b"; exit 2 ;;
esac
REL="jaredpalmer/kev-$SIZE@v1.0"
D="$WORK/data/contoso"
R="$WORK/runs/$SIZE"
FT="$R/ft"
FC="$R/ft_cf"
STATUS="$META/state/pipeline-cf-$SIZE.status"
mkdir -p "$R" "$META/state"
cd "$KEV"
stage() { echo "$1 $(date -Is)" | tee -a "$STATUS"; }
gpu_watch() { nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 2 > "$R/gpu-$1.csv" & echo $!; }
peak() { cut -d, -f2 "$R/gpu-$1.csv" | tr -dc '0-9\n' | sort -n | tail -1; }

bench() {  # name run data
  local out="$R/$1"
  [ -f "$out/report.json" ] && return 0
  [ -f "$3" ] || { echo "SKIP $1 (no $3)" | tee -a "$STATUS"; return 0; }
  rm -rf "$out"
  "$PY" -m kev.benchmark --run "$2" --data "$3" --out "$out" --device cuda > "$R/$1.log" 2>&1
  "$PY" -c "import json,sys; c=json.load(open(sys.argv[1]))['clean']; print('BENCH', sys.argv[2], 'acc=%.4f brier=%.4f ece=%.4f n=%d' % (c['acc'], c['brier'], c['ece'], c['n']))" "$out/report.json" "$1" | tee -a "$STATUS"
}

CF_SETS="test_cf_support test_cf_assistant ood_cf_support ood_cf_assistant dev_cf_support dev_cf_assistant"
stage "STAGE baseline_cf"
for s in $CF_SETS; do bench "b0-$s" "$REL" "$D/$s.jsonl"; done
for s in test_cf_support test_cf_assistant ood_cf_support ood_cf_assistant; do bench "b0policy-$s" "$REL" "$D/policy_$s.jsonl"; done
if [ -f "$FT/head.pt" ]; then
  for s in $CF_SETS; do bench "ft-$s" "$FT" "$D/$s.jsonl"; done
fi

if [ ! -f "$FC/head.pt" ]; then
  stage "STAGE train_cf batch=4 accum=2"
  mon=$(gpu_watch train_cf); start=$SECONDS
  "$PY" -m kev.train --data "$D/train_cf.jsonl" --suite evals/v7/decision-v7 --replay 1000 \
    --base "$BASE" --base_revision "$REV" --init_from "$REL" --epochs 2 --lr 2e-5 --batch 4 --accum 2 \
    --dtype bf16 --checkpointing 1 --max_state 768 --device cuda --seed 1 --out "$FC" > "$R/train_cf.log" 2>&1
  kill "$mon" || true
  echo "TRAIN_CF_DONE wall_s=$((SECONDS - start)) peak_gpu_mib=$(peak train_cf) batch=4 accum=2 $(date -Is)" | tee -a "$STATUS"
  (cd "$FC" && sha256sum $(ls) > "$R/ft_cf-raw.sha256" 2>/dev/null || true)
fi

stage "STAGE calibrate_cf"
bench ftcf-calib-raw "$FC" "$D/calib.jsonl"
if ! grep -q '^CALIBRATED_CF' "$STATUS"; then
  "$PY" scripts/calibrate_checkpoint.py --run "$FC" --rows "$R/ftcf-calib-raw/rows.json" --allow-in-distribution > "$R/calibrate_cf.log" 2>&1
  echo "CALIBRATED_CF $(tail -n 3 "$R/calibrate_cf.log" | tr '\n' ' ')" | tee -a "$STATUS"
  (cd "$FC" && sha256sum $(ls) > "$R/ft_cf-calibrated.sha256" 2>/dev/null || true)
fi

stage "STAGE evaluate_cf"
for s in test_support test_assistant ood_support ood_assistant dev_support dev_assistant $CF_SETS; do
  bench "ftcf-$s" "$FC" "$D/$s.jsonl"
done
if [ ! -f "$R/ftcf-public-transfer-v4-dev/report.json" ]; then
  rm -rf "$R/ftcf-public-transfer-v4-dev"
  "$PY" -m kev.benchmark --run "$FC" --suite evals/v4/transfer-v4 --out "$R/ftcf-public-transfer-v4-dev" --device cuda > "$R/ftcf-public.log" 2>&1
  "$PY" -c "import json,sys; c=json.load(open(sys.argv[1]))['clean']; print('BENCH ftcf-public-transfer-v4-dev acc=%.4f brier=%.4f' % (c['acc'], c['brier']))" "$R/ftcf-public-transfer-v4-dev/report.json" | tee -a "$STATUS"
fi

stage "STAGE compare_cf"
for s in test_support test_assistant ood_support ood_assistant test_cf_support test_cf_assistant ood_cf_support ood_cf_assistant; do
  for ref in b0 ft; do
    [ -f "$R/ftcf-$s/report.json" ] && [ -f "$R/$ref-$s/report.json" ] || continue
    "$PY" -m kev.compare --candidate "$R/ftcf-$s" --reference "$R/$ref-$s" --out "$R/cmpcf-$ref-$s" > "$R/cmpcf-$ref-$s.log" 2>&1 || echo "COMPARE_FAILED $ref $s" | tee -a "$STATUS"
  done
done
stage "PIPELINE_CF_DONE"
