#!/bin/bash
cd /root/quant_exp
LOG_FILE="logs/test_10b.log"
rm -f $LOG_FILE
echo "=== Testing 9-10B Boundary ===" | tee -a $LOG_FILE
echo "Start: $(date)" | tee -a $LOG_FILE

MODEL="google/gemma-2-9b-it"
NAME="gemma-2-9b-it"

# 1. 原始模型
echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Testing ORIGINAL: $NAME (9B)" | tee -a $LOG_FILE
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 5 \
    --output_path results/orig_$NAME 2>&1 | tee -a $LOG_FILE
echo "Original time: $(($(date +%s) - START)) seconds" | tee -a $LOG_FILE

# 2. 4-bit 量化
echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Testing 4-BIT: $NAME (9B)" | tee -a $LOG_FILE
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,load_in_4bit=True,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 5 \
    --output_path results/bnb4bit_$NAME 2>&1 | tee -a $LOG_FILE
echo "4-bit time: $(($(date +%s) - START)) seconds" | tee -a $LOG_FILE

echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Done: $(date)" | tee -a $LOG_FILE
