#!/usr/bin/env bash
# Kev environment on a 1x H100 NVL Ubuntu 24.04 host; safe to re-run.
# Mirrors kev's Modal image: Python 3.13, uv-locked deps, fla 0.5.2 + triton>=3.7.1 (Hopper backward fix, fla#640), causal-conv1d wheel.
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
KEV_REPO="https://github.com/jaredpalmer/kev.git"
KEV_REF="${KEV_REF:-2074cc44256200bb37540103fa4572901faa10f3}"  # the commit every result of 2026-10-27 used
CAUSAL_CONV1D="https://github.com/Dao-AILab/causal-conv1d/releases/download/v1.7.0/causal_conv1d-1.7.0%2Bcu12torch2.8cxx11abiTRUE-cp313-cp313-linux_x86_64.whl"

echo "SETUP_START $(date -Is)"
# /mnt comes back root-owned and empty after every deallocate.
[ -w "$WORK" ] || { sudo -n mkdir -p "$WORK" && sudo -n chown "$(id -u):$(id -g)" "$WORK"; }
mkdir -p "$WORK"/{runs,data,logs,tmp} "$HF_HOME" "$TRITON_CACHE_DIR" "$UV_CACHE_DIR" "$META"/{logs,state}
nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv
df -h / /mnt
free -g | head -2

command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
[ -d "$KEV/.git" ] || git clone --quiet "$KEV_REPO" "$KEV"
cd "$KEV"
git fetch --quiet origin
git checkout --quiet "$KEV_REF"
git rev-parse HEAD | tee "$META/state/kev_commit.txt"

uv sync --extra serve
# Always call .venv/bin/python afterwards: `uv run` would re-sync triton back to the locked 3.4.
# triton 3.9.0 rejects fla 0.5.2's autotune key "BT" at import (2026-10-27); 3.7.1 is the Hopper-safe floor.
uv pip install "flash-linear-attention==0.5.2" "triton==3.7.1"
uv pip install --no-deps "$CAUSAL_CONV1D"

"$PY" - <<'PY'
import torch, transformers, peft, triton, fla, causal_conv1d
print("torch", torch.__version__, "cuda", torch.version.cuda, "gpu", torch.cuda.get_device_name(0), "avail", torch.cuda.is_available())
print("transformers", transformers.__version__, "peft", peft.__version__, "triton", triton.__version__, "fla", fla.__version__)
PY
df -h / /mnt
echo "SETUP_DONE $(date -Is) kev_commit=$(cat "$META/state/kev_commit.txt")"
