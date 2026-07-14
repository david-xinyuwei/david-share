#!/bin/bash
# launch_pd_router.sh — SGLang PD router
#
# Run this on the PREFILL node after both P and D servers are ready.
#
# Author: Xinyu Wei (Microsoft AI GBB)

set -euo pipefail

PREFILL_IB_IP="${PREFILL_IB_IP:?Set PREFILL_IB_IP to the prefill node IB address}"
DECODE_IB_IP="${DECODE_IB_IP:?Set DECODE_IB_IP to the decode node IB address}"
LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/onep/service}"
ROUTER_HEALTH_CHECK_TIMEOUT_SECONDS="${ROUTER_HEALTH_CHECK_TIMEOUT_SECONDS:-30}"
ROUTER_HEALTH_CHECK_ENDPOINT="${ROUTER_HEALTH_CHECK_ENDPOINT:-/server_info}"

mkdir -p "$LOG_DIR"

echo "=== Launching SGLang PD Router ==="
echo "Prefill: http://$PREFILL_IB_IP:30000"
echo "Decode:  http://$DECODE_IB_IP:30001"

python3 -m sglang_router.launch_router \
  --pd-disaggregation \
  --prefill "http://${PREFILL_IB_IP}:30000" \
  --decode "http://${DECODE_IB_IP}:30001" \
  --health-check-timeout-secs "$ROUTER_HEALTH_CHECK_TIMEOUT_SECONDS" \
  --health-check-endpoint "$ROUTER_HEALTH_CHECK_ENDPOINT" \
  --host 0.0.0.0 --port 40000 \
  2>&1 | tee "$LOG_DIR/router_outer.log"
