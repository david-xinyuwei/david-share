#!/bin/bash
# launch_pd_mtp.sh — Launch PD-disaggregated MiMo-V2.5-Pro with MTP/EAGLE on MI300X
#
# Prerequisites:
#   - Two ND96isr_MI300X_v5 VMs in the same VMSS (IB guaranteed)
#   - Docker image: rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510
#   - AMD fork SGLang installed: TianHao65/sglang branch Mimo_mtp_enable
#   - Model downloaded to /data/models/MiMo-V2.5-Pro on BOTH VMs
#   - Mooncake: pip install mooncake-transfer-engine
#
# Usage:
#   1. Edit PREFILL_IB_IP and DECODE_IB_IP below
#   2. Run this script inside the PREFILL node container
#   3. Run launch_decode.sh on the DECODE node container
#   4. Then run launch_router.sh on the PREFILL node container
#
# Author: Xinyu Wei (Microsoft AI GBB)

# Defaults are the verified IB IPs for the current Azure MI300X pair.
# Override with environment variables when running on a different VM pair.
PREFILL_IB_IP="${PREFILL_IB_IP:-172.16.1.26}"
DECODE_IB_IP="${DECODE_IB_IP:-172.16.1.122}"
MODEL_PATH="${MODEL_PATH:-/data/models/MiMo-V2.5-Pro}"
LOG_DIR="${LOG_DIR:-/data/pd_mtp}"

# --- Environment Variables ---
export SGLANG_USE_AITER=1
export SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1
export SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1
export HSA_NO_SCRATCH_RECLAIM=1
export NCCL_DMABUF_ENABLE=0
export TORCH_NCCL_BLOCKING_WAIT=1
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_DISAGGREGATION_THREAD_POOL_SIZE=12
export SGLANG_DISAGGREGATION_BOOTSTRAP_TIMEOUT=5000
export SGLANG_DISAGGREGATION_WAITING_TIMEOUT=5000
export SGLANG_MORI_NUM_MAX_DISPATCH_TOKENS_PER_RANK=16384
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected

mkdir -p "$LOG_DIR"

# --- IB devices: use ALL 8 CX7 400G NICs ---
IB_DEVICES="mlx5_ib0,mlx5_ib1,mlx5_ib2,mlx5_ib3,mlx5_ib4,mlx5_ib5,mlx5_ib6,mlx5_ib7"

echo "=== Launching PREFILL server ==="
echo "IB devices: $IB_DEVICES"
echo "Model: $MODEL_PATH"

python3 -u -m sglang.launch_server \
  --model-path "$MODEL_PATH" \
  --tp-size 8 \
  --host 0.0.0.0 --port 30000 \
  --trust-remote-code \
  --disable-radix-cache \
  --disable-cuda-graph \
  --mem-fraction-static 0.85 \
  --context-length 262144 \
  --max-running-requests 128 \
  --chunked-prefill-size 16384 \
  --attention-backend triton \
  --disaggregation-mode prefill \
  --disaggregation-transfer-backend mooncake \
  --disaggregation-ib-device "$IB_DEVICES" \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --enable-draft-weights-cpu-backup \
  2>&1 | tee "$LOG_DIR/prefill_server.log"
