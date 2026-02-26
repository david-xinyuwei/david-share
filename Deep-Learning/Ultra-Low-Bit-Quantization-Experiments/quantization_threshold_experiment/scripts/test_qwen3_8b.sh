#!/bin/bash
cd /root/quant_exp
LOG="logs/qwen3_8b.log"
rm -f $LOG
echo "=== Qwen3-8B Quantization Test ===" | tee $LOG
echo "Start: $(date)" | tee $LOG

MODEL="Qwen/Qwen3-8B"

# Phase 0: Smoke test (1 sample)
echo "--- Phase 0: Smoke Test ---" | tee -a $LOG
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 1 \
    --output_path results/smoke_qwen3_8b 2>&1 | tee -a $LOG
echo "Smoke test time: $(($(date +%s) - START)) seconds" | tee -a $LOG

# Phase 1: Original (5 samples)
echo "--- Phase 1: Original (5 samples) ---" | tee -a $LOG
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 5 \
    --output_path results/orig_qwen3_8b 2>&1 | tee -a $LOG
echo "Original time: $(($(date +%s) - START)) seconds" | tee -a $LOG

# Phase 1: 4-bit (5 samples)
echo "--- Phase 1: 4-bit (5 samples) ---" | tee -a $LOG
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,load_in_4bit=True,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 5 \
    --output_path results/bnb4bit_qwen3_8b 2>&1 | tee -a $LOG
echo "4-bit time: $(($(date +%s) - START)) seconds" | tee -a $LOG

echo "=== Completed: $(date) ===" | tee -a $LOG
