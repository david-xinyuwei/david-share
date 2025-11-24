#!/bin/bash
source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate agentL
python -u train_math_agent_vllm.py > train_vllm_final.log 2>&1
