#!/bin/bash
# Phase 2: 100 样本测试 Qwen2.5 系列
# Experiment Goal：找到量化损失转折点
# Following best practices：12(公平性) 15(鲁棒性) 3(非阻塞) 8(可观测)

export PATH="/root/miniconda3/bin:$PATH"
source /root/miniconda3/etc/profile.d/conda.sh
conda activate lm-eval

LOGFILE="/root/quant_exp/logs/phase2_100samples.log"
mkdir -p /root/quant_exp/logs

echo "========================================" | tee -a $LOGFILE
echo "Phase 2: 100 样本 Qwen2.5 量化测试" | tee -a $LOGFILE
echo "开始时间: $(date)" | tee -a $LOGFILE
echo "========================================" | tee -a $LOGFILE

# 模型列表（从小到大）
SIZES=("0.5B" "1.5B" "3B" "7B" "14B" "32B")

for SIZE in "${SIZES[@]}"; do
    echo "" | tee -a $LOGFILE
    echo "======== Qwen2.5-${SIZE}-Instruct ========" | tee -a $LOGFILE
    
    # 原版测试
    echo "[$(date +%H:%M:%S)] 测试原版 Qwen2.5-${SIZE}-Instruct..." | tee -a $LOGFILE
    lm_eval --model hf \
        --model_args pretrained=Qwen/Qwen2.5-${SIZE}-Instruct,trust_remote_code=True \
        --tasks mmlu_abstract_algebra \
        --limit 100 \
        --batch_size auto 2>&1 | tee -a $LOGFILE
    
    # 清理 GPU 显存
    python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null
    
    # bnb-4bit 测试
    echo "[$(date +%H:%M:%S)] 测试 unsloth/Qwen2.5-${SIZE}-Instruct-bnb-4bit..." | tee -a $LOGFILE
    lm_eval --model hf \
        --model_args pretrained=unsloth/Qwen2.5-${SIZE}-Instruct-bnb-4bit,trust_remote_code=True \
        --tasks mmlu_abstract_algebra \
        --limit 100 \
        --batch_size auto 2>&1 | tee -a $LOGFILE
    
    # 清理 GPU 显存
    python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null
    
    echo "[$(date +%H:%M:%S)] Qwen2.5-${SIZE} 完成" | tee -a $LOGFILE
done

echo "" | tee -a $LOGFILE
echo "========================================" | tee -a $LOGFILE
echo "Phase 2 完成时间: $(date)" | tee -a $LOGFILE
echo "========================================" | tee -a $LOGFILE
