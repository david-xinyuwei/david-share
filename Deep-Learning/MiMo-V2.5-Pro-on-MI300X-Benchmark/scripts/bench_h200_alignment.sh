#!/bin/bash
# bench_h200_alignment.sh — Benchmark aligned to Xiaomi H200 test matrix
#
# Run inside the PREFILL container after Router is ready on port 40000.
#
# Author: Xinyu Wei (Microsoft AI GBB)
set +e

DIR=/data/pd_mtp_final
LOG=$DIR/bench_h200_align.log
mkdir -p "$DIR"

echo "========================================" | tee "$LOG"
echo "PD+MTP H200 Alignment Benchmark" | tee -a "$LOG"
echo "Started at $(date -u)" | tee -a "$LOG"
echo "Router: http://127.0.0.1:40000" | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"

MODEL=/data/models/MiMo-V2.5-Pro
COMMON="--backend sglang --host 127.0.0.1 --port 40000 --model $MODEL --tokenizer $MODEL --random-range-ratio 1.0 --flush-cache --seed 12345 --num-prompts 200"

# ============================================================
# PART 1: Decode — 16K input / 1K output (baseline comparison)
# ============================================================
echo "" | tee -a "$LOG"
echo "=== PART 1: Decode 16K/1K BS sweep ===" | tee -a "$LOG"

for BS in 4 8 16 32 48 64; do
  echo "--- BS=$BS at $(date -u) ---" | tee -a "$LOG"
  python3 -m sglang.bench_serving $COMMON \
    --random-input-len 16384 --random-output-len 1024 \
    --max-concurrency $BS \
    2>&1 | tee "$DIR/decode_16k_1k_bs${BS}.log"
  grep -E "Successful|Output token throughput|Median TPOT|Median TTFT|Failed|accept" \
    "$DIR/decode_16k_1k_bs${BS}.log" 2>/dev/null | tee -a "$LOG"
  sleep 15
done

# ============================================================
# PART 2: Decode — context 8K (H200 customer alignment)
# ============================================================
echo "" | tee -a "$LOG"
echo "=== PART 2: Decode ctx=8192 (H200 alignment) ===" | tee -a "$LOG"

for BS in 16 32 64 128; do
  echo "--- ctx=8192 BS=$BS at $(date -u) ---" | tee -a "$LOG"
  python3 -m sglang.bench_serving $COMMON \
    --random-input-len 8192 --random-output-len 1024 \
    --max-concurrency $BS \
    2>&1 | tee "$DIR/decode_ctx8k_bs${BS}.log"
  grep -E "Successful|Output token throughput|Median TPOT|Median TTFT|Failed|accept" \
    "$DIR/decode_ctx8k_bs${BS}.log" 2>/dev/null | tee -a "$LOG"
  sleep 15
done

# ============================================================
# PART 3: Decode — context 64K (H200 customer alignment)
# ============================================================
echo "" | tee -a "$LOG"
echo "=== PART 3: Decode ctx=65536 (H200 alignment) ===" | tee -a "$LOG"

for BS in 16 32 64 96; do
  echo "--- ctx=65536 BS=$BS at $(date -u) ---" | tee -a "$LOG"
  python3 -m sglang.bench_serving $COMMON \
    --random-input-len 65536 --random-output-len 1024 \
    --max-concurrency $BS \
    2>&1 | tee "$DIR/decode_ctx64k_bs${BS}.log"
  grep -E "Successful|Output token throughput|Median TPOT|Median TTFT|Failed|accept" \
    "$DIR/decode_ctx64k_bs${BS}.log" 2>/dev/null | tee -a "$LOG"
  sleep 15
done

# ============================================================
# PART 4: Prefill — output=1 (H200 customer alignment)
# ============================================================
echo "" | tee -a "$LOG"
echo "=== PART 4: Prefill (output=1, H200 alignment) ===" | tee -a "$LOG"

for INPUT in 8192 65536 262144; do
  echo "--- prefill input=$INPUT at $(date -u) ---" | tee -a "$LOG"
  python3 -m sglang.bench_serving $COMMON \
    --random-input-len $INPUT --random-output-len 1 \
    --num-prompts 30 --max-concurrency 4 \
    2>&1 | tee "$DIR/prefill_in${INPUT}_out1.log"
  grep -E "Successful|Input token throughput|Output token throughput|Median TTFT|Failed" \
    "$DIR/prefill_in${INPUT}_out1.log" 2>/dev/null | tee -a "$LOG"
  sleep 15
done

echo "" | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"
echo "ALL DONE at $(date -u)" | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"
