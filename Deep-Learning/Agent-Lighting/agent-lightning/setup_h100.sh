#!/bin/bash
set -e

echo "🚀 Setting up H100 Environment..."

# 1. Install Miniconda if not exists
INSTALL_DIR="$HOME/anaconda3"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "📦 Installing Miniconda to $INSTALL_DIR..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p $INSTALL_DIR
    rm miniconda.sh
    $INSTALL_DIR/bin/conda init
else
    echo "✅ Miniconda already installed at $INSTALL_DIR."
fi

source $INSTALL_DIR/etc/profile.d/conda.sh

# 2. Create Environment
if ! conda info --envs | grep -q "agentL"; then
    echo "🐍 Creating conda environment 'agentL'..."
    conda create -n agentL python=3.11 -y
else
    echo "✅ Environment 'agentL' already exists."
fi

conda activate agentL

# 3. Install Dependencies
# Install dependencies from requirements.txt
pip install -r requirements.txt

# Install flash-attn with specific flags to avoid ABI issues
pip install flash-attn --no-build-isolation

# Install the local package in editable mode
pip install -e .

# 4. Download Model (3B)
echo "📥 Downloading Qwen2.5-3B-Instruct..."
export HF_ENDPOINT=https://hf-mirror.com
# Download to ./Qwen/Qwen2.5-3B-Instruct relative to current directory
mkdir -p Qwen/Qwen2.5-3B-Instruct
huggingface-cli download Qwen/Qwen2.5-3B-Instruct --local-dir Qwen/Qwen2.5-3B-Instruct --local-dir-use-symlinks False

echo "✅ Setup Complete!"
