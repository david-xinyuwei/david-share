#!/usr/bin/env bash
set -euo pipefail

# Example only. Validate version, CUDA, audio dependencies, and endpoint contract first.
python -m vllm.entrypoints.openai.api_server   --model Qwen/Qwen3-ASR-1.7B   --host 0.0.0.0   --port 8000   --gpu-memory-utilization 0.80   --trust-remote-code

