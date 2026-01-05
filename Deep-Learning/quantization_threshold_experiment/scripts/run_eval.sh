#!/bin/bash
# 可观测的评估脚本 (Best Practice: Traceability)

MODEL=$1
OUTPUT_NAME=$2
LOG_FILE="/root/quant_exp/logs/${OUTPUT_NAME}.log"

mkdir -p /root/quant_exp/logs
mkdir -p /root/quant_exp/results/raw

echo "========================================" | tee -a $LOG_FILE
echo "🚀 开始评估: $MODEL" | tee -a $LOG_FILE
echo "⏰ 时间: $(date)" | tee -a $LOG_FILE
echo "========================================" | tee -a $LOG_FILE

# 运行 lm_eval，实时输出到日志
lm_eval --model hf \
    --model_args pretrained=$MODEL,trust_remote_code=True \
    --tasks mmlu_pro \
    --limit 50 \
    --batch_size 4 \
    --output_path /root/quant_exp/results/raw/${OUTPUT_NAME} \
    2>&1 | tee -a $LOG_FILE

echo "" | tee -a $LOG_FILE
echo "✅ 评估完成: $(date)" | tee -a $LOG_FILE
echo "📁 结果: /root/quant_exp/results/raw/${OUTPUT_NAME}" | tee -a $LOG_FILE
