#!/usr/bin/env bash
# llama.cpp on the VM for GGUF export of the fine-tuned checkpoints: same tag as the Surface binaries (b11935),
# CPU-only llama-quantize (the recipe of ggml-org/convert), and a separate venv for convert_hf_to_gguf.py so the
# training venv is never touched. Runs on CPU while the GPU trains. Idempotent.
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
L="$WORK/llama.cpp"
LV="$WORK/llama-venv"
TAG=b11935
[ -d "$L/.git" ] || git clone --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp.git "$L"
echo "LLAMA_COMMIT $(git -C "$L" rev-parse HEAD)"
[ -x "$LV/bin/python" ] || uv venv --python 3.12 "$LV"
uv pip install --python "$LV/bin/python" -r "$L/requirements/requirements-convert_hf_to_gguf.txt" cmake
"$LV/bin/python" -c "import torch, transformers, gguf, numpy; print('CONVERT_ENV torch', torch.__version__, 'transformers', transformers.__version__, 'numpy', numpy.__version__)"
"$LV/bin/cmake" -S "$L" -B "$L/build" -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_CURL=OFF > "$WORK/logs/llama-cmake.log" 2>&1
"$LV/bin/cmake" --build "$L/build" -j 12 --target llama-quantize llama-server > "$WORK/logs/llama-build.log" 2>&1
ls -la "$L/build/bin/llama-quantize" "$L/build/bin/llama-server"
"$L/build/bin/llama-server" --version 2>&1 | tail -2
echo "KEV_IN_CONVERTER"
grep -n -i -E "kev|decision|temperature|head\.pt|adapter_model" "$L/convert_hf_to_gguf.py" | head -60
echo "LLAMA_PREP_DONE $(date -Is)"
