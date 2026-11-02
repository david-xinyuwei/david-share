#!/bin/bash
# 00_env.sh — shared settings for the MI300X BF16 run. Source it; do not execute.
# Every other script in this directory starts with:  . "$(dirname "$0")/00_env.sh"
#
# Tested 2026-11-02 on Azure Standard_ND96isr_MI300X_v5 (8x MI300X 192 GB, 8x 400 Gb/s InfiniBand) with the
# marketplace image microsoft-dsvm:ubuntu-hpc:2404-rocm (Ubuntu 24.04.5, kernel 6.8.0-1067-azure, ROCm 6.4.4 host).
# Values here are the ones that produced the evidence in ../../data/mi300x-run/; change them deliberately.

# Work root on the node (logs, evidence, venv). Must be writable by the login user; sudo is used for Docker only.
export MOE_ROOT="${MOE_ROOT:-$HOME/moe-run}"

# Fast local scratch for weights and container images. On ND96isr_MI300X_v5 this is the 8x NVMe RAID0 created by
# 01_preflight.sh (28 TB, ephemeral: contents are lost on deallocate). Use a persistent path on other machines.
export MOE_SCRATCH="${MOE_SCRATCH:-/mnt/nvme}"
export HF_CACHE="${HF_CACHE:-$MOE_SCRATCH/hf}"

# Container image (digest observed on 2026-11-02: imageid sha256:e0ea9a10b729573ea8598bdc073bda0ea382fe1037eec7c0761b6fa7f46baaf4).
# vLLM 0.29.1.dev0+g98dff2a81, torch 2.13.0+rocm10.1.0, Triton 3.8.0, aiter, Ray 2.59.0, RCCL 2.30.7.
export VLLM_IMAGE="${VLLM_IMAGE:-rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0}"

# Pinned model revisions (same as data/model-evidence.json and data/tensor-census/).
export NEMOTRON_ID="nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16"
export NEMOTRON_REV="77df655d5e9f8362164ed14dd8b48f8bce657498"
export INKLING_ID="thinkingmachines/Inkling"
export INKLING_REV="828496eeae4c243ff1a22f7f28ff83694f2f7bc9"
# Muse Spark Open BF16 is gated: accept the Muse Model License on the model page first (approval took about one
# hour on 2026-11-02) and put the token in ~/.cache/huggingface/token on the download host. 65 safetensors, 1.64 TB.
export MUSE_ID="meta-models/Muse-Spark-Open-816B-A42B"
export MUSE_REV="0fb02478b02565b2ce7fc57e6051c91172774ac9"
# The Muse architecture is not in rocm/vllm 0.29; the vLLM recipe ships it in this image (11.3 GB, pushed 2026-10-15).
export MUSE_IMAGE="${MUSE_IMAGE:-vllm/vllm-openai-rocm:muse-spark-open}"

# Two-node runs: private IP of the Ray head node (node 0). Set it on BOTH nodes.
export HEAD_IP="${HEAD_IP:-}"

# Docker flags common to every container in this run.
# --device /dev/infiniband is added only by the two-node script.
export DOCKER_COMMON="--network host --ipc host --device /dev/kfd --device /dev/dri --ulimit memlock=-1:-1 --shm-size 64g \
  -v $HF_CACHE:/hf -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 -e VLLM_LOGGING_LEVEL=INFO -e VLLM_WORKER_MULTIPROC_METHOD=spawn"

mkdir -p "$MOE_ROOT/logs" "$MOE_ROOT/evidence"
