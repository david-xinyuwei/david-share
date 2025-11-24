#!/bin/bash
set -e

echo "=== 清理运行中的进程 ==="
pkill -f train_agent.py || true
pkill -f vllm || true
ray stop --force || true

echo "=== 激活conda并删除旧环境 ==="
source ~/anaconda3/etc/profile.d/conda.sh
conda deactivate || true
conda env remove -n agentL -y || true

echo "=== 创建新环境 Python 3.10 ==="
conda create -n agentL python=3.10 -y

echo "=== 激活新环境 ==="
conda activate agentL

echo "=== 1. 安装 PyTorch 2.8.0 + CUDA 12.8 ==="
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128

echo "=== 2. 安装 vLLM 0.10.2 (官方推荐版本) ==="
pip install vllm==0.10.2

echo "=== 3. 安装 VERL 0.5.0 (官方推荐版本) ==="
pip install verl==0.5.0

echo "=== 4. 安装 Agent Lightning ==="
cd "$(dirname "$0")"
pip install -e .

echo "=== 5. 安装其他必要依赖 ==="
pip install openai pandas pyarrow huggingface_hub hydra-core datasets

echo "=== 6. 验证安装 ==="
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import vllm; print(f'vLLM: {vllm.__version__}')"
python -c "import verl; print(f'VERL: {verl.__version__}')"
python -c "import ray; print(f'Ray: {ray.__version__}')"
python -c "import agentlightning; print(f'AgentLightning: {agentlightning.__version__}')"

echo ""
echo "=== ✅ 环境重建完成！==="
echo "依赖版本："
echo "  - PyTorch: 2.8.0"
echo "  - vLLM: 0.10.2"
echo "  - VERL: 0.5.0"
echo ""
echo "可以开始训练了！"
