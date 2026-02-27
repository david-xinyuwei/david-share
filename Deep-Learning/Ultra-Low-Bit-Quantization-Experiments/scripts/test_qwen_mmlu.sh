#!/bin/bash
cd /root/quant_exp
TASK="mmlu_abstract_algebra"

for SIZE in 7B 14B; do
    echo "=== Qwen2.5-${SIZE}-Instruct ===" | tee -a logs/qwen_mmlu.log
    
    # Original
    lm_eval --model hf \
        --model_args pretrained=Qwen/Qwen2.5-${SIZE}-Instruct,trust_remote_code=True \
        --tasks $TASK --batch_size auto --limit 5 \
        --output_path results/orig_qwen${SIZE}_mmlu 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/qwen_mmlu.log
    
    # 4-bit
    lm_eval --model hf \
        --model_args pretrained=Qwen/Qwen2.5-${SIZE}-Instruct,trust_remote_code=True,load_in_4bit=True \
        --tasks $TASK --batch_size auto --limit 5 \
        --output_path results/bnb4bit_qwen${SIZE}_mmlu 2>&1 | grep -E "abstract_algebra|error" | tee -a logs/qwen_mmlu.log
    
    echo "---" | tee -a logs/qwen_mmlu.log
done
echo "=== Done $(date) ===" | tee -a logs/qwen_mmlu.log
