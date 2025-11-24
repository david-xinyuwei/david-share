#!/bin/bash
source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate agentL

export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

echo "🚀 Starting Verification on H100..."
python train_math_agent_vllm.py
