#!/bin/bash
# Phase 1: 快速验证转折点 (Best Practice: 最小代价验证)
# 每模型只跑 5 样本，预计 2-3 分钟/模型

LOG_FILE="/root/quant_exp/logs/quick_threshold.log"
RESULT_FILE="/root/quant_exp/results/quick_threshold.json"

echo "============================================" | tee $LOG_FILE
echo "🚀 Phase 1: 快速验证转折点" | tee -a $LOG_FILE
echo "⏰ 开始: $(date)" | tee -a $LOG_FILE
echo "============================================" | tee -a $LOG_FILE

# 只测试关键模型 (覆盖转折点区间)
MODELS=(
    "Qwen/Qwen2.5-0.5B-Instruct"
    "Qwen/Qwen2.5-1.5B-Instruct"  
    "Qwen/Qwen2.5-3B-Instruct"
    "Qwen/Qwen2.5-7B-Instruct"
)

echo "[" > $RESULT_FILE

for i in "${!MODELS[@]}"; do
    MODEL=${MODELS[$i]}
    MODEL_NAME=$(basename $MODEL)
    
    echo "" | tee -a $LOG_FILE
    echo "[$((i+1))/${#MODELS[@]}] 评估 $MODEL_NAME ..." | tee -a $LOG_FILE
    
    START=$(date +%s)
    
    # 只跑 5 样本，单任务
    OUTPUT=$(lm_eval --model hf \
        --model_args pretrained=$MODEL,trust_remote_code=True \
        --tasks mmlu_pro_math \
        --limit 5 \
        --batch_size 4 \
        2>&1 | tee -a $LOG_FILE)
    
    END=$(date +%s)
    ELAPSED=$((END-START))
    
    # 提取分数
    SCORE=$(echo "$OUTPUT" | grep "exact_match" | awk '{print $(NF-2)}')
    
    echo "   ⏱️ 耗时: ${ELAPSED}s | 分数: $SCORE" | tee -a $LOG_FILE
    
    # 写入 JSON
    if [ $i -gt 0 ]; then echo "," >> $RESULT_FILE; fi
    echo "  {\"model\": \"$MODEL_NAME\", \"score\": $SCORE, \"time_s\": $ELAPSED}" >> $RESULT_FILE
done

echo "]" >> $RESULT_FILE

echo "" | tee -a $LOG_FILE
echo "============================================" | tee -a $LOG_FILE
echo "✅ 完成: $(date)" | tee -a $LOG_FILE
echo "📊 结果: $RESULT_FILE" | tee -a $LOG_FILE
cat $RESULT_FILE | tee -a $LOG_FILE
