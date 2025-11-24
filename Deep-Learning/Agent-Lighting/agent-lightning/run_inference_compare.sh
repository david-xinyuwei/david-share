#!/usr/bin/env bash
# End-to-end helper script for comparing base and trained models via inference_compare.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Preferred Python interpreter. Override with `PYTHON_BIN=/path/to/python ./run_inference_compare.sh`
PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ -x "$PYTHON_BIN" ]]; then
  :
elif command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v "$PYTHON_BIN")"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "❌ No python interpreter found. Set PYTHON_BIN explicitly." >&2
  exit 1
fi

# Optional Hugging Face token. You can also pre-export HF_TOKEN/HUGGINGFACEHUB_API_TOKEN.
if [[ -n "${HF_TOKEN:-}" ]]; then
  export HF_TOKEN
  export HUGGINGFACEHUB_API_TOKEN="${HUGGINGFACEHUB_API_TOKEN:-$HF_TOKEN}"
fi

# Model sources and fallbacks.
export BASE_MODEL_REPO="${BASE_MODEL_REPO:-Qwen/Qwen2.5-0.5B-Instruct}"  # HF repo for the base model
export TRAINED_MODEL_REPO="${TRAINED_MODEL_REPO:-}"                       # Optional HF repo for trained model
export DEFAULT_TRAINED_MODEL_PATH="${DEFAULT_TRAINED_MODEL_PATH:-$PROJECT_ROOT/checkpoints/AgentLightningTutorial/math_agent/global_step_1_hf}"
export BASE_MODEL_PATH="${BASE_MODEL_PATH:-}"                               # Optional explicit local path for base model
export TRAINED_MODEL_PATH="${TRAINED_MODEL_PATH:-}"                         # Optional explicit local path for trained model

# vLLM runtime settings (override via environment variables as needed)
export VLLM_API_KEY="${VLLM_API_KEY:-EMPTY}"
export VLLM_PORT="${VLLM_PORT:-8001}"
export VLLM_LAUNCH_TIMEOUT="${VLLM_LAUNCH_TIMEOUT:-300}"

# Log location for vLLM stdout/stderr. Defaults to ./logs/
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/logs}"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"
export VLLM_LOG_FILE="${VLLM_LOG_FILE:-$LOG_DIR/vllm_compare_${TIMESTAMP}.log}"

echo "🧹 Killing any existing vLLM processes..."
pkill -f vllm.entrypoints.openai.api_server >/dev/null 2>&1 || true
sleep 2

echo "🚀 Running inference_compare.py with $PYTHON_BIN"
cd "$PROJECT_ROOT"
"$PYTHON_BIN" "$PROJECT_ROOT/inference_compare.py"

echo "✅ Done. Check the output above and vLLM logs at $VLLM_LOG_FILE if needed."
