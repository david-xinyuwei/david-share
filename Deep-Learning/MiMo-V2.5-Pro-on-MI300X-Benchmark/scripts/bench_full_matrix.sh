#!/bin/bash
# bench_full_matrix.sh — Complete H200-aligned benchmark with EP=8
# Run inside VM8 container after Router is ready on port 40000
#
# Covers: Prefill (3 input lengths) + Decode (3 context × multiple BS) + 16K baseline
# Dataset: random (fixed length), aligned to Xiaomi H200 test protocol
#
# Author: Xinyu Wei (Microsoft AI GBB)
set +e

DIR=/data/bench_ep8_router_valid
LOG=$DIR/results.log
mkdir -p "$DIR"
rm -f "$DIR"/*.log

echo "============================================================" | tee "$LOG"
echo "Full Matrix Benchmark — PD + MTP + EP=8"                      | tee -a "$LOG"
echo "Started at $(date -u)"                                        | tee -a "$LOG"
echo "Endpoint: http://127.0.0.1:40000 (PD router)"                 | tee -a "$LOG"
echo "Config: TP=8, EP=8, MORI, MTP/EAGLE layer=3, chunk=16384"     | tee -a "$LOG"
echo "Context: prefill server=786432 (mem=0.75), decode server=262144 (mem=0.85)" | tee -a "$LOG"
echo "Scope: router-valid H200 points; 768K prefill requires a separate long-context decode pass" | tee -a "$LOG"
echo "Spec protocol: SPEC_V2=1, simulate_acc_len=3, draft_tokens=4"  | tee -a "$LOG"
echo "Dataset: random (fixed length)"                                | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

MODEL=/data/models/MiMo-V2.5-Pro
COMMON="--backend sglang --host 127.0.0.1 --model $MODEL --tokenizer $MODEL --dataset-name random --random-range-ratio 1.0 --flush-cache --seed 12345"
BASE_DECODE="$COMMON --port 40000"

run_bench() {
  local LABEL=$1
  local PORT_KIND=$2
  local INPUT=$3
  local OUTPUT=$4
  local BS=$5
  local NPROMPTS=$6
  local OUTFILE="$DIR/${LABEL}.log"
  local BASE="$BASE_DECODE"

  echo "" | tee -a "$LOG"
  echo "--- $LABEL | endpoint=$PORT_KIND in=$INPUT out=$OUTPUT BS=$BS n=$NPROMPTS | $(date -u) ---" | tee -a "$LOG"

  python3 -m sglang.bench_serving $BASE \
    --random-input-len $INPUT \
    --random-output-len $OUTPUT \
    --max-concurrency $BS \
    --num-prompts $NPROMPTS \
    2>&1 | tee "$OUTFILE"

  grep -E "Successful|Failed|Output token throughput|Input token throughput|Median TPOT|Median TTFT" \
    "$OUTFILE" 2>/dev/null | tee -a "$LOG"

  sleep 10
}

# ============================================================
# SCENE 1: Prefill Performance (output=1)
# H200 ref: EP16/DP2 → 31950/27400/17400 tok/s
# ============================================================
echo "" | tee -a "$LOG"
echo "========== SCENE 1: Prefill (output=1) ==========" | tee -a "$LOG"

run_bench "prefill_8k"   router 8192   1  4  30
run_bench "prefill_64k"  router 65536  1  4  30
run_bench "prefill_256k" router 262144 1  4  20
echo "SKIP prefill_768k in this pass: decode server context-length=262144; run a separate long-context pass." | tee -a "$LOG"

# ============================================================
# SCENE 2a: Decode ctx=8192 (H200 ref: TPOT 11.59-27.38ms)
# ============================================================
echo "" | tee -a "$LOG"
echo "========== SCENE 2a: Decode ctx=8K ==========" | tee -a "$LOG"

for BS in 16 32 64 128 192 256; do
  run_bench "decode_ctx8k_bs${BS}" decode 8192 1024 $BS 200
done

# ============================================================
# SCENE 2b: Decode ctx=65536 (H200 ref: TPOT 11.99-19.63ms)
# ============================================================
echo "" | tee -a "$LOG"
echo "========== SCENE 2b: Decode ctx=64K ==========" | tee -a "$LOG"

for BS in 16 32 64 96; do
  run_bench "decode_ctx64k_bs${BS}" decode 65536 1024 $BS 200
done

# ============================================================
# SCENE 2c: Decode ctx=262144 (H200 ref: TPOT 13.93-16.94ms)
# ============================================================
echo "" | tee -a "$LOG"
echo "========== SCENE 2c: Decode ctx=256K ==========" | tee -a "$LOG"

for BS in 16 32; do
  run_bench "decode_ctx256k_bs${BS}" decode 262144 1024 $BS 100
done

# ============================================================
# SCENE 3: Decode 16K/1K baseline (compare with May data)
# ============================================================
echo "" | tee -a "$LOG"
echo "========== SCENE 3: Decode 16K/1K baseline ==========" | tee -a "$LOG"

for BS in 4 8 16 32 48 64; do
  run_bench "decode_16k_bs${BS}" decode 16384 1024 $BS 200
done

# ============================================================
echo "" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
echo "ALL DONE at $(date -u)" | tee -a "$LOG"
echo "Results in $DIR/" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
