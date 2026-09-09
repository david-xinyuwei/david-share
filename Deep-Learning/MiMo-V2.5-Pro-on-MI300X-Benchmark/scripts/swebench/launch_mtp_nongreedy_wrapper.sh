#!/usr/bin/env bash
set -euo pipefail
NODE_ID="${NODE_ID:?Set NODE_ID}"
RUN_ID="${RUN_ID:?Set RUN_ID}"
MODEL_LOG="${MODEL_LOG:?Set MODEL_LOG}"

export SGLANG_ROOT=/sgl-workspace/sglang_0625
export MEM_FRACTION_STATIC=0.95
export LOG_DIR="$(dirname "$MODEL_LOG")"
export LOG_FILE="$(basename "$MODEL_LOG")"
export RUN_ID

# AMD fix 878fff156 is opt-in; without this the HIP path silently uses the
# greedy verifier and temperature=1.0 has no effect.
export SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1

# Aligned with the no-MTP baseline run (launch_swebench_nomtp_accuracy.sh).
export ROCM_QUICK_REDUCE_QUANTIZATION=NONE
export SGLANG_SCHEDULER_SKIP_ALL_GATHER=1
export SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION=0

mkdir -p "$LOG_DIR"
exec /bin/bash /data/xisun/decode_server_scripts/launch_tp8_noep_aiter_mtp_accuracy.sh
