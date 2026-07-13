#!/bin/bash
# launch_dp2_router.sh — SGLang DP=2 router
#
# Run this on the node0 after node0 and node1 servers are ready.
#
# Author: Xinyu Wei (Microsoft AI GBB)

set -euo pipefail

Node0_IP="${Node0_IP:?Set Node0_IP to the first prefill node IB address}"
Node1_IP="${Node1_IP:?Set Node1_IP to the second prefill node IB address}"
LOG_DIR="${LOG_DIR:-/data/mimo-tuned-expanded/rep-1/dp2/service}"
ROUTER_HEALTH_CHECK_TIMEOUT_SECONDS="${ROUTER_HEALTH_CHECK_TIMEOUT_SECONDS:-30}"
ROUTER_HEALTH_CHECK_ENDPOINT="${ROUTER_HEALTH_CHECK_ENDPOINT:-/server_info}"

mkdir -p "$LOG_DIR"

echo "=== Launching SGLang PD Router ==="
echo "Node0: http://$Node0_IP:30000"
echo "Node1: http://$Node1_IP:30001"

python3 -m sglang_router.launch_router \
  --worker-urls "http://${Node0_IP}:30000" "http://${Node1_IP}:30001" \
  --policy round_robin \
  --health-check-timeout-secs "$ROUTER_HEALTH_CHECK_TIMEOUT_SECONDS" \
  --health-check-endpoint "$ROUTER_HEALTH_CHECK_ENDPOINT" \
  --host 0.0.0.0 --port 40000 \
  2>&1 | tee "$LOG_DIR/router_outer.log"
