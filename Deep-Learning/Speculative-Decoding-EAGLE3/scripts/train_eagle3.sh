#!/bin/bash
# EAGLE-3 Training Script for Llama-3.1-8B-Instruct
# Optimized configuration based on actual H100 training experience

export TORCHINDUCTOR_CACHE_DIR=./cache/compiled_kernels
export HF_HOME=~/.cache/huggingface
export NCCL_TIMEOUT=1800

echo "=================================================="
echo "EAGLE-3 Training - Optimized Version"
echo "=================================================="
echo "Data: 114,641 samples (ShareGPT full)"
echo "Epochs: 10"
echo "Learning Rate: 1e-4"
echo "=================================================="

# Option 1: Using torchrun (recommended for distributed training)
torchrun \
    --standalone \
    --nproc_per_node 1 \
    scripts/train_eagle3.py \
    --target-model-path meta-llama/Llama-3.1-8B-Instruct \
    --draft-model-config configs/llama3-8B-eagle3.json \
    --train-data-path cache/dataset/sharegpt_train.jsonl \
    --output-dir output/eagle3-llama31-8b-full \
    --num-epochs 10 \
    --batch-size 1 \
    --learning-rate 1e-4 \
    --max-length 4096 \
    --chat-template llama3 \
    --cache-dir cache \
    --attention-backend sdpa \
    --target-model-backend sglang \
    --log-interval 100 \
    --save-interval 5000 \
    --warmup-ratio 0.02

# Option 2: Simple python execution (for debugging)
# python scripts/train_eagle3.py \
#     --target-model-path meta-llama/Llama-3.1-8B-Instruct \
#     --draft-model-config configs/llama3-8B-eagle3.json \
#     --train-data-path cache/dataset/sharegpt_train.jsonl \
#     --output-dir output/eagle3-llama31-8b-full \
#     --num-epochs 10 \
#     --batch-size 1 \
#     --learning-rate 1e-4 \
#     --max-length 4096 \
#     --chat-template llama3 \
#     --cache-dir cache \
#     --attention-backend sdpa \
#     --target-model-backend sglang \
#     --log-interval 100 \
#     --save-interval 5000
