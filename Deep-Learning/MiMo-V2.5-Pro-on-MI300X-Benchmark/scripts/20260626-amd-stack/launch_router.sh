#!/bin/bash
# launch_router.sh — SGLang PD router
#
# Run this on the PREFILL node after both P and D servers are ready.
#
# Author: Xinyu Wei (Microsoft AI GBB)

# Defaults are the verified IB IPs for the current Azure MI300X pair.
# Override with environment variables when running on a different VM pair.
PREFILL_IB_IP="${PREFILL_IB_IP:-172.16.1.26}"
DECODE_IB_IP="${DECODE_IB_IP:-172.16.1.122}"
LOG_DIR="${LOG_DIR:-/data/bench_ep8_full}"

mkdir -p "$LOG_DIR"

echo "=== Launching SGLang PD Router ==="
echo "Prefill: http://$PREFILL_IB_IP:30000"
echo "Decode:  http://$DECODE_IB_IP:30001"

python3 -m sglang_router.launch_router \
  --pd-disaggregation \
  --prefill "http://$PREFILL_IB_IP:30000" \
  --decode "http://$DECODE_IB_IP:30001" \
  --host 0.0.0.0 --port 40000 \
  2>&1 | tee "$LOG_DIR/router.log"
