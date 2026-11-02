#!/bin/bash
# 08_serve_muse_2node.sh <head|worker> — Muse Spark Open BF16 (816B, 1.64 TB) on 2 nodes x 8 MI300X with Ray.
#   node 1 (worker) first:   HEAD_IP=<node0 private ip> sudo -E bash scripts/mi300x/08_serve_muse_2node.sh worker
#   node 0 (head)   ~30 s later:  HEAD_IP=<node0 private ip> sudo -E bash scripts/mi300x/08_serve_muse_2node.sh head
# Both nodes need the full BF16 snapshot in $HF_CACHE (03_download.sh with HF_TOKEN set; the repo is gated).
# Follow on node 0:  tail -f $MOE_ROOT/logs/08_serve_muse_head.log ; ready when `curl -s localhost:8000/health` is 200
#
# Image: the Muse architecture is not in rocm/vllm 0.29 (00_env.sh). Two images carry it (2026-11-02):
#   vllm/vllm-openai-rocm:muse-spark-open  the recipe image (MUSE_IMAGE in 00_env.sh). Compiled for gfx950 ONLY
#                                          (PYTORCH_ROCM_ARCH=gfx950; `llvm-objdump --offloading` on every .so shows
#                                          no gfx942 code object). On MI300X (gfx942) attempt 2 loaded the weights
#                                          (104.84 GiB per GPU) and then all 16 ranks segfaulted in
#                                          fused_muse_spark_qknorm_rope_kv_insert_kernel.hip during profiling.
#   vllm/vllm-openai-rocm:v0.33.0          the 2026-11-02 release: same vllm/models/muse_spark tree, compiled for
#                                          gfx90a/gfx942/gfx950/gfx11xx/gfx12xx. This is the base used from attempt 3.
# Neither image has Ray, and vLLM's multi-node executor needs Ray >= 2.43.0 (attempt 1: worker `ray: command not
# found`, head `Failed to import Ray`). Build the derived image on BOTH nodes first (Dockerfile.muse-ray adds
# ray[default]==2.55.1, the version vLLM 0.29.0 pins in requirements/test/rocm.txt):
#   sudo docker build --network host --build-arg BASE=vllm/vllm-openai-rocm:v0.33.0 \
#     -t vllm-muse-ray:0.33.0 -f scripts/mi300x/Dockerfile.muse-ray scripts/mi300x
# MUSE_SERVE_IMAGE below selects it; MUSE_SERVE_IMAGE=vllm-muse-ray:2.55.1 (recipe base + Ray) reproduces the
# gfx950-only segfault, MUSE_SERVE_IMAGE=$MUSE_IMAGE reproduces the missing-Ray failure.
#
# Layout: the recipe validates BF16 only on gfx950 (MI350X/MI355X, 288 GB) where 1.64 TB fits one 8-GPU node (TP8).
# On MI300X (192 GB) one node cannot hold it (1.64 TB / 8 = 205 GB per GPU), so LAYOUT=pp (default) uses the same
# two-node layout that passed for Inkling: TP8 x PP2 (one pipeline stage per node, 1.64 TB / 16 = 103 GB per GPU).
# The recipe says "AMD supports only TP and TP + expert parallel"; PP across nodes is therefore an experiment, and the
# result (pass or the exact error) is the evidence.
# LAYOUT=tep is the recipe's own two-node answer: the command builder's "2x MI300X . Multi-Node Tensor + Expert
# Parallel . BF16" tab (recipes.vllm.ai, recipe updated 2026-10-23) emits `--tensor-parallel-size 16
# --enable-expert-parallel --nnodes 2 --node-rank <0|1> --master-addr $HEAD_IP --distributed-executor-backend mp`,
# i.e. vLLM's multiprocessing multi-node backend without Ray: both nodes run the same `vllm serve`, rank 1 adds
# `--headless` (vllm/entrypoints/cli/serve.py: node_rank_within_dp > 0 -> headless MultiprocExecutor). Deviations
# from the recipe tab, each forced: image (see above), the Python front end (VLLM_USE_RUST_FRONTEND=0; the v0.33.0
# image ships no vllm-rs binary), `--kernel-config '{"enable_jit_warmup": false}'` (same as the passed PP run; the
# FA4 warm-up imports a CUDA-only module on ROCm), and this cluster's RCCL settings plus `--network host`.
#   node 0:  HEAD_IP=<node0 private ip> LAYOUT=tep sudo -E bash scripts/mi300x/08_serve_muse_2node.sh head
#   node 1:  HEAD_IP=<node0 private ip> LAYOUT=tep sudo -E bash scripts/mi300x/08_serve_muse_2node.sh worker   (within ~60 s)
#
# Flags copied from the recipe's AMD BF16 variant (recipes/models/meta-models/Muse-Spark-Open-816B-A42B.yaml):
#   --moe-backend triton --attention-backend ROCM_AITER_FA --dtype bfloat16 --language-model-only
#   --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}' --no-enable-prefix-caching --enable-chunked-prefill
#   env VLLM_ROCM_USE_AITER=1 VLLM_ROCM_MUSE_MOE_REDUCE_DTYPE=bf16 VLLM_USE_BREAKABLE_CUDAGRAPH=1
# plus the RCCL settings that this image/cluster needed for Inkling (NCCL_NET_GDR_LEVEL=0, NCCL_IB_HCA exclusions).
set -u
. "$(dirname "$0")/00_env.sh"
ROLE="${1:?usage: $0 head|worker}"
[ -n "$HEAD_IP" ] || { echo "set HEAD_IP to node 0's private IP"; exit 2; }
MAXLEN="${MAXLEN:-32768}"
LAYOUT="${LAYOUT:-pp}"
MUSE_SERVE_IMAGE="${MUSE_SERVE_IMAGE:-vllm-muse-ray:0.33.0}"
RANK=0; [ "$ROLE" = "worker" ] && RANK=1
if [ "$LAYOUT" = "pp" ]; then
  PAR="--tensor-parallel-size 8 --pipeline-parallel-size 2 --distributed-executor-backend ray"
  GPU_UTIL=0.92; EXTRA=""; ENV_LAYOUT=""
