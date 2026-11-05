#!/bin/bash
set -Eeuo pipefail

RUN_ROOT="${RUN_ROOT:?set RUN_ROOT to the frozen run directory}"
LAYOUT="${LAYOUT:?set LAYOUT to tp, pp, tep, dp, or pd}"
CONTAINER_NAME="${CONTAINER_NAME:?set the running container name}"
PYTHON="${PYTHON:-/usr/bin/python3}"
SERVED_MODEL="${SERVED_MODEL:-muse-spark-open-bf16}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
HEALTH_URL="${HEALTH_URL:-$BASE_URL/health}"
READY_PATTERN="${READY_PATTERN:-Application startup complete}"
MODEL_CONTAINER_NAME="${MODEL_CONTAINER_NAME:-$CONTAINER_NAME}"
CONCURRENCIES="${CONCURRENCIES:-1,8,32}"
ROUNDS="${ROUNDS:-3}"
SHORT_MAX_TOKENS="${SHORT_MAX_TOKENS:-256}"
GUIDE_MAX_TOKENS="${GUIDE_MAX_TOKENS:-1024}"
RESUME="${RESUME:-0}"
measurement_status=PASS
OUT="$RUN_ROOT/$LAYOUT"
mkdir -p "$OUT"

write_status() {
  "$PYTHON" - "$OUT/status.json" "$LAYOUT" "$1" "$2" <<'PY'
import datetime
import json
import os
import sys

path, layout, status, phase = sys.argv[1:]
record = {
    "layout": layout,
    "status": status,
    "phase": phase,
    "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
temporary = path + ".tmp"
with open(temporary, "w", encoding="utf-8") as output:
    json.dump(record, output, indent=2)
os.replace(temporary, path)
print(json.dumps(record), flush=True)
PY
}

capture_metrics() {
  local stage="$1"
  local name url exit_code status
  for name in metrics prefill-metrics; do
    url="${METRICS_URL:-$BASE_URL/metrics}"
    if [ "$name" = prefill-metrics ]; then url="${PREFILL_METRICS_URL:-}"; fi
    if [ -z "$url" ]; then continue; fi
    exit_code=0
    curl --fail --silent --show-error --max-time 15 "$url" > "$OUT/$name-$stage.txt" 2> "$OUT/$name-$stage-error.txt" || exit_code=$?
    status=AVAILABLE
    if [ "$exit_code" != 0 ] || [ ! -s "$OUT/$name-$stage.txt" ]; then status=MISSING; fi
    printf '{"status":"%s","curl_exit":%s}\n' "$status" "$exit_code" > "$OUT/$name-$stage-status.json"
    if [ "$status" = MISSING ]; then
      if [ "$stage" != after ]; then return 1; fi
      measurement_status=COMPLETE_WITH_ERRORS
    fi
  done
}

run_probe() {
  local report_path="$1"
  shift
  local exit_code=0
  if [ "$RESUME" != 0 ] && [ -s "$report_path" ]; then
    exit_code=$("$PYTHON" -c 'import json, sys; print(0 if json.load(open(sys.argv[1]))["status"] == "PASS" else 1)' "$report_path")
  else
    test ! -e "$report_path"
    "$PYTHON" "$RUN_ROOT/source/09_perf_probe.py" "$SERVED_MODEL" "$report_path" \
      --base "$BASE_URL" --conc "$CONCURRENCIES" --rounds "$ROUNDS" "$@" || exit_code=$?
  fi
  "$PYTHON" - "$report_path" "$CONCURRENCIES" "$ROUNDS" "$exit_code" <<'PY'
import json
import sys

path, concurrencies, rounds, exit_code = sys.argv[1:]
with open(path, encoding="utf-8") as source:
    report = json.load(source)
expected_levels = [int(value) for value in concurrencies.split(",")]
assert int(exit_code) in (0, 1), "Probe process failed before a complete sweep."
assert report["status"] in ("PASS", "FAILED")
assert (report["status"] == "PASS") == (int(exit_code) == 0)
assert [level["concurrency"] for level in report["levels"]] == expected_levels
assert report["rounds"] == int(rounds)
for level in report["levels"]:
    assert len(level["rounds"]) == int(rounds)
    assert all(len(batch["requests"]) == level["concurrency"] for batch in level["rounds"])
print(json.dumps({"sweep": "COMPLETE", "inference_status": report["status"], "file": path}), flush=True)
PY
  if [ "$exit_code" = 1 ]; then measurement_status=COMPLETE_WITH_ERRORS; fi
}

trap 'exit_code=$?; write_status FAILED "$phase"; printf "MEASURE_FAILED phase=%s exit=%s\n" "$phase" "$exit_code"; exit "$exit_code"' ERR
phase=readiness
if [ "$RESUME" = evidence ]; then
  current_launch=$(docker inspect --format '{{.Id}} {{.Image}} {{json .Config.Cmd}}' "$MODEL_CONTAINER_NAME")
  test "$(cat "$OUT/launch.txt")" = "$current_launch"
  test -s "$OUT/perf-short.json"
  test -s "$OUT/perf-guide.json"
else
write_status IN_PROGRESS "$phase"
timeout 1800 "$PYTHON" - "$CONTAINER_NAME" "$READY_PATTERN" <<'PY'
import subprocess
import sys

follower = subprocess.Popen(
  ["docker", "logs", "--follow", sys.argv[1]],
  stdout=subprocess.PIPE,
  stderr=subprocess.STDOUT,
  text=True,
  encoding="utf-8",
  errors="replace",
)
try:
  for line in follower.stdout:
    if sys.argv[2] in line:
      print(line.strip(), flush=True)
      break
  else:
    raise RuntimeError("Server log ended before application startup completed.")
finally:
  follower.terminate()
  try:
    follower.wait(timeout=10)
  except subprocess.TimeoutExpired:
    follower.kill()
    follower.wait()
PY
curl --fail --silent --show-error --max-time 15 --retry 120 --retry-delay 1 --retry-connrefused --retry-max-time 1800 "$HEALTH_URL"
current_launch=$(docker inspect --format '{{.Id}} {{.Image}} {{json .Config.Cmd}}' "$MODEL_CONTAINER_NAME")
if [ "$RESUME" = 1 ]; then
  test "$(cat "$OUT/launch.txt")" = "$current_launch"
else
  test ! -e "$OUT/launch.txt"
  printf '%s\n' "$current_launch" > "$OUT/launch.txt"
  if [ "$MODEL_CONTAINER_NAME" != "$CONTAINER_NAME" ]; then
    docker inspect --format '{{.Id}} {{.Image}} {{json .Config.Cmd}}' "$CONTAINER_NAME" > "$OUT/proxy-launch.txt"
  fi
  rocm-smi --showmeminfo vram --json > "$OUT/gpu-before.json"
fi

phase=metrics_before
write_status IN_PROGRESS "$phase"
if [ "$RESUME" != 1 ]; then capture_metrics before; fi

phase=smoke
write_status IN_PROGRESS "$phase"
if [ "$RESUME" != 1 ]; then
  curl --fail-with-body --silent --show-error --max-time 900 \
    -H 'Content-Type: application/json' \
    --data-binary "@$RUN_ROOT/smoke_request.json" \
    -o "$OUT/smoke-response.json" \
    -w '%{http_code} %{time_total}\n' \
    "$BASE_URL/v1/chat/completions" > "$OUT/smoke-timing.txt"
fi
"$PYTHON" - "$OUT/smoke-response.json" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    response = json.load(source)
choice = response["choices"][0]
content = choice["message"].get("content") or ""
assert choice["finish_reason"] == "stop", "Smoke did not finish naturally."
assert content.strip(), "Smoke has no final answer."
assert all(re.search(r"\b" + str(bits) + r"\b", content) for bits in (8, 7, 5, 10)), "Smoke omitted expected bit counts; inspect the answer."
print(json.dumps({"smoke": "PASS", "finish_reason": choice["finish_reason"], "content": content, "usage": response.get("usage")}), flush=True)
PY

phase=metrics_smoke
write_status IN_PROGRESS "$phase"
if [ "$RESUME" != 1 ]; then capture_metrics smoke; fi
fi

phase=short_input
write_status IN_PROGRESS "$phase"
run_probe "$OUT/perf-short.json" --max-tokens "$SHORT_MAX_TOKENS"

phase=guide_input
write_status IN_PROGRESS "$phase"
run_probe "$OUT/perf-guide.json" --max-tokens "$GUIDE_MAX_TOKENS" \
  --prompt-file "$RUN_ROOT/guide_prompt.txt"

phase=evidence
write_status IN_PROGRESS "$phase"
if [ ! -s "$OUT/gpu-after.json" ]; then
  rocm-smi --showmeminfo vram --json > "$OUT/gpu-after.json"
fi
capture_metrics after
docker logs "$MODEL_CONTAINER_NAME" > "$OUT/server.log" 2>&1
if [ "$MODEL_CONTAINER_NAME" != "$CONTAINER_NAME" ]; then
  docker logs "$CONTAINER_NAME" > "$OUT/proxy.log" 2>&1
fi
sha256sum "$RUN_ROOT/source/09_perf_probe.py" "$RUN_ROOT/guide_prompt.txt" \
  "$RUN_ROOT/smoke_request.json" "$OUT/launch.txt" "$OUT/smoke-response.json" \
  "$OUT/smoke-timing.txt" "$OUT/perf-short.json" "$OUT/perf-guide.json" \
  "$OUT/gpu-before.json" "$OUT/gpu-after.json" "$OUT/server.log" \
  "${BASH_SOURCE[0]}" "$OUT/metrics-before.txt" "$OUT/metrics-smoke.txt" \
  "$OUT/metrics-after.txt" > "$OUT/SHA256SUMS"
if [ -n "${PREFILL_METRICS_URL:-}" ]; then
  sha256sum "$OUT/prefill-metrics-before.txt" "$OUT/prefill-metrics-smoke.txt" \
    "$OUT/prefill-metrics-after.txt" >> "$OUT/SHA256SUMS"
fi
if [ "$MODEL_CONTAINER_NAME" != "$CONTAINER_NAME" ]; then
  sha256sum "$OUT/proxy-launch.txt" "$OUT/proxy.log" >> "$OUT/SHA256SUMS"
fi
for metrics_status in "$OUT"/*-status.json; do
  if [ -f "$metrics_status" ]; then sha256sum "$metrics_status" >> "$OUT/SHA256SUMS"; fi
done
for metrics_error in "$OUT"/*-error.txt; do
  if [ -f "$metrics_error" ]; then sha256sum "$metrics_error" >> "$OUT/SHA256SUMS"; fi
done
write_status "$measurement_status" complete