#!/bin/bash
# 02_evaluate_models.sh - 使用 lm-eval 评估模型
#
# 评估原始模型和量化模型在 MMLU-PRO, IFEval, GSM8K 上的表现
# 用于验证 Benjamin Marie 的 "≥10B 量化安全" 结论

set -e

# ============================================================
# 配置
# ============================================================

OUTPUT_DIR="./results/raw"
mkdir -p "$OUTPUT_DIR"

# 原始模型列表
ORIGINAL_MODELS=(
    "Qwen/Qwen2.5-0.5B-Instruct"
    "Qwen/Qwen2.5-1.5B-Instruct"
    "Qwen/Qwen2.5-3B-Instruct"
    "Qwen/Qwen2.5-7B-Instruct"
    "Qwen/Qwen2.5-14B-Instruct"
    "Qwen/Qwen2.5-32B-Instruct"
)

# 量化模型目录
QUANT_DIR="./quantized_models"

# Benchmark 配置
# - MMLU-PRO: 知识准确性 (5-shot)
# - IFEval: 指令遵循 (0-shot)
# - GSM8K: 数学推理 (8-shot)

# ============================================================
# 辅助函数
# ============================================================

evaluate_model() {
    local model_path="$1"
    local model_name="$2"
    local backend="$3"  # "hf" 或 "vllm"
    local output_file="$OUTPUT_DIR/${model_name}_results.json"
    
    if [[ -f "$output_file" ]]; then
        echo "⏭️  跳过 $model_name (结果已存在)"
        return
    fi
    
    echo ""
    echo "============================================================"
    echo "🧪 评估 $model_name (backend: $backend)"
    echo "============================================================"
    
    if [[ "$backend" == "vllm" ]]; then
        # vLLM backend (更快，用于生成式任务)
        lm_eval --model vllm \
            --model_args "pretrained=$model_path,tensor_parallel_size=1,gpu_memory_utilization=0.9" \
            --tasks mmlu_pro,ifeval,gsm8k \
            --num_fewshot 5,0,8 \
            --batch_size auto \
            --output_path "$output_file"
    else
        # HF Transformers backend
        lm_eval --model hf \
            --model_args "pretrained=$model_path,trust_remote_code=True" \
            --tasks mmlu_pro,ifeval,gsm8k \
            --num_fewshot 5,0,8 \
            --batch_size auto \
            --output_path "$output_file"
    fi
    
    echo "✅ 结果保存到 $output_file"
}

# ============================================================
# Step 1: 评估原始模型 (Baseline)
# ============================================================

echo ""
echo "########################################################"
echo "#  Step 1: 评估原始模型 (Baseline)                      #"
echo "########################################################"

for model in "${ORIGINAL_MODELS[@]}"; do
    model_name=$(basename "$model")
    evaluate_model "$model" "${model_name}_original" "vllm"
done

# ============================================================
# Step 2: 评估 AWQ 量化模型
# ============================================================

echo ""
echo "########################################################"
echo "#  Step 2: 评估 AWQ 量化模型                           #"
echo "########################################################"

for model in "${ORIGINAL_MODELS[@]}"; do
    model_name=$(basename "$model")
    quant_path="$QUANT_DIR/${model_name}-AWQ-4bit"
    
    if [[ -d "$quant_path" ]]; then
        evaluate_model "$quant_path" "${model_name}_AWQ-4bit" "vllm"
    else
        echo "⚠️  跳过 $model_name AWQ (未找到量化模型)"
    fi
done

# ============================================================
# Step 3: 评估 GPTQ 量化模型
# ============================================================

echo ""
echo "########################################################"
echo "#  Step 3: 评估 GPTQ 量化模型                          #"
echo "########################################################"

for model in "${ORIGINAL_MODELS[@]}"; do
    model_name=$(basename "$model")
    quant_path="$QUANT_DIR/${model_name}-GPTQ-4bit"
    
    if [[ -d "$quant_path" ]]; then
        evaluate_model "$quant_path" "${model_name}_GPTQ-4bit" "vllm"
    else
        echo "⚠️  跳过 $model_name GPTQ (未找到量化模型)"
    fi
done

# ============================================================
# 完成
# ============================================================

echo ""
echo "########################################################"
echo "#  评估完成！                                          #"
echo "########################################################"
echo ""
echo "📁 结果目录: $OUTPUT_DIR"
echo "📊 下一步: 运行 03_analyze_results.py 分析结果"
