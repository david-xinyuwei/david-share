#!/bin/bash
cd /root/quant_exp
mkdir -p logs results

TASK="mmlu_abstract_algebra"
LIMIT=30
LOG="logs/phase1_unsloth.log"

echo "=== Phase 1: Qwen2.5 Original vs unsloth bnb-4bit ===" | tee $LOG
echo "Start: $(date)" | tee -a $LOG
echo "Task: $TASK, Limit: $LIMIT" | tee -a $LOG
echo "Fair Comparison: 公平性 - 同系列模型、同任务、同样本数" | tee -a $LOG
echo "" | tee -a $LOG

for SIZE in 0.5B 1.5B 3B 7B 14B; do
    echo "========================================" | tee -a $LOG
    echo "=== Qwen2.5-${SIZE}-Instruct ===" | tee -a $LOG
    echo "========================================" | tee -a $LOG
    
    # Original (FP16/BF16)
    ORIG_MODEL="Qwen/Qwen2.5-${SIZE}-Instruct"
    echo "[Original] $ORIG_MODEL" | tee -a $LOG
    START=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$ORIG_MODEL,trust_remote_code=True \
        --tasks $TASK --batch_size auto --limit $LIMIT \
        --output_path results/unsloth_orig_${SIZE} 2>&1 | tee -a $LOG | grep -E "abstract_algebra.*\|"
    END=$(date +%s)
    echo "Time: $((END-START))s" | tee -a $LOG
    
    # unsloth bnb-4bit (预量化)
    QUANT_MODEL="unsloth/Qwen2.5-${SIZE}-Instruct-bnb-4bit"
    echo "[bnb-4bit] $QUANT_MODEL" | tee -a $LOG
    START=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$QUANT_MODEL,trust_remote_code=True \
        --tasks $TASK --batch_size auto --limit $LIMIT \
        --output_path results/unsloth_4bit_${SIZE} 2>&1 | tee -a $LOG | grep -E "abstract_algebra.*\|"
    END=$(date +%s)
    echo "Time: $((END-START))s" | tee -a $LOG
    echo "" | tee -a $LOG
done

echo "========================================" | tee -a $LOG
echo "=== Completed: $(date) ===" | tee -a $LOG
