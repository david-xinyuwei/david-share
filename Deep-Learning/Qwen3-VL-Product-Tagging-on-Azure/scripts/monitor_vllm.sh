#!/usr/bin/env bash
set -euo pipefail

REFRESH_SECONDS=10
MODE="loop"
WORK_DIR="${WORK_DIR:-$(pwd)}"
CONTAINER_NAME="vlm-vllm-bf16"
ENDPOINT="http://localhost:8000"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --once)
      MODE="once"
      shift
      ;;
    --refresh)
      REFRESH_SECONDS="$2"
      shift 2
      ;;
    --container)
      CONTAINER_NAME="$2"
      shift 2
      ;;
    --endpoint)
      ENDPOINT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

print_section() {
  echo
  echo "--- $1 ---"
}

print_once() {
  if [[ "$MODE" != "once" ]]; then
    printf '\033[2J\033[H'
  fi
  echo "========== VLM VLM Monitor $(date -u '+%Y-%m-%d %H:%M:%S UTC') =========="

  print_section "VM"
  hostname
  uptime

  print_section "GPU (Real-time)"
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit --format=csv || true
    echo
    # Compact one-liner for quick glance
    local gpu_util mem_used mem_total mem_pct
    gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo '?')
    mem_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo '?')
    mem_total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null || echo '?')
    if [[ "$mem_total" != "?" && "$mem_total" -gt 0 ]] 2>/dev/null; then
      mem_pct=$((mem_used * 100 / mem_total))
    else
      mem_pct='?'
    fi
    echo ">>> GPU Util: ${gpu_util}%  |  VRAM: ${mem_used}/${mem_total} MiB (${mem_pct}%)  <<<"
  else
    echo "nvidia-smi not found"
  fi

  print_section "vLLM Container"
  docker ps -a --filter "name=${CONTAINER_NAME}" --format 'name={{.Names}} status={{.Status}} image={{.Image}}' || true

  print_section "Endpoint"
  local model_status
  model_status=$(curl -s --max-time 5 "${ENDPOINT}/v1/models" 2>/dev/null | python3 -c 'import json,sys
try:
    data=json.load(sys.stdin)
    first=data.get("data", [{}])[0]
    print("OK model={} max_model_len={}".format(first.get("id"), first.get("max_model_len")))
except Exception as exc:
    print(f"NOT_READY {exc}")
' || true)
  echo "${model_status:-NOT_READY}"

  print_section "Recent vLLM Throughput"
  docker logs --tail 80 "${CONTAINER_NAME}" 2>&1 | grep -E 'Avg prompt throughput|HTTP/1.1|ERROR|Traceback' | tail -12 || true

  print_section "Benchmark Process"
  ps -ef | grep -E 'run_openai_vlm_bench|benchmark|vllm_bf16|vllm_fp8' | grep -v grep || echo "no active benchmark process"

  print_section "Latest Benchmark Artifacts"
  find "${WORK_DIR}/reports_engine_benchmark" -maxdepth 1 -type f \
    \( -name '*.json' -o -name '*.log' \) \
    -printf '%TY-%Tm-%Td %TH:%TM %9s %p\n' 2>/dev/null | sort | tail -8 || true

  print_section "Latest Benchmark Summary"
  local latest_json
  latest_json=$(ls -t "${WORK_DIR}"/reports_engine_benchmark/*.json 2>/dev/null | head -1 || true)
  if [[ -n "${latest_json}" ]]; then
    python3 - "${latest_json}" <<'PY'
import json
import sys

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
print(f"file={path}")
print(f"label={data.get('label')}")
for run in data.get("runs", []):
    summary = run.get("summary", {})
    print(
        "concurrency={concurrency} success={success}/{requests} errors={errors} "
        "p50_ms={p50:.2f} p90_ms={p90:.2f} rps={rps:.3f} out_tok_s={out_tok_s:.3f}".format(
            concurrency=run.get("concurrency"),
            success=summary.get("success", 0),
            requests=summary.get("requests", 0),
            errors=summary.get("errors", 0),
            p50=summary.get("latency_ms_p50") or 0,
            p90=summary.get("latency_ms_p90") or 0,
            rps=summary.get("request_throughput_rps") or 0,
            out_tok_s=summary.get("completion_tokens_per_s") or 0,
        )
    )
PY
  else
    echo "no benchmark JSON yet"
  fi

  print_section "Disk"
  df -h / "${WORK_DIR}" 2>/dev/null || df -h /

  echo
  echo "Refresh=${REFRESH_SECONDS}s  Mode=${MODE}  Container=${CONTAINER_NAME}"
  echo "============================================================"
}

if [[ "${MODE}" == "once" ]]; then
  print_once
else
  while true; do
    print_once
    sleep "${REFRESH_SECONDS}"
  done
fi