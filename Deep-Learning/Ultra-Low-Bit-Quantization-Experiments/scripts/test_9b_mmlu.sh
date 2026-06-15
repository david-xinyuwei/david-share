#!/bin/bash
cd /root/quant_exp
LOG_FILE="logs/test_9b_mmlu.log"
rm -f $LOG_FILE
echo "=== 9B Model Test with MMLU (easier) ===" | tee -a $LOG_FILE
echo "Start: $(date)" | tee -a $LOG_FILE

MODEL="01-ai/Yi-1.5-9B-Chat"
NAME="Yi-1.5-9B"

# 1. Original
echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Testing ORIGINAL: $NAME" | tee -a $LOG_FILE
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu \
    --batch_size auto \
    --limit 10 \
    --output_path results/orig_yi9b_mmlu 2>&1 | tee -a $LOG_FILE
echo "Original time: $(($(date +%s) - START)) seconds" | tee -a $LOG_FILE

# 2. 4-bit
echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Testing 4-BIT: $NAME" | tee -a $LOG_FILE
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,load_in_4bit=True,trust_remote_code=True \
    --tasks mmlu \
    --batch_size auto \
    --limit 10 \
    --output_path results/bnb4bit_yi9b_mmlu 2>&1 | tee -a $LOG_FILE
echo "4-bit time: $(($(date +%s) - START)) seconds" | tee -a $LOG_FILE

echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Completed: $(date)" | tee -a $LOG_FILE
