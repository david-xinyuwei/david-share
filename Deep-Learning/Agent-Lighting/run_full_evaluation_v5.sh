#!/bin/bash
# 完整验证 Pipeline: 启动基础模型 -> 启动训练后模型 -> 运行对比评估

# 1. 清理环境
echo "🧹 Cleaning up..."
pkill -9 -f python
pkill -9 -f vllm
sleep 2

# 2. 激活环境（如果使用 conda）
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    conda activate agentL
fi

# 3. 启动基础模型 (Port 8000)
BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"
echo "🚀 Starting Base Model (vLLM on port 8000)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $BASE_MODEL \
    --served-model-name "base-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.35 \
    --port 8000 > vllm_base.log 2>&1 &

# 4. 启动训练后模型 (Port 8001)
# 注意：这里使用我们刚刚转换好的 Checkpoint (v5_correctness_first)
TRAINED_MODEL="$(pwd)/checkpoints/AgentLightningTutorial/math_agent_3b_h100_v5_correctness_first/global_step_100/actor/huggingface"
echo "🚀 Starting Trained Model (vLLM on port 8001)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $TRAINED_MODEL \
    --served-model-name "trained-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.35 \
    --port 8001 > vllm_trained.log 2>&1 &

# 5. 等待两个模型启动
echo "⏳ Waiting for models to start..."
timeout=300
elapsed=0
while true; do
    if grep -q "Uvicorn running on" vllm_base.log && grep -q "Uvicorn running on" vllm_trained.log; then
        echo "\n✅ Both models started!"
        break
    fi
    sleep 5
    elapsed=$((elapsed+5))
    if [ $elapsed -ge $timeout ]; then
        echo "❌ Models failed to start within $timeout seconds."
        echo "--- Base Model Log ---"
        tail -n 10 vllm_base.log
        echo "--- Trained Model Log ---"
        tail -n 10 vllm_trained.log
        exit 1
    fi
    echo -n "."
done

# 6. 运行对比评估脚本
echo "🧪 Running comparative evaluation..."
python inference_validation.py

# 7. 运行 LLM 判分脚本
echo "⚖️ Running LLM Judge..."
python judge_with_llm_agl.py

# 8. 清理
echo "🧹 Cleaning up..."
pkill -9 -f vllm
echo "✅ Evaluation Complete! Check validation_report.txt and validation_llm_judged.parquet for details."
