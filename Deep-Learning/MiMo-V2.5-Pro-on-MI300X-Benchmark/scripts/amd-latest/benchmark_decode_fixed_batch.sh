#!/bin/bash
# Exact 64K input / 1K output, fixed BS16 Decode benchmark.
#
# Start a fresh service with launch_single_node_decode.sh, wait for health,
# then run this script once with REP=1. Stop the service and repeat from a
# fresh launch with REP=2. The report uses the mean of the two server-side
# steady-state windows; client E2E throughput is not mixed with that metric.
set -euo pipefail

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
DATASET_PATH="${DATASET_PATH:-/data/datasets/ShareGPT_V3_unfiltered_cleaned_split.json}"
LOG_DIR="${LOG_DIR:-/data/mimo-fixedbatch/points}"
SERVICE_LOG="${SERVICE_LOG:-/data/mimo-fixedbatch/service/decode_outer.log}"
REP="${REP:-1}"
EXPECTED_RETOKENIZED_TOKENS="${EXPECTED_RETOKENIZED_TOKENS:-4112}"
STEM="$LOG_DIR/benchmark_65536_out1024_bs16_rep${REP}"
mkdir -p "$LOG_DIR"
export PYTHONPATH="${SGLANG_PYTHONPATH:-/sgl-workspace/sglang_0625/python}${PYTHONPATH:+:$PYTHONPATH}"

[[ "$REP" =~ ^[12]$ ]]
[[ -s "$SERVICE_LOG" ]]
curl -fsS --max-time 5 http://127.0.0.1:30001/health >/dev/null
grep -Eq 'module_gemm_a8w8_blockscale_bpreshuffle|BpreShuffle' "$SERVICE_LOG"

before_line=$(wc -l < "$SERVICE_LOG")
start_utc=$(date -u +%FT%TZ)
rm -f "${STEM}.rc"
set +e
timeout --signal=TERM --kill-after=30s 1200s \
  python3 -m sglang.bench_serving \
    --backend sglang \
    --model "$MODEL" \
    --host 127.0.0.1 --port 30001 \
    --dataset-name random \
    --random-input-len 65536 \
    --random-output-len 1024 \
    --random-range-ratio 1.0 \
    --dataset-path "$DATASET_PATH" \
    --flush-cache \
    --seed 12345 \
    --num-prompts 16 \
    --warmup-requests 1 \
    --max-concurrency 16 \
    2>&1 | tee "${STEM}.log"
rc="${PIPESTATUS[0]}"
set -e
after_line=$(wc -l < "$SERVICE_LOG")

printf '%s\n' "$rc" > "${STEM}.rc"
printf 'start_utc=%s\nend_utc=%s\nbefore_line=%s\nafter_line=%s\n' \
  "$start_utc" "$(date -u +%FT%TZ)" "$before_line" "$after_line" > "${STEM}.window"
sed -n "$((before_line + 1)),${after_line}p" "$SERVICE_LOG" > "${STEM}.decode.log"

[[ "$rc" == 0 ]]
grep -Eq 'Successful requests:[[:space:]]+16([[:space:]]*)$' "${STEM}.log"
grep -Eq 'Total input tokens:[[:space:]]+1048576([[:space:]]*)$' "${STEM}.log"
grep -Eq 'Total generated tokens:[[:space:]]+16384([[:space:]]*)$' "${STEM}.log"
grep -Eq "Total generated tokens \(retokenized\):[[:space:]]+${EXPECTED_RETOKENIZED_TOKENS}([[:space:]]*)$" "${STEM}.log"
grep -Eq 'accept len: 3\.00' "${STEM}.decode.log"
! grep -Eqi 'Traceback|ClientPayloadError|No available|TimedOut|out of memory|fatal|Exception:' \
  "${STEM}.log" "${STEM}.decode.log"

echo "EXACT_64K_1K_BS16_REP${REP}_PASS"
