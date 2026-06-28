#!/usr/bin/env bash
set -euo pipefail

WORKDIR=/root/mtp-dflash-repro
REPO_DIR="$WORKDIR/llama.cpp"
LOGDIR="$WORKDIR/logs"
mkdir -p "$WORKDIR" "$LOGDIR"

TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOGDIR/llamacpp_build_${TS}.log"

exec > >(tee "$LOG") 2>&1

echo "started_at=$(date -Is)"
echo "log=$LOG"
echo "workdir=$WORKDIR"
echo "repo_dir=$REPO_DIR"
echo "cuda_nvcc=$(/usr/local/cuda/bin/nvcc --version | tail -1)"
echo "cmake=$(cmake --version | head -1)"
echo "ninja=$(ninja --version || true)"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$REPO_DIR"
fi

cd "$REPO_DIR"
current_branch=$(git branch --show-current)
git fetch --depth 1 origin "$current_branch"
git pull --ff-only
echo "llama_cpp_commit=$(git rev-parse HEAD)"

export PATH=/usr/local/cuda/bin:$PATH
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON \
  -DLLAMA_OPENSSL=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=90

cmake --build build --target llama-server -j "$(nproc)"

build/bin/llama-server --version
echo "finished_at=$(date -Is)"