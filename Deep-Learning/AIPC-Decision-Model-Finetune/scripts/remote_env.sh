# Sourced by every remote step. / is 99% full (14 GB free on 2026-10-27), so all bulky state lives on the ephemeral /mnt disk.
export WORK=/mnt/aipc
export META="${META:-$HOME/remote-workspaces/aipc-decision}"
export KEV="$WORK/kev"
export PY="$KEV/.venv/bin/python"
export HF_HOME="$WORK/hf-cache"
export TRITON_CACHE_DIR="$WORK/hf-cache/triton-cache"
export UV_CACHE_DIR="$WORK/uv-cache"
export UV_PYTHON_INSTALL_DIR="$WORK/uv-python"
export XDG_CACHE_HOME="$WORK/xdg-cache"
export TMPDIR="$WORK/tmp"
export HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1
export PATH="$HOME/.local/bin:$PATH"
