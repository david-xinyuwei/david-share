#!/bin/bash
# 07_rccl_probe.sh <node_rank 0|1> <variant> — 16-rank RCCL all_reduce across the two nodes, inside the vLLM image,
# without vLLM. Use it before a two-node serve to separate "RCCL/InfiniBand works" from "the model works".
#   on node 0:  HEAD_IP=<node0 ip> sudo -E bash scripts/mi300x/07_rccl_probe.sh 0 nogdr
#   on node 1:  HEAD_IP=<node0 ip> sudo -E bash scripts/mi300x/07_rccl_probe.sh 1 nogdr     (start within ~30 s)
# variants:
#   gdr    default GPU Direct RDMA          -> hung (timeout 300 s) on this image, 2026-11-02
#   nogdr  NCCL_NET_GDR_LEVEL=0 (host-staged IB) -> RCCL_PROBE_OK=True world=16 avg_allreduce_ms=2.4 busbw_GBps=52.4
# Expected PASS line from node 0:  RCCL_PROBE_OK=True world=16 ... ; PROBE_EXIT=0
set -u
. "$(dirname "$0")/00_env.sh"
NR="${1:?node rank 0|1}"; V="${2:-nogdr}"
[ -n "$HEAD_IP" ] || { echo "set HEAD_IP to node 0's private IP"; exit 2; }
case "$V" in
  gdr)   ENVV="-e NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 -e NCCL_IB_PCI_RELAXED_ORDERING=1 -e GLOO_SOCKET_IFNAME=eth0" ;;
  nogdr) ENVV="-e NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 -e NCCL_IB_PCI_RELAXED_ORDERING=1 -e GLOO_SOCKET_IFNAME=eth0 -e NCCL_NET_GDR_LEVEL=0" ;;
  *) echo "unknown variant $V"; exit 2 ;;
esac
LOG="$MOE_ROOT/logs/07_rccl_probe_${V}_node${NR}.log"
echo "PROBE_START=$(date -u +%FT%TZ) node_rank=$NR variant=$V" | tee "$LOG"
timeout 300 docker run --rm --name rcclprobe --network host --ipc host --device /dev/kfd --device /dev/dri --device /dev/infiniband \
  --ulimit memlock=-1:-1 --shm-size 16g -v "$(cd "$(dirname "$0")" && pwd)":/r $ENVV -e NCCL_DEBUG=WARN \
  "$VLLM_IMAGE" torchrun --nnodes=2 --nproc_per_node=8 --node_rank="$NR" --master_addr="$HEAD_IP" --master_port=29500 /r/07_rccl_probe.py >> "$LOG" 2>&1
echo "PROBE_EXIT=$? PROBE_END=$(date -u +%FT%TZ)" | tee -a "$LOG"
grep -E "RCCL_PROBE_OK|Error|Timeout|timed out|NCCL WARN" "$LOG" | head -n 6 | cut -c1-220
