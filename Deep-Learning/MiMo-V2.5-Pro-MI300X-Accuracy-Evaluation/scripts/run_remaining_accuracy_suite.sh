#!/bin/bash
set -Eeuo pipefail

ROLE="${1:?Usage: run_remaining_accuracy_suite.sh vm8|vm10}"
BASE_DIR="${BASE_DIR:?Set BASE_DIR to the private evaluation workspace}"
CONTROL_DIR="$BASE_DIR/control"
LOG_DIR="$BASE_DIR/mini-eval/logs"
STATE_DIR="$BASE_DIR/remaining-full/$ROLE"
CONTRACT="$BASE_DIR/remaining-work-contract-20260723.json"
stage="initialization"

case "$ROLE" in
  vm8)
    API_BASE="${VM8_API_BASE:?Set VM8_API_BASE}"
    HEALTH_URL="${VM8_HEALTH_URL:?Set VM8_HEALTH_URL}"
    EXPECTED_REMAINING=35336
    ;;
  vm10)
    API_BASE="${VM10_API_BASE:?Set VM10_API_BASE}"
    HEALTH_URL="${VM10_HEALTH_URL:?Set VM10_HEALTH_URL}"
    EXPECTED_REMAINING=91079
    ;;
  *) exit 2 ;;
esac

mkdir -p "$STATE_DIR"
exec 9> "$STATE_DIR/suite.lock"
flock -n 9 || { printf 'REMAINING_SUITE_ALREADY_RUNNING role=%s\n' "$ROLE"; exit 3; }

on_error() {
  local code=$?
  trap - ERR
  printf 'failed_at_utc=%s\nstage=%s\nexit_code=%s\n' \
    "$(date -u +%FT%TZ)" "$stage" "$code" > "$STATE_DIR/failure.tmp"
  mv "$STATE_DIR/failure.tmp" "$STATE_DIR/failure"
  exit "$code"
}
trap on_error ERR

test -s "$CONTRACT"
python3 - "$CONTRACT" "$EXPECTED_REMAINING" "$ROLE" <<'PY'
import json
import sys

contract = json.load(open(sys.argv[1], encoding="utf-8"))
expected = int(sys.argv[2])
role = sys.argv[3]
tasks = {
    "vm8": ("aime", "mmlu_pro", "minerva_math"),
    "vm10": ("cmmlu", "mmlu_redux", "supergpqa"),
}[role]
actual = sum(contract["remaining"]["datasets"][task]["remaining_responses"] for task in tasks)
assert actual == expected, (actual, expected)
assert contract["invariants"]["completed_plus_remaining_responses"] == 134239
PY

run_chunk_attempt() {
  local task="$1" label="$2" concurrency="$3" max_samples="$4" offset="$5"
  local repeats="$6" shard_index="$7" shard_count="$8" repeat_offset="$9"
  local before_file after_file env_name env_file prefix attempt_code
  before_file="$STATE_DIR/.${task}-${label}.before"
  after_file="$STATE_DIR/.${task}-${label}.after"
  find "$LOG_DIR" -maxdepth 1 -type f -name "${task}-${label}-*.env" \
    -printf '%f\n' | sort > "$before_file"
  curl -fsS --connect-timeout 3 --max-time 20 "$HEALTH_URL" >/dev/null
  if RUN_LABEL="$label" LOCAL_API_BASE="$API_BASE" \
    MAX_CONCURRENT_REQUESTS="$concurrency" MAX_SAMPLES="$max_samples" \
    SAMPLE_OFFSET="$offset" REPEATS="$repeats" REPEAT_OFFSET="$repeat_offset" \
    SHARD_INDEX="$shard_index" SHARD_COUNT="$shard_count" \
      bash "$CONTROL_DIR/run_mini_eval_smoke.sh" "$task"; then
    attempt_code=0
  else
    attempt_code=$?
  fi
  find "$LOG_DIR" -maxdepth 1 -type f -name "${task}-${label}-*.env" \
    -printf '%f\n' | sort > "$after_file"
  mapfile -t new_envs < <(comm -13 "$before_file" "$after_file")
  rm -f "$before_file" "$after_file"
  if [ "${#new_envs[@]}" -ne 1 ]; then
    CHUNK_PREFIX=""
    return 1
  fi
  env_name="${new_envs[0]}"
  env_file="$LOG_DIR/$env_name"
  prefix="${env_file%.env}"
  CHUNK_PREFIX="$prefix"
  [ "$attempt_code" -eq 0 ] || return "$attempt_code"
  grep -qx status=passed "$prefix.outcome"
  test -s "$prefix.evidence.sha256"
  (cd "$LOG_DIR" && sha256sum -c "$(basename "$prefix.evidence.sha256")" >/dev/null)
}

