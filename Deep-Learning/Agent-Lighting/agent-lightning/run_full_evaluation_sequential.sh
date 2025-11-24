#!/bin/bash
# 顺序验证 Pipeline: 避免显存不足，依次运行模型

# 1. 清理环境
echo "🧹 Cleaning up..."
fuser -k 8000/tcp
fuser -k 8001/tcp
fuser -k -9 /dev/nvidia0
pkill -9 -f python
pkill -9 -f vllm
rm -f vllm_base.log vllm_trained.log
sleep 5

# 2. 激活环境
# Try to find conda
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
# elif [ -f "/root/anaconda3/etc/profile.d/conda.sh" ]; then
#     source "/root/anaconda3/etc/profile.d/conda.sh"
fi
# conda activate agentL
export HF_ENDPOINT=https://hf-mirror.com

# ==================== 阶段 1: 评估基础模型 ====================
# 优先使用本地下载的模型路径
if [ -d "Qwen/Qwen2.5-3B-Instruct" ]; then
    BASE_MODEL="$(pwd)/Qwen/Qwen2.5-3B-Instruct"
elif [ -d "$HOME/agent-lightning/Qwen/Qwen2.5-3B-Instruct" ]; then
    BASE_MODEL="$HOME/agent-lightning/Qwen/Qwen2.5-3B-Instruct"
# elif [ -d "/root/agent-lightning/Qwen/Qwen2.5-3B-Instruct" ]; then
#     BASE_MODEL="/root/agent-lightning/Qwen/Qwen2.5-3B-Instruct"
else
    BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"
fi

echo "🚀 [Phase 1] Starting Base Model (vLLM on port 8000)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $BASE_MODEL \
    --served-model-name "base-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.8 \
    --port 8000 > vllm_base.log 2>&1 &

# 等待启动
echo "⏳ Waiting for Base Model..."
timeout=300
elapsed=0
while true; do
    if grep -q "Uvicorn running on" vllm_base.log || grep -q "Application startup complete" vllm_base.log; then
        echo "\n✅ Base Model started!"
        break
    fi
    if grep -q "Traceback" vllm_base.log || grep -q "CUDA out of memory" vllm_base.log || grep -q "Address already in use" vllm_base.log; then
        echo "\n❌ Base Model crashed!"
        tail -n 20 vllm_base.log
        exit 1
    fi
    sleep 5
    elapsed=$((elapsed+5))
    if [ $elapsed -ge $timeout ]; then
        echo "❌ Base Model failed to start."
        tail -n 20 vllm_base.log
        exit 1
    fi
    echo -n "."
done

# 运行评估
echo "🧪 Running Base Model evaluation..."
python inference_validation_sequential.py base

# 停止模型
echo "🛑 Stopping Base Model..."
fuser -k 8000/tcp
fuser -k -9 /dev/nvidia0
pkill -9 -f vllm
sleep 10

# ==================== 阶段 2: 评估训练后模型 ====================
TRAINED_MODEL="$(pwd)/checkpoints/AgentLightningTutorial/math_agent_3b_h100_v4_deepthink/global_step_100/actor/huggingface"
echo "🚀 [Phase 2] Starting Trained Model (vLLM on port 8001)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $TRAINED_MODEL \
    --served-model-name "trained-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.8 \
    --port 8001 > vllm_trained.log 2>&1 &

# 等待启动
echo "⏳ Waiting for Trained Model..."
elapsed=0
while true; do
    if grep -q "Uvicorn running on" vllm_trained.log || grep -q "Application startup complete" vllm_trained.log; then
        echo "\n✅ Trained Model started!"
        break
    fi
    if grep -q "Traceback" vllm_trained.log || grep -q "CUDA out of memory" vllm_trained.log || grep -q "Address already in use" vllm_trained.log; then
        echo "\n❌ Trained Model crashed!"
        tail -n 20 vllm_trained.log
        exit 1
    fi
    sleep 5
    elapsed=$((elapsed+5))
    if [ $elapsed -ge $timeout ]; then
        echo "❌ Trained Model failed to start."
        tail -n 20 vllm_trained.log
        exit 1
    fi
    echo -n "."
done

# 运行评估
echo "🧪 Running Trained Model evaluation..."
python inference_validation_sequential.py trained

# 停止模型
echo "🛑 Stopping Trained Model..."
fuser -k 8001/tcp
fuser -k -9 /dev/nvidia0
pkill -9 -f vllm
sleep 5

# ==================== 阶段 3: 生成对比报告 ====================
echo "📊 Generating Comparison Report..."
python inference_validation_sequential.py compare

echo "✅ Sequential Evaluation Complete! Check validation_report.txt"