else
  # Recipe tab verbatim: TP16 + EP over the mp backend; rank 1 is headless (no API server, joins rank 0's process group).
  PAR="--tensor-parallel-size 16 --enable-expert-parallel --distributed-executor-backend mp --nnodes 2 --node-rank $RANK --master-addr $HEAD_IP"
  [ "$RANK" = 1 ] && PAR="$PAR --headless"
  GPU_UTIL=0.95; EXTRA="--enable-auto-tool-choice --tool-call-parser muse"
  ENV_LAYOUT="-e NCCL_SOCKET_IFNAME=eth0 -e VLLM_USE_RUST_FRONTEND=0"
fi
LOG="$MOE_ROOT/logs/08_serve_muse_${ROLE}.log"
docker rm -f vllm_muse >/dev/null 2>&1
echo "SERVE_START=$(date -u +%FT%TZ) role=$ROLE rank=$RANK head=$HEAD_IP IMG=$MUSE_SERVE_IMAGE (base $MUSE_IMAGE) MID=$MUSE_ID REV=$MUSE_REV MAXLEN=$MAXLEN LAYOUT=$LAYOUT PAR=$PAR GPU_UTIL=$GPU_UTIL" | tee "$LOG"
ENV2="$DOCKER_COMMON --device /dev/infiniband --cap-add SYS_PTRACE \
  -e VLLM_ROCM_USE_AITER=1 -e VLLM_ROCM_MUSE_MOE_REDUCE_DTYPE=bf16 -e VLLM_USE_BREAKABLE_CUDAGRAPH=1 \
  -e NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 -e NCCL_IB_PCI_RELAXED_ORDERING=1 -e NCCL_NET_GDR_LEVEL=${GDR_LEVEL:-0} -e GLOO_SOCKET_IFNAME=eth0 \
  -e NCCL_DEBUG=WARN -e RAY_memory_monitor_refresh_ms=0 $ENV_LAYOUT"
# The serve command is the same for both layouts and (LAYOUT=tep) for both nodes; only $PAR / $GPU_UTIL / $EXTRA differ.
SERVE="vllm serve $MUSE_ID --revision $MUSE_REV --host 0.0.0.0 --port 8000 --served-model-name muse-spark-open-bf16 \
      --dtype bfloat16 --language-model-only \
      --moe-backend triton --attention-backend ROCM_AITER_FA \
      $PAR \
      --max-model-len $MAXLEN --gpu-memory-utilization $GPU_UTIL --max-num-seqs 32 --max-num-batched-tokens 4096 \
      --no-enable-prefix-caching --enable-chunked-prefill \
      --compilation-config '{\"cudagraph_mode\":\"FULL_AND_PIECEWISE\"}' \
      --kernel-config '{\"enable_jit_warmup\": false}' \
      --reasoning-parser muse $EXTRA --distributed-timeout-seconds 3600"
# This image's ENTRYPOINT is /bin/bash (rocm/vllm's is an entry script), so the command is passed with -c.
if [ "$LAYOUT" != "pp" ]; then
  docker run -d --name vllm_muse $ENV2 --entrypoint /bin/bash "$MUSE_SERVE_IMAGE" -lc "$SERVE" >> "$LOG" 2>&1
elif [ "$ROLE" = "worker" ]; then
  docker run -d --name vllm_muse $ENV2 --entrypoint /bin/bash "$MUSE_SERVE_IMAGE" -lc "ray start --address=$HEAD_IP:6379 --num-gpus=8 --block" >> "$LOG" 2>&1
else
  docker run -d --name vllm_muse $ENV2 --entrypoint /bin/bash "$MUSE_SERVE_IMAGE" -lc "
    ray start --head --node-ip-address=$HEAD_IP --port=6379 --num-gpus=8 --dashboard-host=0.0.0.0 &&
    for i in \$(seq 1 60); do n=\$(ray status 2>/dev/null | grep -c 'node_'); [ \"\$n\" -ge 2 ] && break; sleep 5; done; ray status;
    $SERVE" >> "$LOG" 2>&1
fi
echo "CONTAINER=$(docker ps -q -f name=vllm_muse)" | tee -a "$LOG"
nohup docker logs -f vllm_muse >> "$LOG" 2>&1 &
echo "FOLLOW_PID=$!" | tee -a "$LOG"
