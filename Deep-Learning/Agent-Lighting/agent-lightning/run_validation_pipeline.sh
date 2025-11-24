#!/bin/bash
# 验证 Pipeline: 转换 Checkpoint -> 启动 vLLM -> 运行推理

# 1. 清理环境
echo "🧹 Cleaning up..."
pkill -9 -f python
pkill -9 -f vllm
sleep 2

# 2. 激活环境
# source /root/anaconda3/etc/profile.d/conda.sh
# conda activate agentL

# 3. 转换 Checkpoint
echo "🔄 Converting checkpoint..."
python convert_checkpoint.py

# 4. 启动 vLLM
MODEL_PATH="${MODEL_PATH:-$(pwd)/checkpoints/AgentLightningTutorial/math_agent_0.5b_3epochs_verified/global_step_360/actor/huggingface_converted}"
echo "🚀 Starting vLLM server with model: $MODEL_PATH"
nohup python -m vllm.entrypoints.openai.api_server \
    --model $MODEL_PATH \
    --served-model-name $MODEL_PATH \
    --trust-remote-code \
    --dtype float16 \
    --gpu-memory-utilization 0.5 \
    --port 8000 > vllm_validation.log 2>&1 &

# 5. 等待 vLLM 启动
echo "⏳ Waiting for vLLM to start..."
timeout=300
elapsed=0
while ! grep -q "Uvicorn running on" vllm_validation.log; do
    sleep 5
    elapsed=$((elapsed+5))
    if [ $elapsed -ge $timeout ]; then
        echo "❌ vLLM failed to start within $timeout seconds."
        cat vllm_validation.log
        exit 1
    fi
    echo -n "."
done
echo "\n✅ vLLM started!"

# 6. 运行推理验证
echo "🧪 Running inference verification..."
python inference_verification.py

# 7. 清理
echo "🧹 Cleaning up..."
pkill -9 -f vllm
echo "✅ Validation Pipeline Complete!"
