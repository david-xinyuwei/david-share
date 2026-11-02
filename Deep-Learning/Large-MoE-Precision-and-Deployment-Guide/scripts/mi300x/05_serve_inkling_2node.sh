#!/bin/bash
# 05_serve_inkling_2node.sh <head|worker> — Inkling BF16 on 2 nodes x 8 MI300X with Ray.
#   node 1 (worker) first:   HEAD_IP=<node0 private ip> sudo -E bash scripts/mi300x/05_serve_inkling_2node.sh worker
#   node 0 (head)   ~30 s later:  HEAD_IP=<node0 private ip> sudo -E bash scripts/mi300x/05_serve_inkling_2node.sh head
# Both nodes need the full Inkling snapshot in $HF_CACHE (03_download.sh on each node).
# Follow on node 0:  tail -f $MOE_ROOT/logs/05_serve_inkling_head.log ; ready when `curl -s localhost:8000/health` is 200
# (observed 2026-11-02, LAYOUT=pp: weights 109.5 / 116.1 GiB per GPU on the two pipeline stages, ready ~10 min after
#  the head starts including a cold weight load).
#
# LAYOUT=pp (default)  TP8 x PP2: one pipeline stage per node, no DP, no EP.  <- the layout that passed all smoke requests
# LAYOUT=dp            TP8 x DP2 (one DP rank per node) + EP over 16 ranks.   <- the model card's Hopper recipe; on this
#                      image the engine became ready but the first request routed to the remote DP rank hung for 5 min
#                      and killed the engine ("RPC call to sample_tokens timed out"). Kept here so the failure can be
#                      reproduced on a newer image; see VALIDATION.md attempt table.
# TP16 is rejected by the model itself: "sconv SWA cache supports tp_size <= num_kv_heads (8), got 16".
#
# RCCL settings that were required on this image (attempt table in VALIDATION.md):
#   NCCL_NET_GDR_LEVEL=0            GPU Direct RDMA across nodes hung RCCL init ("Peermem not available, falling back
#                                   to GPU Direct RDMA (DMAbuf)" then no "Init COMPLETE"); host-staged IB works.
#   NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1  exclude the two non-compute ports; the 8 compute rails remain.
#   --kernel-config '{"enable_jit_warmup": false}'  skips vLLM's FA4 CuTeDSL warm-up, which imports a CUDA-only
#                                   extension even on ROCm (ImportError: vllm.vllm_flash_attn requires the CUDA ...).
set -u
. "$(dirname "$0")/00_env.sh"
ROLE="${1:?usage: $0 head|worker}"
[ -n "$HEAD_IP" ] || { echo "set HEAD_IP to node 0's private IP"; exit 2; }
MAXLEN="${MAXLEN:-65536}"
LAYOUT="${LAYOUT:-pp}"
if [ "$LAYOUT" = "pp" ]; then
  PAR="--tensor-parallel-size 8 --pipeline-parallel-size 2 --distributed-executor-backend ray"
else
  PAR="--tensor-parallel-size 8 --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-backend ray --enable-expert-parallel"
fi
LOG="$MOE_ROOT/logs/05_serve_inkling_${ROLE}.log"
docker rm -f vllm_inkling >/dev/null 2>&1
echo "SERVE_START=$(date -u +%FT%TZ) role=$ROLE head=$HEAD_IP IMG=$VLLM_IMAGE MID=$INKLING_ID REV=$INKLING_REV MAXLEN=$MAXLEN LAYOUT=$LAYOUT PAR=$PAR" | tee "$LOG"
ENV2="$DOCKER_COMMON --device /dev/infiniband --cap-add SYS_PTRACE \
  -e VLLM_ROCM_USE_AITER=${AITER:-1} \
  -e NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 -e NCCL_IB_PCI_RELAXED_ORDERING=1 -e NCCL_NET_GDR_LEVEL=${GDR_LEVEL:-0} -e GLOO_SOCKET_IFNAME=eth0 \
  -e NCCL_DEBUG=WARN -e RAY_memory_monitor_refresh_ms=0"
if [ "$ROLE" = "worker" ]; then
  docker run -d --name vllm_inkling $ENV2 "$VLLM_IMAGE" bash -lc "ray start --address=$HEAD_IP:6379 --num-gpus=8 --block" >> "$LOG" 2>&1
else
  docker run -d --name vllm_inkling $ENV2 "$VLLM_IMAGE" bash -lc "
    ray start --head --node-ip-address=$HEAD_IP --port=6379 --num-gpus=8 --dashboard-host=0.0.0.0 &&
    for i in \$(seq 1 60); do n=\$(ray status 2>/dev/null | grep -c 'node_'); [ \"\$n\" -ge 2 ] && break; sleep 5; done; ray status;
    vllm serve $INKLING_ID --revision $INKLING_REV --host 0.0.0.0 --port 8000 --served-model-name inkling-bf16 \
      --trust-remote-code --dtype bfloat16 --tokenizer-mode inkling --reasoning-parser inkling \
      $PAR \
      --max-model-len $MAXLEN --gpu-memory-utilization 0.90 --max-num-seqs 16 --max-num-batched-tokens 16384 \
      --enable-chunked-prefill --distributed-timeout-seconds 3600 \
      --kernel-config '{\"enable_jit_warmup\": false}'" >> "$LOG" 2>&1
fi
echo "CONTAINER=$(docker ps -q -f name=vllm_inkling)" | tee -a "$LOG"
nohup docker logs -f vllm_inkling >> "$LOG" 2>&1 &
echo "FOLLOW_PID=$!" | tee -a "$LOG"
# If the worker log shows "GCS returned an authentication error" right after the head started, the worker raced the
# head's GCS start-up: re-run this script with `worker` once the head log shows "Ray runtime started".
