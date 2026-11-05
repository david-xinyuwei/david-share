#!/bin/bash
set -euo pipefail

ROLE="${1:?usage: head or worker}"
LAYOUT="${LAYOUT:?set tp, pp, tep, dp, or pd}"
HEAD_IP="${HEAD_IP:?set the node-0 private address}"
NODE_IP="${NODE_IP:?set this node private address}"
RUN_ROOT="${RUN_ROOT:?set the frozen run directory}"
IMAGE="${IMAGE:-vllm-muse-ray:fiveway-20261103}"
MODEL="Qwen/Qwen3-235B-A22B-Instruct-2507"
REVISION="ac9c66cc9b46af7306746a9250f23d47083d689e"
RANK=0
if [ "$ROLE" = worker ]; then RANK=1; fi
NAME="qwen_fiveway_$LAYOUT"
PARALLEL=()
EXTRA_ENV=()
PORT=8000
case "$LAYOUT" in
  tp|tep)
    PARALLEL=(--tensor-parallel-size 16 --nnodes 2 --node-rank "$RANK" --master-addr "$HEAD_IP")
    if [ "$LAYOUT" = tep ]; then PARALLEL+=(--enable-expert-parallel); fi
    if [ "$RANK" = 1 ]; then PARALLEL+=(--headless); fi
    ;;
  pp)
    PARALLEL=(--tensor-parallel-size 8 --pipeline-parallel-size 2 --nnodes 2 --node-rank "$RANK" --master-addr "$HEAD_IP")
    if [ "$RANK" = 1 ]; then PARALLEL+=(--headless); fi
    ;;
  dp)
    PARALLEL=(--tensor-parallel-size 1 --data-parallel-size 16 --data-parallel-size-local 8
      --data-parallel-address "$HEAD_IP" --data-parallel-rpc-port 13345 --data-parallel-backend mp --enable-expert-parallel)
    if [ "$RANK" = 1 ]; then PARALLEL+=(--data-parallel-start-rank 8 --headless); fi
    ;;
  pd)
    PARALLEL=(--tensor-parallel-size 8)
    EXTRA_ENV=(-e MC_FORCE_TCP=1)
    if [ "$RANK" = 0 ]; then
      PORT=8001
      PARALLEL+=(--kv-transfer-config '{"kv_connector":"MooncakeConnector","kv_role":"kv_producer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"mooncake_protocol":"tcp"}}')
    else
      PORT=8002
      PARALLEL+=(--kv-transfer-config '{"kv_connector":"MooncakeConnector","kv_role":"kv_consumer","kv_load_failure_policy":"fail","kv_connector_extra_config":{"mooncake_protocol":"tcp"}}')
    fi
    ;;
  *) printf 'Unsupported layout: %s\n' "$LAYOUT" >&2; exit 2 ;;
esac

COMMAND=(vllm serve "$MODEL" --revision "$REVISION" --served-model-name qwen-fiveway-bf16
  --host 0.0.0.0 --port "$PORT" --dtype bfloat16 --distributed-executor-backend mp
  --max-model-len 32768 --max-num-seqs 64 --max-num-batched-tokens 4096
  --gpu-memory-utilization 0.80 --moe-backend triton --attention-backend TRITON_ATTN
  --enable-prefix-caching --enable-chunked-prefill "${PARALLEL[@]}")
if [ "${DRY_RUN:-0}" = 1 ]; then
  printf 'LAYOUT=%s ROLE=%s NAME=%s\n' "$LAYOUT" "$ROLE" "$NAME"
  printf '%q ' "${EXTRA_ENV[@]}"
  printf '%q ' "${COMMAND[@]}"
  printf '\n'
  exit 0
fi

mkdir -p "$RUN_ROOT/$LAYOUT"
if docker container inspect "$NAME" >/dev/null 2>&1; then
  printf 'Container already exists: %s; preserve it and choose a new run.\n' "$NAME" >&2
  exit 2
fi
printf 'START_UTC=%s\nLAYOUT=%s\nROLE=%s\n' "$(date -u +%FT%TZ)" "$LAYOUT" "$ROLE" > "$RUN_ROOT/$LAYOUT/launch-$ROLE.txt"
printf '%q ' "${COMMAND[@]}" >> "$RUN_ROOT/$LAYOUT/launch-$ROLE.txt"
printf '\n' >> "$RUN_ROOT/$LAYOUT/launch-$ROLE.txt"
docker run -d --name "$NAME" --network host --ipc host \
  --device /dev/kfd --device /dev/dri --device /dev/infiniband \
  --ulimit memlock=-1:-1 --shm-size 64g \
  -v /mnt/nvme/hf:/hf -v "$RUN_ROOT:/run-evidence" \
  -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 -e VLLM_USE_RUST_FRONTEND=0 \
  -e VLLM_HOST_IP="$NODE_IP" -e GLOO_SOCKET_IFNAME=eth0 -e NCCL_SOCKET_IFNAME=eth0 \
  -e NCCL_NET_GDR_LEVEL=0 -e NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 \
  -e NCCL_IB_PCI_RELAXED_ORDERING=1 -e NCCL_DEBUG=WARN \
  -e VLLM_MOONCAKE_BOOTSTRAP_PORT=8998 -e VLLM_MOONCAKE_CONNECTOR_TIMEOUT=120 \
  "${EXTRA_ENV[@]}" --entrypoint /usr/local/bin/vllm "$IMAGE" "${COMMAND[@]:1}"