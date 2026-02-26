#!/bin/bash
cd /root/quant_exp
mkdir -p logs results

echo "=== Llama-3.1-8B-Instruct MMLU Test ===" | tee logs/llama8b_mmlu.log
echo "Start: $(date)" | tee -a logs/llama8b_mmlu.log

# 使用 mmlu_abstract_algebra (多选题，不需要长生成)
TASK="mmlu_abstract_algebra"

echo "--- Phase 1: Original (5 samples) ---" | tee -a logs/llama8b_mmlu.log
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=meta-llama/Llama-3.1-8B-Instruct,trust_remote_code=True \
    --tasks $TASK \
    --batch_size auto \
    --limit 5 \
    --output_path results/orig_llama8b_mmlu 2>&1 | tee -a logs/llama8b_mmlu.log
END=$(date +%s)
echo "Original time: $((END-START)) seconds" | tee -a logs/llama8b_mmlu.log

echo "--- Phase 2: 4-bit (5 samples) ---" | tee -a logs/llama8b_mmlu.log
START=$(date +%s)
lm_eval --model hf \
    --model_args pretrained=meta-llama/Llama-3.1-8B-Instruct,trust_remote_code=True,load_in_4bit=True \
    --tasks $TASK \
    --batch_size auto \
    --limit 5 \
    --output_path results/bnb4bit_llama8b_mmlu 2>&1 | tee -a logs/llama8b_mmlu.log
END=$(date +%s)
echo "4-bit time: $((END-START)) seconds" | tee -a logs/llama8b_mmlu.log

echo "=== Completed: $(date) ===" | tee -a logs/llama8b_mmlu.log
