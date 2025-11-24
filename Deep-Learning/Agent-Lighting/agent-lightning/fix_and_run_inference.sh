#!/bin/bash

# 修复检查点并启动推理服务
# 使用方法: bash fix_and_run_inference.sh

set -e

echo "🔧 修复检查点配置..."

# 1. 复制必要的配置文件
# 尝试查找模型目录，如果找不到则使用默认路径
CACHE_DIR="${HF_HOME:-$HOME/.cache/huggingface}"
BASE_MODEL_DIR=$(find "$CACHE_DIR/hub/models--Qwen--Qwen2.5-0.5B-Instruct" -name 'config.json' -type f 2>/dev/null | head -1 | xargs dirname)

if [ -z "$BASE_MODEL_DIR" ]; then
    echo "⚠️ 警告: 未找到基础模型目录，请确保已下载模型。"
    BASE_MODEL_DIR="Qwen/Qwen2.5-0.5B-Instruct" # Fallback
fi

CHECKPOINT_DIR="$(pwd)/checkpoints/AgentLightningTutorial/math_agent/global_step_1"

echo "📂 源模型目录: $BASE_MODEL_DIR"
echo "📂 目标检查点目录: $CHECKPOINT_DIR"

# 复制所有必要的配置文件
if [ -d "$BASE_MODEL_DIR" ]; then
    cp "$BASE_MODEL_DIR"/*.json "$CHECKPOINT_DIR/" 2>/dev/null || true
    cp "$BASE_MODEL_DIR"/tokenizer* "$CHECKPOINT_DIR/" 2>/dev/null || true
    cp "$BASE_MODEL_DIR"/*.txt "$CHECKPOINT_DIR/" 2>/dev/null || true
    cp "$BASE_MODEL_DIR"/*.model "$CHECKPOINT_DIR/" 2>/dev/null || true
    echo "✅ 配置文件已复制"
else
    echo "⚠️ 源目录不存在，跳过复制"
fi

ls -la "$CHECKPOINT_DIR"

# 2. 停止旧的 vLLM 服务器
echo ""
echo "🛑 停止旧的 vLLM 服务器..."
pkill -f 'vllm.entrypoints.openai.api_server' || true
sleep 3

# 3. 启动新的 vLLM 服务器
echo ""
echo "🚀 启动 vLLM 服务器 (后台运行)..."
# cd /root/agent-lightning # Removed hardcoded path

nohup python -m vllm.entrypoints.openai.api_server \
  --model "$CHECKPOINT_DIR" \
  --port 8001 \
  --trust-remote-code \
  --gpu-memory-utilization 0.8 \
  --dtype float16 \
  --api-key "EMPTY" \
  > vllm_inference.log 2>&1 &

VLLM_PID=$!
echo "✅ vLLM 服务器已启动 (PID: $VLLM_PID)"

# 4. 等待服务器启动
echo "⏳ 等待 70 秒让服务器完全启动..."
sleep 70

# 5. 检查服务器状态
if ps -p $VLLM_PID > /dev/null; then
    echo "✅ vLLM 服务器正在运行"
else
    echo "❌ vLLM 服务器启动失败，查看日志:"
    tail -50 vllm_inference.log
    exit 1
fi

# 6. 运行推理测试
echo ""
echo "============================================================"
echo "🧮 开始推理测试"
echo "============================================================"
echo ""

if [ -f "inference_simple.py" ]; then
    python3 inference_simple.py
else
    echo "⚠️ inference_simple.py not found, skipping inference test"
fi

echo ""
echo "✅ 推理测试完成！"
echo ""
echo "📋 查看完整日志: tail -f $(pwd)/vllm_inference.log"
echo "🛑 停止服务器: pkill -f 'vllm.entrypoints.openai.api_server'"
