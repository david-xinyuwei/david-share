#!/bin/bash
# Phase 1b: 量化模型 vs 原模型对比
# 使用社区已量化的 AWQ 模型

LOG_FILE="/root/quant_exp/logs/quant_compare.log"

echo "============================================" | tee $LOG_FILE
echo "🔬 量化模型 vs 原模型对比" | tee -a $LOG_FILE
echo "⏰ 开始: $(date)" | tee -a $LOG_FILE
echo "============================================" | tee -a $LOG_FILE

# 测试模型对 (原模型 vs AWQ 量化)
declare -A MODELS
MODELS["0.5B_orig"]="Qwen/Qwen2.5-0.5B-Instruct"
MODELS["0.5B_awq"]="Qwen/Qwen2.5-0.5B-Instruct-AWQ"
MODELS["1.5B_orig"]="Qwen/Qwen2.5-1.5B-Instruct"
MODELS["1.5B_awq"]="Qwen/Qwen2.5-1.5B-Instruct-AWQ"
MODELS["3B_orig"]="Qwen/Qwen2.5-3B-Instruct"
MODELS["3B_awq"]="Qwen/Qwen2.5-3B-Instruct-AWQ"
MODELS["7B_orig"]="Qwen/Qwen2.5-7B-Instruct"
MODELS["7B_awq"]="Qwen/Qwen2.5-7B-Instruct-AWQ"

# 只测量化版本 (原模型已测过)
QUANT_MODELS=(
    "Qwen/Qwen2.5-0.5B-Instruct-AWQ"
    "Qwen/Qwen2.5-1.5B-Instruct-AWQ"
    "Qwen/Qwen2.5-3B-Instruct-AWQ"
    "Qwen/Qwen2.5-7B-Instruct-AWQ"
)

for i in "${!QUANT_MODELS[@]}"; do
    MODEL=${QUANT_MODELS[$i]}
    MODEL_NAME=$(basename $MODEL)
    
    echo "" | tee -a $LOG_FILE
    echo "[$((i+1))/${#QUANT_MODELS[@]}] 评估 $MODEL_NAME ..." | tee -a $LOG_FILE
    
    START=$(date +%s)
    
    lm_eval --model hf \
        --model_args pretrained=$MODEL,trust_remote_code=True \
        --tasks mmlu_pro_math \
        --limit 5 \
        --batch_size 4 \
        2>&1 | tee -a $LOG_FILE
    
    END=$(date +%s)
    echo "   ⏱️ 耗时: $((END-START))s" | tee -a $LOG_FILE
done

echo "" | tee -a $LOG_FILE
echo "============================================" | tee -a $LOG_FILE
echo "✅ 完成: $(date)" | tee -a $LOG_FILE
