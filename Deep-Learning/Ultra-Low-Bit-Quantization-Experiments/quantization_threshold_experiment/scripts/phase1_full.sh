#!/bin/bash
cd /root/quant_exp
mkdir -p logs results

TASK="mmlu_abstract_algebra"
LIMIT=30
LOG="logs/phase1_full.log"

echo "=== Phase 1: Qwen2.5 Full Series (30 samples) ===" | tee $LOG
echo "Start: $(date)" | tee -a $LOG
echo "Task: $TASK, Limit: $LIMIT" | tee -a $LOG
echo "" | tee -a $LOG

for SIZE in 0.5B 1.5B 3B 7B 14B; do
    MODEL="Qwen/Qwen2.5-${SIZE}-Instruct"
    echo "=== $MODEL ===" | tee -a $LOG
    
    # Original
    echo "  [Original]" | tee -a $LOG
    START=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$MODEL,trust_remote_code=True \
        --tasks $TASK --batch_size auto --limit $LIMIT \
        --output_path results/p1_orig_${SIZE} 2>&1 | grep -E "abstract_algebra.*acc|Error" | tee -a $LOG
    END=$(date +%s)
    echo "  Time: $((END-START))s" | tee -a $LOG
    
    # 4-bit
    echo "  [4-bit]" | tee -a $LOG
    START=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$MODEL,trust_remote_code=True,load_in_4bit=True \
        --tasks $TASK --batch_size auto --limit $LIMIT \
        --output_path results/p1_4bit_${SIZE} 2>&1 | grep -E "abstract_algebra.*acc|Error" | tee -a $LOG
    END=$(date +%s)
    echo "  Time: $((END-START))s" | tee -a $LOG
    echo "" | tee -a $LOG
done

echo "=== Completed: $(date) ===" | tee -a $LOG
