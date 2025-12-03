#!/bin/bash
# Data Preparation Script for EAGLE3 Training
# This script prepares conversation data for training the draft model

echo "=================================================="
echo "EAGLE-3 Data Preparation"
echo "=================================================="

# Install dependencies if needed
# pip install datasets tqdm

# Option 1: Use ShareGPT (Full dataset ~114K samples) - RECOMMENDED
echo "Preparing ShareGPT dataset (full)..."
python scripts/prepare_data.py \
    --dataset sharegpt \
    --output-path cache/dataset/

# Option 2: Use ShareGPT with limited samples (for testing/quick iteration)
# echo "Preparing ShareGPT dataset (10K samples)..."
# python scripts/prepare_data.py \
#     --dataset sharegpt \
#     --sample-size 10000 \
#     --output-path cache/dataset/

# Option 3: Use PerfectBlend (larger, higher quality, 7M+ conversations)
# echo "Preparing PerfectBlend dataset..."
# python scripts/prepare_data.py \
#     --dataset perfectblend \
#     --sample-size 50000 \
#     --output-path cache/dataset/

# Option 4: Use UltraChat
# echo "Preparing UltraChat dataset..."
# python scripts/prepare_data.py \
#     --dataset ultrachat \
#     --output-path cache/dataset/

echo "=================================================="
echo "Data preparation complete!"
echo "Output: cache/dataset/sharegpt_train.jsonl"
echo "=================================================="
