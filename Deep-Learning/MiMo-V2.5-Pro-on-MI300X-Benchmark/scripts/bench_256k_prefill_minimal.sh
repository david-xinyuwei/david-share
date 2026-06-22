#!/usr/bin/env bash
set +euo pipefail

RUN_ID="${RUN_ID:-$(date -u +%Y%m%d_%H%M%S)}"
DIR="${DIR:-/data/bench_256k_prefill_minimal_${RUN_ID}}"
MODEL="${MODEL:-/data/models/MiMo-V2.5-Pro}"
SUMMARY="$DIR/summary.tsv"
RESULTS="$DIR/results.log"
STALE_SECONDS="${STALE_SECONDS:-300}"
ROUTER_HOST="${ROUTER_HOST:-127.0.0.1}"
ROUTER_PORT="${ROUTER_PORT:-40000}"
ROUTER_BASE_URL="${ROUTER_BASE_URL:-http://${ROUTER_HOST}:${ROUTER_PORT}}"
PREFILL_BASE_URL="${PREFILL_BASE_URL:-http://127.0.0.1:30000}"
DECODE_BASE_URL="${DECODE_BASE_URL:-}"
BASE=(--backend sglang --host "$ROUTER_HOST" --port "$ROUTER_PORT" --model "$MODEL" --tokenizer "$MODEL" --dataset-name random --random-range-ratio 1.0 --flush-cache --seed 12345)

mkdir -p "$DIR"
printf "case\tinput_len\toutput_len\tbs\tnum_prompts\tstream\ttimeout_s\tstale_s\texit_code\tstatus\tsuccess\tinput_tps\toutput_tps\tmedian_ttft_ms\tmedian_tpot_ms\n" > "$SUMMARY"

log() {
  printf '%s\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$RESULTS"
}

metric() {
  local file=$1 pattern=$2
  grep -E "$pattern" "$file" 2>/dev/null | tail -1 | awk -F: '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' | awk '{print $1}'
}

file_age_seconds() {
  local file=$1
  if [[ ! -e "$file" ]]; then echo 999999; return; fi
  echo $(($(date +%s) - $(stat -c %Y "$file")))
}

gpu_busy_max() {
  if command -v rocm-smi >/dev/null 2>&1; then
    rocm-smi --showuse 2>/dev/null | awk -F': ' '/GPU use \(%\)/ {gsub(/[^0-9.]/,"",$2); if ($2+0>max) max=$2+0} END {printf "%.0f", max+0}'
  elif command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | awk '{if ($1+0>max) max=$1+0} END {printf "%.0f", max+0}'
  else
    echo 0
  fi
}

health_check() {
  curl -fsS --max-time 10 "$PREFILL_BASE_URL/v1/models" >/dev/null 2>&1 || return 1
  if [[ -n "$DECODE_BASE_URL" ]]; then
    curl -fsS --max-time 10 "$DECODE_BASE_URL/v1/models" >/dev/null 2>&1 || return 1
  else
    log "decode_health_skipped set_DECODE_BASE_URL_to_enable"
  fi
  curl -fsS --max-time 10 "$ROUTER_BASE_URL/v1/models" >/dev/null 2>&1 || return 1
  return 0
}

flush_cache() {
  curl -sS --max-time 30 -X POST "$ROUTER_BASE_URL/flush_cache" >/dev/null 2>&1 || true
}

restart_router() {
  log "router_restart_start"
  for pid in $(ps -eo pid=,args= | awk '/[s]glang_router.launch_router|[s]glang::router/ {print $1}'); do
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 3
  for pid in $(ps -eo pid=,args= | awk '/[s]glang_router.launch_router|[s]glang::router/ {print $1}'); do
    kill -KILL "$pid" 2>/dev/null || true
  done
  nohup bash /data/bench_ep8_full/launch_router.sh > "$DIR/router_restart_$(date -u +%H%M%S).log" 2>&1 </dev/null &
  for i in $(seq 1 48); do
    if curl -fsS --max-time 5 "$ROUTER_BASE_URL/v1/models" >/dev/null 2>&1; then
      log "router_restart_ready attempt=$i"
      return 0
    fi
    sleep 5
  done
  log "router_restart_failed"
  return 1
}

