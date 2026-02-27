#!/bin/bash
cd /root/quant_exp
LOG_FILE="logs/quant_gptq.log"
rm -f $LOG_FILE
echo "=== GPTQ 4-bit Pre-quantized Model Test ===" | tee -a $LOG_FILE
echo "Start time: $(date)" | tee -a $LOG_FILE

MODELS=(
    "Qwen/Qwen2.5-0.5B-Instruct-GPTQ-Int4"
    "Qwen/Qwen2.5-1.5B-Instruct-GPTQ-Int4"
    "Qwen/Qwen2.5-3B-Instruct-GPTQ-Int4"
    "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
)

for MODEL in "${MODELS[@]}"; do
    NAME=$(basename $MODEL)
    echo "---------------------------------------------" | tee -a $LOG_FILE
    echo "Testing GPTQ: $NAME" | tee -a $LOG_FILE
    echo "Time: $(date)" | tee -a $LOG_FILE
    
    START_TIME=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$MODEL,trust_remote_code=True \
        --tasks mmlu_pro_math \
        --batch_size auto \
        --limit 5 \
        --output_path results/gptq_$NAME 2>&1 | tee -a $LOG_FILE
    END_TIME=$(date +%s)
    echo "Time taken: $((END_TIME - START_TIME)) seconds" | tee -a $LOG_FILE
done

echo "---------------------------------------------" | tee -a $LOG_FILE
echo "All GPTQ tests completed: $(date)" | tee -a $LOG_FILE
