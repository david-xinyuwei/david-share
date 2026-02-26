#!/bin/bash
export PATH="/root/miniconda3/bin:$PATH"
source /root/miniconda3/etc/profile.d/conda.sh
conda activate lm-eval

LOGFILE="/root/quant_exp/logs/phase2_verify.log"
echo "=== 可重复性验证 Run2 ===" | tee $LOGFILE
echo "开始: $(date)" | tee -a $LOGFILE

for SIZE in "0.5B" "1.5B" "3B" "7B" "14B" "32B"; do
    echo "" | tee -a $LOGFILE
    echo "=== Qwen2.5-${SIZE} ===" | tee -a $LOGFILE
    
    lm_eval --model hf --model_args pretrained=Qwen/Qwen2.5-${SIZE}-Instruct,trust_remote_code=True \
        --tasks mmlu_abstract_algebra --limit 100 --batch_size auto 2>&1 | tee -a $LOGFILE
    python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null
    
    lm_eval --model hf --model_args pretrained=unsloth/Qwen2.5-${SIZE}-Instruct-bnb-4bit,trust_remote_code=True \
        --tasks mmlu_abstract_algebra --limit 100 --batch_size auto 2>&1 | tee -a $LOGFILE
    python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null
done

echo "" | tee -a $LOGFILE
echo "完成: $(date)" | tee -a $LOGFILE
