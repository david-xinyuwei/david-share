#!/bin/bash
# 完整验证 Pipeline: 启动基础模型 -> 启动训练后模型 -> 运行对比评估

# 1. 清理环境
echo "🧹 Cleaning up..."
pkill -9 -f python
pkill -9 -f vllm
sleep 2

# 2. 激活环境
# Try to find conda
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
# elif [ -f "/root/anaconda3/etc/profile.d/conda.sh" ]; then
#     source "/root/anaconda3/etc/profile.d/conda.sh"
fi
# conda activate agentL

# 3. 启动基础模型 (Port 8000)
if [ -d "Qwen/Qwen2.5-3B-Instruct" ]; then
    BASE_MODEL="$(pwd)/Qwen/Qwen2.5-3B-Instruct"
elif [ -d "$HOME/agent-lightning/Qwen/Qwen2.5-3B-Instruct" ]; then
    BASE_MODEL="$HOME/agent-lightning/Qwen/Qwen2.5-3B-Instruct"
# elif [ -d "/root/agent-lightning/Qwen/Qwen2.5-3B-Instruct" ]; then
#     BASE_MODEL="/root/agent-lightning/Qwen/Qwen2.5-3B-Instruct"
else
    BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"
fi

echo "🚀 Starting Base Model (vLLM on port 8000)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $BASE_MODEL \
    --served-model-name "base-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.35 \
    --port 8000 > vllm_base.log 2>&1 &

# 4. 启动训练后模型 (Port 8001)
# 注意：这里使用我们刚刚转换好的 Checkpoint
TRAINED_MODEL="$(pwd)/checkpoints/AgentLightningTutorial/math_agent_3b_h100_v4_deepthink/global_step_100/actor/huggingface"
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

# 7. 清理
echo "🧹 Cleaning up..."
pkill -9 -f vllm
echo "✅ Evaluation Complete! Check validation_report.txt for details."
