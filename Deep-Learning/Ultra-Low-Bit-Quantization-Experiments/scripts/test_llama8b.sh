#!/bin/bash
cd /root/quant_exp
LOG="logs/llama8b.log"
rm -f $LOG
echo "=== Llama-3.1-8B-Instruct Quantization Test ===" | tee $LOG
echo "Start: $(date)" | tee $LOG

MODEL="meta-llama/Llama-3.1-8B-Instruct"

# Phase 0: Smoke test (1 sample)
echo "--- Phase 0: Smoke Test (1 sample) ---" | tee -a $LOG
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 1 \
    --output_path results/smoke_llama8b 2>&1 | tee -a $LOG
SMOKE_TIME=$(($(date +%s) - START))
echo "Smoke test time: ${SMOKE_TIME} seconds" | tee -a $LOG

if [ $SMOKE_TIME -gt 600 ]; then
    echo "❌ Smoke test too slow, aborting" | tee -a $LOG
    exit 1
fi

# Phase 1: Original (5 samples)
echo "--- Phase 1: Original (5 samples) ---" | tee -a $LOG
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 5 \
    --output_path results/orig_llama8b 2>&1 | tee -a $LOG
echo "Original time: $(($(date +%s) - START)) seconds" | tee -a $LOG

# Phase 2: 4-bit (5 samples)
echo "--- Phase 2: 4-bit (5 samples) ---" | tee -a $LOG
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=$MODEL,load_in_4bit=True,trust_remote_code=True \
    --tasks mmlu_pro_math \
    --batch_size auto \
    --limit 5 \
    --output_path results/bnb4bit_llama8b 2>&1 | tee -a $LOG
echo "4-bit time: $(($(date +%s) - START)) seconds" | tee -a $LOG

echo "=== Completed: $(date) ===" | tee -a $LOG
