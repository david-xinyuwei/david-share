#!/bin/bash
# EAGLE3 Server Deployment Script
# Deploy the trained EAGLE3 model with SGLang

export SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1

# Configuration
MODEL_PATH="meta-llama/Llama-3.1-8B-Instruct"
# Use official model or custom trained model:
# DRAFT_MODEL="jamesliu1/sglang-EAGLE3-Llama-3.1-Instruct-8B"  # Official
DRAFT_MODEL="./output/eagle3-llama31-8b-full/epoch_0_step_5000"  # Custom trained
PORT=8080

echo "=================================================="
echo "Deploying EAGLE3 Server"
echo "=================================================="
echo "Target Model: ${MODEL_PATH}"
echo "Draft Model: ${DRAFT_MODEL}"
echo "Port: ${PORT}"
echo "=================================================="

python -m sglang.launch_server \
    --model-path ${MODEL_PATH} \
    --speculative-algorithm EAGLE3 \
    --speculative-draft-model-path ${DRAFT_MODEL} \
    --speculative-num-steps 5 \
    --speculative-eagle-topk 8 \
    --speculative-num-draft-tokens 64 \
    --dtype float16 \
    --host 0.0.0.0 \
    --port ${PORT}

# For baseline comparison (no speculative decoding):
# python -m sglang.launch_server \
#     --model-path ${MODEL_PATH} \
#     --dtype float16 \
#     --host 0.0.0.0 \
#     --port ${PORT}
