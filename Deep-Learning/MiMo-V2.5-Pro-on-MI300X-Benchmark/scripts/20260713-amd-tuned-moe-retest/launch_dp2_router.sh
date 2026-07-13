#!/bin/bash
# launch_dp2_router.sh — SGLang DP=2 router
#
# Run this on the node0 after node0 and node1 servers are ready.
#
# Author: Xinyu Wei (Microsoft AI GBB)

set -euo pipefail

Node0_IP="${Node0_IP:?Set Node0_IP to the first prefill node IB address}"
Node1_IP="${Node1_IP:?Set Node1_IP to the second prefill node IB address}"
LOG_DIR="${LOG_DIR:-/data/bench_tp8_dp2_noep}"

mkdir -p "$LOG_DIR"

echo "=== Launching SGLang PD Router ==="
echo "Node0: http://$Node0_IP:30000"
echo "Node1: http://$Node1_IP:30001"

python3 -m sglang_router.launch_router \
  --worker-urls "http://${Node0_IP}:30000" "http://${Node1_IP}:30001" \
  --host 0.0.0.0 --port 40000 \
  2>&1 | tee "$LOG_DIR/dp_router.log"
