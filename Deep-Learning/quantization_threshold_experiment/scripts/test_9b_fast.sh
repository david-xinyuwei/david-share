#!/bin/bash
LOG="logs/test_9b_fast.log"
echo "=== Yi-1.5-9B 4-bit Fast Test (max_gen_toks=512) ===" | tee $LOG

START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=01-ai/Yi-1.5-9B-Chat,load_in_4bit=True,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 10 \
    --gen_kwargs max_gen_toks=512 \
    --output_path results/bnb4bit_yi9b_fast 2>&1 | tee -a $LOG
echo "4-bit time: $(($(date +%s) - START)) seconds" | tee -a $LOG
