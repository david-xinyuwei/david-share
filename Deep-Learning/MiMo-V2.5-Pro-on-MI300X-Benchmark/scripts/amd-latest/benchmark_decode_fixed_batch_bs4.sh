#!/usr/bin/env bash
set -Eeuo pipefail

MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
DATASET_PATH="${DATASET_PATH:?Set DATASET_PATH to the benchmark dataset JSON}"
INPUT_TOKENS="${INPUT_TOKENS:?Set INPUT_TOKENS to 131072 or 196608}"
LOG_DIR="${LOG_DIR:-/data/mimo-fixedbatch/controlled-isl}"
SERVICE_LOG="${SERVICE_LOG:-/data/mimo-fixedbatch/service/decode_outer.log}"

[[ "$INPUT_TOKENS" == 131072 || "$INPUT_TOKENS" == 196608 ]]
mkdir -p "$LOG_DIR"
export PYTHONPATH="/sgl-workspace/sglang_0625/python${PYTHONPATH:+:$PYTHONPATH}"
stem="$LOG_DIR/benchmark_${INPUT_TOKENS}_out1024_bs4"

curl -fsS --max-time 5 http://127.0.0.1:30001/health >/dev/null
grep -Eq 'module_gemm_a8w8_blockscale_bpreshuffle|BpreShuffle' "$SERVICE_LOG"
before_line=$(wc -l < "$SERVICE_LOG")
start_utc=$(date -u +%FT%TZ)
set +e
timeout --signal=TERM --kill-after=30s 3000s \
  python3 -m sglang.bench_serving \
    --backend sglang \
    --model "$MODEL" \
    --host 127.0.0.1 --port 30001 \
    --dataset-name random \
    --random-input-len "$INPUT_TOKENS" \
    --random-output-len 1024 \
    --random-range-ratio 1.0 \
    --dataset-path "$DATASET_PATH" \
    --flush-cache \
    --seed 12345 \
    --num-prompts 4 \
    --warmup-requests 1 \
    --max-concurrency 4 \
    >"${stem}.log" 2>&1
rc=$?
set -e
after_line=$(wc -l < "$SERVICE_LOG")
printf '%s\n' "$rc" > "${stem}.rc"
printf 'start_utc=%s\nend_utc=%s\nbefore_line=%s\nafter_line=%s\n' \
  "$start_utc" "$(date -u +%FT%TZ)" "$before_line" "$after_line" > "${stem}.window"
sed -n "$((before_line + 1)),${after_line}p" "$SERVICE_LOG" > "${stem}.decode.log"

[[ "$rc" == 0 ]]
grep -Eq 'Successful requests:[[:space:]]+4([[:space:]]*)$' "${stem}.log"
grep -Eq "Total input tokens:[[:space:]]+$((INPUT_TOKENS * 4))([[:space:]]*)$" "${stem}.log"
grep -Eq 'Total generated tokens:[[:space:]]+4096([[:space:]]*)$' "${stem}.log"
grep -Eq 'Total generated tokens \(retokenized\):[[:space:]]+[1-9][0-9,]*([[:space:]]*)$' "${stem}.log"
full_batch_samples=$(grep -c 'Decode batch, #running-req: 4' "${stem}.decode.log")
fixed_acceptance_samples=$(grep 'Decode batch, #running-req: 4' "${stem}.decode.log" | grep -c 'accept len: 3\.00, accept rate: 0\.67')
((full_batch_samples >= 2))
[[ "$fixed_acceptance_samples" == "$full_batch_samples" ]]
if grep 'Decode batch, #running-req: 4' "${stem}.decode.log" | grep -Eq '#queue-req: [1-9]'; then
  echo "full-BS4 scheduler sample has a nonzero queue" >&2
  exit 1
fi
! grep -Eqi 'Traceback|ClientPayloadError|No available|TimedOut|out of memory|fatal|Exception:' \
  "${stem}.log" "${stem}.decode.log"

printf 'CONTROLLED_ISL_%s_BS4_PASS\n' "$INPUT_TOKENS"
