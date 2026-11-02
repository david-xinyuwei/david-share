#!/usr/bin/env bash
# Second training round for one size, as two arms that differ in exactly one thing each from the published FT-cf recipe
# (remote_cf_round.sh: train_cf.jsonl, 2 epochs, LoRA r16 + pointer head, lr 2e-5, batch 4 x accum 2, bf16, seed 1):
#   A  = train_cf2.jsonl (scripts/augment_round2.py: + region flips, + onsite_repair positives), 2 epochs  -> "more data"
#   B  = train_cf.jsonl unchanged, 4 epochs                                                              -> "more epochs"
#   C  = train_cf2.jsonl, 4 epochs                                                                        -> "both" (added after A and B: epochs won, data alone did not)
# Each arm: train -> fit temperature on calib.jsonl -> score every evaluation set used by the README (in-distribution,
# out-of-distribution, counterfactual, public transfer-v4) -> kev.compare against the arm's own B0 rows.
# Outputs live under runs/<size>/r2-<arm>/... so nothing of the 2026-10-27 run is touched or reused by accident.
# Usage: remote_round2.sh 0.8b A|B|C [A|B|C ...]      (re-running skips finished stages of the same arm)
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
SIZE="$1"; shift
case "$SIZE" in
  0.8b) BASE=Qwen/Qwen3.5-0.8B-Base; REV=dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 ;;
  4b)   BASE=Qwen/Qwen3.5-4B-Base;   REV=1001bb4d826a52d1f399e183466143f4da7b741b ;;
  *) echo "size must be 0.8b or 4b"; exit 2 ;;
esac
REL="jaredpalmer/kev-$SIZE@v1.0"
D="$WORK/data/contoso"
R="$WORK/runs/$SIZE"
mkdir -p "$R" "$META/state"
cd "$KEV"
EVAL_SETS="test_support test_assistant ood_support ood_assistant dev_support dev_assistant test_cf_support test_cf_assistant ood_cf_support ood_cf_assistant dev_cf_support dev_cf_assistant"

gpu_watch() { nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 2 > "$R/gpu-$1.csv" & echo $!; }
peak() { cut -d, -f2 "$R/gpu-$1.csv" | tr -dc '0-9\n' | sort -n | tail -1; }

for ARM in "$@"; do
  case "$ARM" in
    A) DATA="$D/train_cf2.jsonl"; EPOCHS=2; TAG=r2-A ;;
    B) DATA="$D/train_cf.jsonl";  EPOCHS=4; TAG=r2-B ;;
    C) DATA="$D/train_cf2.jsonl"; EPOCHS=4; TAG=r2-C ;;
    *) echo "arm must be A, B or C"; exit 2 ;;
  esac
  CK="$R/$TAG"
  STATUS="$META/state/round2-$SIZE-$ARM.status"
  stage() { echo "$1 $(date -Is)" | tee -a "$STATUS"; }
  bench() {  # name data
    local out="$R/$TAG-$1"
    [ -s "$2" ] || { echo "MISSING_DATA $2" | tee -a "$STATUS"; return 3; }
    [ -f "$out/report.json" ] && return 0
    rm -rf "$out"
    "$PY" -m kev.benchmark --run "$CK" --data "$2" --out "$out" --device cuda > "$R/$TAG-$1.log" 2>&1
    "$PY" -c "import json,sys; c=json.load(open(sys.argv[1]))['clean']; print('BENCH', sys.argv[2], 'acc=%.4f brier=%.4f ece=%.4f n=%d' % (c['acc'], c['brier'], c['ece'], c['n']))" "$out/report.json" "$TAG-$1" | tee -a "$STATUS"
  }
  [ -f "$DATA" ] || { echo "MISSING_DATA $DATA" | tee -a "$STATUS"; exit 3; }
  stage "ROUND2_START arm=$ARM data=$(basename "$DATA") epochs=$EPOCHS records=$(wc -l < "$DATA") sha256=$(sha256sum "$DATA" | cut -c1-16)"

  if [ ! -f "$CK/head.pt" ]; then
    stage "STAGE train arm=$ARM"
    mon=$(gpu_watch "$TAG-train"); start=$SECONDS
    "$PY" -m kev.train --data "$DATA" --suite evals/v7/decision-v7 --replay 1000 \
      --base "$BASE" --base_revision "$REV" --init_from "$REL" --epochs "$EPOCHS" --lr 2e-5 --batch 4 --accum 2 \
      --dtype bf16 --checkpointing 1 --max_state 768 --device cuda --seed 1 --out "$CK" > "$R/$TAG-train.log" 2>&1
    kill "$mon" || true
    echo "TRAIN_DONE arm=$ARM wall_s=$((SECONDS - start)) peak_gpu_mib=$(peak "$TAG-train") epochs=$EPOCHS $(date -Is)" | tee -a "$STATUS"
    (cd "$CK" && sha256sum $(ls) > "$R/$TAG-raw.sha256" 2>/dev/null || true)
  fi

  stage "STAGE calibrate arm=$ARM"
  bench calib-raw "$D/calib.jsonl"
  if ! grep -q '^CALIBRATED' "$STATUS"; then
    "$PY" scripts/calibrate_checkpoint.py --run "$CK" --rows "$R/$TAG-calib-raw/rows.json" --allow-in-distribution > "$R/$TAG-calibrate.log" 2>&1
    echo "CALIBRATED arm=$ARM $(tail -n 3 "$R/$TAG-calibrate.log" | tr '\n' ' ')" | tee -a "$STATUS"
    (cd "$CK" && sha256sum $(ls) > "$R/$TAG-calibrated.sha256" 2>/dev/null || true)
  fi

  stage "STAGE evaluate arm=$ARM"
  for s in $EVAL_SETS; do bench "$s" "$D/$s.jsonl"; done
  if [ ! -f "$R/$TAG-public-transfer-v4-dev/report.json" ]; then
    rm -rf "$R/$TAG-public-transfer-v4-dev"
    "$PY" -m kev.benchmark --run "$CK" --suite evals/v4/transfer-v4 --out "$R/$TAG-public-transfer-v4-dev" --device cuda > "$R/$TAG-public.log" 2>&1
    "$PY" -c "import json,sys; c=json.load(open(sys.argv[1]))['clean']; print('BENCH %s-public-transfer-v4-dev acc=%.4f brier=%.4f' % (sys.argv[2], c['acc'], c['brier']))" "$R/$TAG-public-transfer-v4-dev/report.json" "$TAG" | tee -a "$STATUS"
  fi

  stage "STAGE compare arm=$ARM"
  for s in test_support test_assistant ood_support ood_assistant test_cf_support ood_cf_support; do
    [ -s "$R/b0-$s/report.json" ] && [ -s "$R/$TAG-$s/report.json" ] || { stage "MISSING_COMPARISON_INPUT b0 $s"; exit 3; }
    "$PY" -m kev.compare --candidate "$R/$TAG-$s" --reference "$R/b0-$s" --out "$R/cmp-$TAG-b0-$s" > "$R/cmp-$TAG-b0-$s.log" 2>&1 || { stage "COMPARE_FAILED b0 $s"; exit 4; }
  done
  stage "ROUND2_DONE arm=$ARM"
done
