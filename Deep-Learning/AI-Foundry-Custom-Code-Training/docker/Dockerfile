# syntax=docker/dockerfile:1
# The managed NC96ads_A100_v4 node exposes driver 570.195.03 (CUDA 12.8 max).
# Among the published acft-rft-training tags tested on that node, :15 is the one
# whose torch build uses CUDA 12.8. The digest is the exact base pulled by the
# successful compatibility build recorded in evidence/image-build.json.
ARG BASE_IMAGE=mcr.microsoft.com/azureml/curated/acft-rft-training:15@sha256:38f3766a5056d43a0be699986ad3613cec0d247405455046346c2051d62f65ac
FROM ${BASE_IMAGE}

ARG VERL_VERSION=0.7.1
ARG ACCELERATE_VERSION=1.14.0

# Both packages are pure Python in this image. --no-deps is intentional: dependency
# resolution must not replace the working torch/vLLM/CUDA stack inherited from :15.
RUN python -m pip install --no-cache-dir --no-deps \
      "verl==${VERL_VERSION}" "accelerate==${ACCELERATE_VERSION}"

COPY docker/verify_stack.py /opt/cct/verify_stack.py
COPY patches /opt/cct/patches

# Fail before patching if the package versions do not close the transformers-v5 /
# accelerate compatibility gap. Then apply and read back both fail-closed patches.
RUN python /opt/cct/verify_stack.py && \
    python /opt/cct/patches/01-fsdp2-set-guard/apply.py && \
    python /opt/cct/patches/01-fsdp2-set-guard/verify.py && \
    python /opt/cct/patches/02-dp-actor-out-of-place/apply.py && \
    python /opt/cct/patches/02-dp-actor-out-of-place/verify.py

# The build host has no GPU. This gate verifies package identity and compiled CUDA;
# torch.cuda.is_available() is deliberately left for the real-node preflight.
RUN python - <<'PY'
from importlib import metadata
import torch
print(
    "CCT_IMAGE_READY",
    f"verl={metadata.version('verl')}",
    f"accelerate={metadata.version('accelerate')}",
    f"torch={torch.__version__}",
    f"compiled_cuda={torch.version.cuda}",
)
assert metadata.version("verl") == "0.7.1"
assert metadata.version("accelerate") == "1.14.0"
assert torch.version.cuda == "12.8"
PY