kill_pid_tree() {
  local pid=$1
  kill -TERM "$pid" 2>/dev/null || true
  sleep 5
  kill -KILL "$pid" 2>/dev/null || true
}

run_case() {
  local label=$1 input_len=$2 output_len=$3 bs=$4 num_prompts=$5 stream_mode=$6 timeout_s=$7 stale_s=$8
  shift 8
  local outfile="$DIR/${label}.log"
  local status="OK" rc=0

  log "CASE_START label=$label input=$input_len output=$output_len bs=$bs n=$num_prompts stream=$stream_mode timeout=$timeout_s stale=$stale_s"
  health_check || { log "health_check_failed_before_${label}"; restart_router; }
  flush_cache

  python3 -m sglang.bench_serving "${BASE[@]}" \
    --random-input-len "$input_len" \
    --random-output-len "$output_len" \
    --max-concurrency "$bs" \
    --num-prompts "$num_prompts" \
    "$@" > "$outfile" 2>&1 &
  local pid=$!
  local started=$(date +%s)

  while kill -0 "$pid" 2>/dev/null; do
    sleep 10
    local elapsed=$(($(date +%s) - started))
    local age=$(file_age_seconds "$outfile")
    local gpu=$(gpu_busy_max)
    if (( elapsed >= timeout_s )); then
      status="TIMEOUT_KILLED"
      log "CASE_TIMEOUT label=$label elapsed=${elapsed}s age=${age}s gpu=${gpu}%"
      kill_pid_tree "$pid"
      break
    fi
    if (( age >= stale_s )) && (( gpu <= 5 )); then
      status="STALE_KILLED"
      log "CASE_STALE label=$label elapsed=${elapsed}s age=${age}s gpu=${gpu}%"
      kill_pid_tree "$pid"
      break
    fi
  done

  wait "$pid" 2>/dev/null
  rc=$?
  if [[ "$status" == "OK" && "$rc" != "0" ]]; then
    status="EXIT_${rc}"
  fi
  if grep -qE 'Traceback|Exception|ERROR|Fatal|aborted|core dumped|ClientPayloadError|TransferEncodingError' "$outfile" 2>/dev/null; then
    status="${status}_ERROR_SEEN"
  fi

  local success input_tps output_tps ttft tpot
  success=$(metric "$outfile" 'Successful requests')
  input_tps=$(metric "$outfile" 'Input token throughput')
  output_tps=$(metric "$outfile" 'Output token throughput')
  ttft=$(metric "$outfile" 'Median TTFT')
  tpot=$(metric "$outfile" 'Median TPOT')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$label" "$input_len" "$output_len" "$bs" "$num_prompts" "$stream_mode" "$timeout_s" "$stale_s" "$rc" "$status" \
    "${success:-}" "${input_tps:-}" "${output_tps:-}" "${ttft:-}" "${tpot:-}" >> "$SUMMARY"
  log "CASE_DONE label=$label rc=$rc status=$status success=${success:-NA} input_tps=${input_tps:-NA} output_tps=${output_tps:-NA} ttft=${ttft:-NA} tpot=${tpot:-NA}"
  sleep 10
}

log "DIAG_START dir=$DIR"
decode_health="skipped"
if [[ -n "$DECODE_BASE_URL" ]]; then
  decode_health=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$DECODE_BASE_URL/health")
fi
log "SERVICE_HEALTH router=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$ROUTER_BASE_URL/health") prefill=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$PREFILL_BASE_URL/health") decode=$decode_health"

run_case prefill_256k_n1_stream 262144 1 1 1 stream 600 "$STALE_SECONDS"
run_case prefill_256k_n4_nostream_seq 262144 1 1 4 no-stream 1200 "$STALE_SECONDS" --disable-stream

for i in 1 2 3 4; do
  restart_router
  run_case "prefill_256k_isolated_restart_${i}" 262144 1 1 1 stream 600 "$STALE_SECONDS"
done

log "DIAG_DONE summary=$SUMMARY"
cat "$SUMMARY"
