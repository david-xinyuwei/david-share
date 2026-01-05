#!/bin/bash
cd /root/quant_exp
LOG="logs/test_9b_quick.log"
echo "=== Yi-1.5-9B 4-bit Quick Test (10 samples) ===" | tee $LOG

START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=01-ai/Yi-1.5-9B-Chat,load_in_4bit=True,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 10 \
    --output_path results/bnb4bit_yi9b_10 2>&1 | tee -a $LOG
echo "4-bit time: $(($(date +%s) - START)) seconds" | tee -a $LOG
