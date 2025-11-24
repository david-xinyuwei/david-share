#!/bin/bash
# 验证 A10 环境和端到端训练流程的脚本

# 1. 清理环境
echo "🧹 Cleaning up GPU processes..."
pkill -9 -f python
sleep 2
nvidia-smi

# 2. 设置环境变量
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# 3. 激活 Conda 环境 (确保使用正确的 python)
# 注意：在脚本中 source conda.sh 是必要的
source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate agentL

echo "🐍 Python path: $(which python)"
echo "📦 Python version: $(python --version)"

# 4. 检查依赖 (可选，用于调试)
# pip list | grep vllm
# pip list | grep agentlightning

# 5. 运行训练
echo "🚀 Starting training verification with 0.5B model..."
# 使用 nohup 运行，并将日志输出到 verification.log
nohup python -u train_math_agent_vllm.py > verification.log 2>&1 &

# 6. 获取 PID 并监控
PID=$!
echo "✅ Training started with PID: $PID"
echo "📄 Logging to verification.log"
echo "👀 Tailing log (Ctrl+C to stop viewing, training will continue)..."
sleep 2
tail -f verification.log
