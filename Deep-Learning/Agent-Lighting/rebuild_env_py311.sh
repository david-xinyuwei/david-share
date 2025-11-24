#!/bin/bash
set -e

echo "🔧 正在重建 Python 3.11 环境..."

# 1. 删除旧环境
echo "📦 删除旧的 agentL 环境..."
source ~/anaconda3/etc/profile.d/conda.sh
conda env remove -n agentL -y || true

# 2. 创建新环境 (Python 3.11)
echo "🐍 创建 Python 3.11 环境..."
conda create -n agentL python=3.11 -y

# 3. 激活环境
conda activate agentL

# 4. 安装 PyTorch 2.8.0 (CUDA 12.8)
echo "🔥 安装 PyTorch 2.8.0+cu128..."
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128

# 5. 安装 vLLM 0.10.2
echo "⚡ 安装 vLLM 0.10.2..."
pip install vllm==0.10.2

# 6. 安装 VERL 0.5.0
echo "🤖 安装 VERL 0.5.0..."
pip install verl==0.5.0

# 7. 安装 Agent Lightning
echo "⚡ 安装 Agent Lightning..."
cd "$(dirname "$0")"
pip install -e .

# 8. 安装其他依赖
echo "📦 安装额外依赖..."
pip install openai pandas pyarrow huggingface_hub hydra-core datasets opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp

# 9. 验证安装
echo ""
echo "✅ 环境重建完成！版本信息："
python --version
python -c 'import torch; print("PyTorch:", torch.__version__)'
python -c 'import vllm; print("vLLM:", vllm.__version__)'
python -c 'import verl; print("VERL:", verl.__version__)'
python -c 'import ray; print("Ray:", ray.__version__)'
python -c 'import agentlightning; print("AgentLightning:", agentlightning.__version__)'

echo ""
echo "🎉 Python 3.11 环境配置完成！"
