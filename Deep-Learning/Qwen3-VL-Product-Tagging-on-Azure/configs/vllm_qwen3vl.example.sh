#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-Qwen/Qwen3-VL-8B-Instruct}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
DTYPE="${DTYPE:-bfloat16}"

# Requires Docker with NVIDIA Container Toolkit.
docker run --gpus all --rm -p "${PORT}:8000" \
  vllm/vllm-openai:latest \
  --model "${MODEL_NAME}" \
  --dtype "${DTYPE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --trust-remote-code
