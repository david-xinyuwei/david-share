#!/bin/bash
# bench_micro_matrix_2x.sh — Two-pass micro matrix for H200-aligned MI300X recovery
#
# Purpose:
#   Run each H200-aligned measurement point twice in isolated, bounded cases.
#   Every case has a timeout; failures are logged and the script continues.
#
# Run inside VM8 container after prefill, decode, and router are ready.
#
# Author: Xinyu Wei (Microsoft AI GBB)
set +e

DIR=/data/bench_ep8_micro_2x
LOG=$DIR/results.log
SUMMARY=$DIR/summary.tsv
MODEL=/data/models/MiMo-V2.5-Pro
BASE="--backend sglang --host 127.0.0.1 --port 40000 --model $MODEL --tokenizer $MODEL --dataset-name random --random-range-ratio 1.0 --flush-cache --seed 12345"

mkdir -p "$DIR"
rm -f "$DIR"/*.log "$DIR"/*.json "$LOG" "$SUMMARY"

printf "case\trep\tinput_len\toutput_len\tbs\tnum_prompts\ttimeout_s\texit_code\tstatus\tsuccess\tinput_tps\toutput_tps\tmedian_ttft_ms\tmedian_tpot_ms\n" > "$SUMMARY"

echo "============================================================" | tee "$LOG"
echo "Two-Pass Micro Matrix — PD + MTP + EP=8"                    | tee -a "$LOG"
echo "Started at $(date -u)"                                      | tee -a "$LOG"
echo "Endpoint: http://127.0.0.1:40000 (PD router)"               | tee -a "$LOG"
echo "Config: TP=8, EP=8, MORI, MTP/EAGLE layer=3, chunk=16384"   | tee -a "$LOG"
echo "Dataset: random, fixed length, seed=12345"                  | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

metric() {
  local file=$1
  local pattern=$2
  grep -E "$pattern" "$file" 2>/dev/null | tail -1 | awk -F: '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' | awk '{print $1}'
}

kill_bench_clients() {
  for pid in $(ps -eo pid=,args= | grep -E '[b]ench_serving|[b]ench_full_matrix|[b]ench_micro_matrix' | awk '{print $1}'); do
    if [[ "$pid" != "$$" ]]; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  sleep 3
  for pid in $(ps -eo pid=,args= | grep -E '[b]ench_serving|[b]ench_full_matrix|[b]ench_micro_matrix' | awk '{print $1}'); do
    if [[ "$pid" != "$$" ]]; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
}

restart_router() {
  echo "[router] restarting at $(date -u)" | tee -a "$LOG"
  for pid in $(ps -eo pid=,args= | grep -E '[s]glang_router.launch_router|[s]glang::router' | awk '{print $1}'); do
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 3
  for pid in $(ps -eo pid=,args= | grep -E '[s]glang_router.launch_router|[s]glang::router' | awk '{print $1}'); do
    kill -KILL "$pid" 2>/dev/null || true
  done
  nohup bash /data/bench_ep8_full/launch_router.sh > /data/bench_ep8_full/router_micro_outer.log 2>&1 &
  for i in $(seq 1 36); do
    if curl -fsS --max-time 5 http://127.0.0.1:40000/v1/models >/dev/null 2>&1; then
      echo "[router] ready attempt=$i" | tee -a "$LOG"
      return 0
    fi
    sleep 5
  done
  echo "[router] not ready after restart" | tee -a "$LOG"
  return 1
}

health_check() {
  curl -fsS --max-time 10 http://127.0.0.1:30000/v1/models >/dev/null 2>&1 || return 1
  curl -fsS --max-time 10 http://172.16.1.122:30001/v1/models >/dev/null 2>&1 || return 1
  curl -fsS --max-time 10 http://127.0.0.1:40000/v1/models >/dev/null 2>&1 || return 1
  return 0
}

flush_cache() {
  curl -sS --max-time 30 -X POST http://127.0.0.1:40000/flush_cache >/dev/null 2>&1 || true
}

run_case() {
  local label=$1
  local rep=$2
  local input_len=$3
  local output_len=$4
  local bs=$5
  local num_prompts=$6
  local timeout_s=$7
  local outfile="$DIR/${label}_rep${rep}.log"
  local status="OK"

  echo "" | tee -a "$LOG"
  echo "--- ${label} rep=${rep} in=${input_len} out=${output_len} bs=${bs} n=${num_prompts} timeout=${timeout_s}s | $(date -u) ---" | tee -a "$LOG"

  if ! health_check; then
    echo "health_check failed; restarting router once" | tee -a "$LOG"
    restart_router
  fi
  flush_cache

  timeout "$timeout_s" python3 -m sglang.bench_serving $BASE \
    --random-input-len "$input_len" \
    --random-output-len "$output_len" \
    --max-concurrency "$bs" \
    --num-prompts "$num_prompts" \
    2>&1 | tee "$outfile"

  local rc=${PIPESTATUS[0]}
  if [[ "$rc" == "124" ]]; then
    status="TIMEOUT"
    kill_bench_clients
    restart_router
  elif grep -qE 'Traceback|Exception|ERROR|ClientPayloadError|TransferEncodingError' "$outfile"; then
    status="ERROR_SEEN"
  fi

  local success input_tps output_tps ttft tpot
  success=$(metric "$outfile" 'Successful requests')
  input_tps=$(metric "$outfile" 'Input token throughput')
  output_tps=$(metric "$outfile" 'Output token throughput')
  ttft=$(metric "$outfile" 'Median TTFT')
  tpot=$(metric "$outfile" 'Median TPOT')

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$label" "$rep" "$input_len" "$output_len" "$bs" "$num_prompts" "$timeout_s" "$rc" "$status" \
    "${success:-}" "${input_tps:-}" "${output_tps:-}" "${ttft:-}" "${tpot:-}" >> "$SUMMARY"

  grep -E 'Successful|Failed|Output token throughput|Input token throughput|Median TPOT|Median TTFT|Traceback|ERROR|Exception|ClientPayloadError|TransferEncodingError' "$outfile" 2>/dev/null | tee -a "$LOG"
  echo "CASE_STATUS: $status exit=$rc" | tee -a "$LOG"
  sleep 20
}

# Repeat every measurement point twice. Use one full batch for decode BS points.
for rep in 1 2; do
  echo "" | tee -a "$LOG"
  echo "==================== REPEAT $rep ====================" | tee -a "$LOG"

  # Prefill points. 256K uses lower concurrency to finish reliably.
  run_case prefill_8k "$rep" 8192 1 4 16 900
  run_case prefill_64k "$rep" 65536 1 4 16 1800
  run_case prefill_256k_lowbs "$rep" 262144 1 1 4 3600

  # Decode ctx=8K H200 BS points.
  for bs in 16 32 64 128 192 256; do
    run_case "decode_ctx8k_bs${bs}" "$rep" 8192 1024 "$bs" "$bs" 1800
  done

  # Decode ctx=64K H200 BS points.
  for bs in 16 32 64 96; do
    run_case "decode_ctx64k_bs${bs}" "$rep" 65536 1024 "$bs" "$bs" 3600
  done

  # Decode ctx=256K H200 BS points, bounded.
  run_case decode_ctx256k_bs16 "$rep" 262144 1024 16 16 5400
  run_case decode_ctx256k_bs32 "$rep" 262144 1024 32 32 7200

done

echo "" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
echo "ALL DONE at $(date -u)" | tee -a "$LOG"
echo "Summary: $SUMMARY" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
