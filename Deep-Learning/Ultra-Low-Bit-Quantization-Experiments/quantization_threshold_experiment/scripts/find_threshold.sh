#!/bin/bash
cd /root/quant_exp
LOG_FILE="logs/find_threshold.log"
rm -f $LOG_FILE
echo "=== Finding Quantization Threshold ===" | tee -a $LOG_FILE
echo "Start time: $(date)" | tee -a $LOG_FILE

# 测试更大的模型找转折点
MODELS=(
    "Qwen/Qwen2.5-14B-Instruct"
    "Qwen/Qwen2.5-32B-Instruct"
)

for MODEL in "${MODELS[@]}"; do
    NAME=$(basename $MODEL)
    
    # 1. 原始模型
    echo "---------------------------------------------" | tee -a $LOG_FILE
    echo "Testing ORIGINAL: $NAME" | tee -a $LOG_FILE
    echo "Time: $(date)" | tee -a $LOG_FILE
    START_TIME=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$MODEL,trust_remote_code=True \
        --tasks mmlu_pro_math \
        --batch_size auto \
        --limit 5 \
        --output_path results/orig_$NAME 2>&1 | tee -a $LOG_FILE
    END_TIME=$(date +%s)
    echo "Original time: $((END_TIME - START_TIME)) seconds" | tee -a $LOG_FILE
    
    # 2. 4-bit 量化
    echo "---------------------------------------------" | tee -a $LOG_FILE
    echo "Testing 4-BIT: $NAME" | tee -a $LOG_FILE
    echo "Time: $(date)" | tee -a $LOG_FILE
    START_TIME=$(date +%s)
    lm_eval --model hf \
        --model_args pretrained=$MODEL,load_in_4bit=True,trust_remote_code=True \
        --tasks mmlu_pro_math \
        --batch_size auto \
        --limit 5 \
        --output_path results/bnb4bit_$NAME 2>&1 | tee -a $LOG_FILE
    END_TIME=$(date +%s)
    echo "4-bit time: $((END_TIME - START_TIME)) seconds" | tee -a $LOG_FILE
done

echo "---------------------------------------------" | tee -a $LOG_FILE
echo "Threshold search completed: $(date)" | tee -a $LOG_FILE
