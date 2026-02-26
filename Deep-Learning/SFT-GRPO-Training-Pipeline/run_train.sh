#!/bin/bash
# Embedded C++ SFT + GRPO Training Script
# Usage: ./run_train.sh

set -e

echo "=========================================="
echo "Embedded C++ Code Generation Training"
echo "SFT + GRPO on H100"
echo "=========================================="

# Environment setup
export CUDA_VISIBLE_DEVICES=0
# export HF_TOKEN="YOUR-HF-TOKEN"  # Set your HuggingFace token if needed
export HF_ENDPOINT="https://hf-mirror.com"

# Install dependencies if needed
pip install -q unsloth trl transformers datasets accelerate peft vllm

# Verify toolchain
echo "Checking toolchain..."
which clang || apt-get install -y clang
which cppcheck || apt-get install -y cppcheck
which arm-none-eabi-gcc || apt-get install -y gcc-arm-none-eabi

echo "Toolchain ready!"

# Training modes:
# 1. Quick test (few steps)
# 2. SFT only
# 3. GRPO only
# 4. Full SFT + GRPO

MODE=${1:-"full"}

case $MODE in
    "test")
        echo "Running quick test (10 GRPO steps)..."
        python embedded_grpo_train.py \
            --grpo_steps 10 \
            --print_every 1 \
            --debug_every 1 \
            --batch_size 1 \
            --num_gen 2
        ;;
    
    "sft")
        echo "Running SFT only..."
        python embedded_grpo_train.py \
            --do_sft \
            --sft_epochs 2 \
            --grpo_steps 0 \
            --print_every 10
        ;;
    
    "grpo")
        echo "Running GRPO only (assumes SFT already done)..."
        python embedded_grpo_train.py \
            --grpo_steps 500 \
            --print_every 10 \
            --debug_every 50
        ;;
    
    "full")
        echo "Running full SFT + GRPO training..."
        python embedded_grpo_train.py \
            --do_sft \
            --sft_epochs 2 \
            --sft_sample_frac 1.0 \
            --grpo_steps 500 \
            --print_every 10 \
            --debug_every 50 \
            --batch_size 2 \
            --num_gen 4
        ;;
    
    "full_compile")
        echo "Running full training with compilation check (slower)..."
        python embedded_grpo_train.py \
            --do_sft \
            --sft_epochs 2 \
            --grpo_steps 300 \
            --print_every 10 \
            --debug_every 50 \
            --no-use_syntax_only \
            --toolchain arm-none-eabi-gcc
        ;;
    
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: ./run_train.sh [test|sft|grpo|full|full_compile]"
        exit 1
        ;;
esac

echo "=========================================="
echo "Training completed!"
echo "Model saved to: outputs_embedded/"
echo "=========================================="