write_chunk_marker() {
  local marker="$1" prefix="$2" concurrency="$3" logical_repeats="$4"
  mkdir -p "${marker%/*}"
  {
    printf 'prefix=%s\n' "$prefix"
    printf 'concurrency=%s\n' "$concurrency"
    printf 'logical_repeats=%s\n' "$logical_repeats"
    printf 'runtime_topology=independent_unified_tp8_dp1_ep1\n'
    printf 'completed_at_utc=%s\n' "$(date -u +%FT%TZ)"
  } > "$marker.tmp"
  mv "$marker.tmp" "$marker"
}

run_chunk() {
  local task="$1" label="$2" concurrency="$3" max_samples="$4" offset="$5"
  local repeats="$6" shard_index="$7" shard_count="$8" marker="$9"
  local fallback="${10}" logical_repeats="${11}" repeat_offset="${12}"
  local primary_failure="${marker%.done}.primary-failed"
  [ -s "$marker" ] && return
  if [ ! -s "$primary_failure" ]; then
    if run_chunk_attempt "$task" "${label}_c${concurrency}" "$concurrency" \
      "$max_samples" "$offset" "$repeats" "$shard_index" "$shard_count" \
      "$repeat_offset"; then
      write_chunk_marker "$marker" "$CHUNK_PREFIX" "$concurrency" "$logical_repeats"
      return
    fi
    printf 'failed_at_utc=%s\nprefix=%s\nconcurrency=%s\n' \
      "$(date -u +%FT%TZ)" "${CHUNK_PREFIX:-unknown}" "$concurrency" \
      > "$primary_failure.tmp"
    mv "$primary_failure.tmp" "$primary_failure"
  fi
  curl -fsS --connect-timeout 3 --max-time 20 "$HEALTH_URL" >/dev/null
  if run_chunk_attempt "$task" "${label}_fallback_c${fallback}" "$fallback" \
    "$max_samples" "$offset" "$repeats" "$shard_index" "$shard_count" \
    "$repeat_offset"; then
    write_chunk_marker "$marker" "$CHUNK_PREFIX" "$fallback" "$logical_repeats"
    return
  fi
  return 1
}

run_aime_remaining() {
  local task_dir="$STATE_DIR/aime" repeat offset count marker label
  mkdir -p "$task_dir/chunks"
  for repeat in $(seq 0 31); do
    if [ "$repeat" -eq 0 ]; then
      offset=16
      count=44
    else
      offset=0
      count=60
    fi
    stage="aime_repeat_${repeat}_offset_${offset}"
    printf '%s\n' "$stage" > "$STATE_DIR/current-stage.tmp"
    mv "$STATE_DIR/current-stage.tmp" "$STATE_DIR/current-stage"
    marker="$task_dir/chunks/repeat-$(printf '%02d' "$repeat").done"
    label="remaining_aime_r$(printf '%02d' "$repeat")_o$(printf '%05d' "$offset")"
    run_chunk aime "$label" 4 "$count" "$offset" 32 "$repeat" 32 \
      "$marker" 1 "$repeat" 0
  done
  date -u +%FT%TZ > "$task_dir/task.done.tmp"
  mv "$task_dir/task.done.tmp" "$task_dir/task.done"
}

