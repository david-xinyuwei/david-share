#!/bin/bash
cd /root/quant_exp
mkdir -p logs results
TASK="mmlu_abstract_algebra"
LIMIT=30

echo "=== Phase 2: 30 Samples Test ===" | tee logs/phase2.log
echo "Start: $(date)" | tee -a logs/phase2.log

# Qwen2.5-7B
echo "--- Qwen2.5-7B-Instruct ---" | tee -a logs/phase2.log
lm_eval --model hf --model_args pretrained=Qwen/Qwen2.5-7B-Instruct,trust_remote_code=True \
    --tasks $TASK --batch_size auto --limit $LIMIT --output_path results/p2_orig_qwen7b 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/phase2.log
lm_eval --model hf --model_args pretrained=Qwen/Qwen2.5-7B-Instruct,trust_remote_code=True,load_in_4bit=True \
    --tasks $TASK --batch_size auto --limit $LIMIT --output_path results/p2_4bit_qwen7b 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/phase2.log

# Llama-3.1-8B
echo "--- Llama-3.1-8B-Instruct ---" | tee -a logs/phase2.log
lm_eval --model hf --model_args pretrained=meta-llama/Llama-3.1-8B-Instruct,trust_remote_code=True \
    --tasks $TASK --batch_size auto --limit $LIMIT --output_path results/p2_orig_llama8b 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/phase2.log
lm_eval --model hf --model_args pretrained=meta-llama/Llama-3.1-8B-Instruct,trust_remote_code=True,load_in_4bit=True \
    --tasks $TASK --batch_size auto --limit $LIMIT --output_path results/p2_4bit_llama8b 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/phase2.log

# Qwen2.5-14B
echo "--- Qwen2.5-14B-Instruct ---" | tee -a logs/phase2.log
lm_eval --model hf --model_args pretrained=Qwen/Qwen2.5-14B-Instruct,trust_remote_code=True \
    --tasks $TASK --batch_size auto --limit $LIMIT --output_path results/p2_orig_qwen14b 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/phase2.log
lm_eval --model hf --model_args pretrained=Qwen/Qwen2.5-14B-Instruct,trust_remote_code=True,load_in_4bit=True \
    --tasks $TASK --batch_size auto --limit $LIMIT --output_path results/p2_4bit_qwen14b 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/phase2.log

echo "=== Completed: $(date) ===" | tee -a logs/phase2.log
