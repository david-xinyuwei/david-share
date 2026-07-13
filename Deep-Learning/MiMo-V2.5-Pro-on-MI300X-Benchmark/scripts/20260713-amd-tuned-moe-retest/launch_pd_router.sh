#!/bin/bash
# launch_pd_router.sh — SGLang PD router
#
# Run this on the PREFILL node after both P and D servers are ready.
#
# Author: Xinyu Wei (Microsoft AI GBB)

set -euo pipefail

PREFILL_IB_IP="${PREFILL_IB_IP:?Set PREFILL_IB_IP to the prefill node IB address}"
DECODE_IB_IP="${DECODE_IB_IP:?Set DECODE_IB_IP to the decode node IB address}"
LOG_DIR="${LOG_DIR:-/data/bench_tp8_noep_mooncake}"

mkdir -p "$LOG_DIR"

echo "=== Launching SGLang PD Router ==="
echo "Prefill: http://$PREFILL_IB_IP:30000"
echo "Decode:  http://$DECODE_IB_IP:30001"

python3 -m sglang_router.launch_router \
  --pd-disaggregation \
  --prefill "http://${PREFILL_IB_IP}:30000" \
  --decode "http://${DECODE_IB_IP}:30001" \
  --host 0.0.0.0 --port 40000 \
  2>&1 | tee "$LOG_DIR/router.log"