run_sample_range() {
  local task="$1" start="$2" stop="$3" repeats="$4" chunk_size="$5"
  local concurrency="$6" fallback="$7" logical_repeats="$8" repeat_offset="$9"
  local task_dir="$STATE_DIR/$task" offset count marker label
  mkdir -p "$task_dir/chunks"
  for ((offset=start; offset<stop; offset+=chunk_size)); do
    count="$chunk_size"
    ((offset + count <= stop)) || count=$((stop-offset))
    stage="${task}_offset_${offset}_repeats_${logical_repeats}"
    printf '%s\n' "$stage" > "$STATE_DIR/current-stage.tmp"
    mv "$STATE_DIR/current-stage.tmp" "$STATE_DIR/current-stage"
    marker="$task_dir/chunks/o$(printf '%05d' "$offset")_n$(printf '%05d' "$count")_lr${logical_repeats//-/_}.done"
    label="remaining_${task}_o$(printf '%05d' "$offset")_n$(printf '%05d' "$count")_lr${logical_repeats//-/_}"
    run_chunk "$task" "$label" "$concurrency" "$count" "$offset" \
      "$repeats" 0 1 "$marker" "$fallback" "$logical_repeats" "$repeat_offset"
  done
}

rm -f "$STATE_DIR/failure"
cp "$CONTRACT" "$STATE_DIR/contract.json"
printf 'started_at_utc=%s\nrole=%s\ntopology=independent_unified_tp8_dp1_ep1\nexpected_remaining_responses=%s\n' \
  "$(date -u +%FT%TZ)" "$ROLE" "$EXPECTED_REMAINING" > "$STATE_DIR/suite.env.tmp"
mv "$STATE_DIR/suite.env.tmp" "$STATE_DIR/suite.env"

if [ "$ROLE" = vm8 ]; then
  run_aime_remaining
  run_sample_range mmlu_pro 512 12032 2 256 16 4 0-1 0
  date -u +%FT%TZ > "$STATE_DIR/mmlu_pro/task.done.tmp"
  mv "$STATE_DIR/mmlu_pro/task.done.tmp" "$STATE_DIR/mmlu_pro/task.done"
  run_sample_range minerva_math 1536 5000 3 128 16 4 0-2 0
  date -u +%FT%TZ > "$STATE_DIR/minerva_math/task.done.tmp"
  mv "$STATE_DIR/minerva_math/task.done.tmp" "$STATE_DIR/minerva_math/task.done"
else
  run_sample_range cmmlu 0 128 2 128 8 4 1-2 1
  run_sample_range cmmlu 128 11582 3 256 8 4 0-2 0
  date -u +%FT%TZ > "$STATE_DIR/cmmlu/task.done.tmp"
  mv "$STATE_DIR/cmmlu/task.done.tmp" "$STATE_DIR/cmmlu/task.done"
  run_sample_range mmlu_redux 0 512 3 128 16 4 3-5 3
  run_sample_range mmlu_redux 512 5330 6 128 16 4 0-5 0
  date -u +%FT%TZ > "$STATE_DIR/mmlu_redux/task.done.tmp"
  mv "$STATE_DIR/mmlu_redux/task.done.tmp" "$STATE_DIR/mmlu_redux/task.done"
  run_sample_range supergpqa 512 26529 1 128 4 1 0 0
  date -u +%FT%TZ > "$STATE_DIR/supergpqa/task.done.tmp"
  mv "$STATE_DIR/supergpqa/task.done.tmp" "$STATE_DIR/supergpqa/task.done"
fi

rm -f "$STATE_DIR/current-stage"
date -u +%FT%TZ > "$STATE_DIR/suite.done.tmp"
mv "$STATE_DIR/suite.done.tmp" "$STATE_DIR/suite.done"
printf 'REMAINING_ACCURACY_SUITE=PASS role=%s\n' "$ROLE"