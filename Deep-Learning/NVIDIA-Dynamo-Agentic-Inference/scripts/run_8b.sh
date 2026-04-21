#!/bin/bash
# 8B Benchmark Suite (Qwen3-8B on 2×H100 NVL)
# Author: Xinyu Wei
# Results 1-3: Single GPU, TP=2, Prefix Cache, Dynamo PD, High Concurrency

set -e
MODEL="${MODEL_PATH:-/root/models/Qwen3-8B}"
PORT=8000
LOG="${LOG_DIR:-/root}"

cleanup() { pkill -f sglang 2>/dev/null || true; pkill -f dynamo 2>/dev/null || true; sleep 2; }
wait_server() {
    local t=${1:-120}
    for i in $(seq 1 $t); do curl -s http://localhost:$PORT/v1/models >/dev/null 2>&1 && echo "Ready ${i}s" && return 0; sleep 1; done
    echo "ERROR: not ready after ${t}s"; return 1
}
bench() { python3 -m sglang.bench_serving --backend "$1" --port $PORT --model "$MODEL" --dataset-name random --random-input-len 1024 --random-output-len 256 --num-prompts "$2" --request-rate "$3" --seed 1 $4 2>&1 | tee "$LOG/$5"; }

echo "=== Phase 1: Single GPU Baseline (50@5) ==="
cleanup
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 &>/tmp/sglang.log &
wait_server 120
bench sglang 50 5 "" benchmark_phase1_baseline.log
cleanup

echo "=== Phase 2: TP=2 (50@5) ==="
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 --tp 2 &>/tmp/sglang.log &
wait_server 120
bench sglang 50 5 "" benchmark_phase2_tp2.log
cleanup

echo "=== Phase 3: Prefix Cache cold/warm/flush (50@5) ==="
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 --tp 2 &>/tmp/sglang.log &
wait_server 120
bench sglang 50 5 "" benchmark_phase3_cold.log
bench sglang 50 5 "" benchmark_phase3_warm.log
bench sglang 50 5 "--flush-cache" benchmark_phase4_flush.log
cleanup

echo "=== Phase 5: Dynamo PD 1P1D (50@5) ==="
nats-server -js &>/tmp/nats.log &
etcd &>/tmp/etcd.log &
sleep 2
python3 -m dynamo.frontend --router-mode kv --router-reset-states &>/tmp/frontend.log &
sleep 3
CUDA_VISIBLE_DEVICES=0 DYN_SYSTEM_PORT=8081 python3 -m dynamo.sglang \
    --model-path "$MODEL" --served-model-name Qwen3-8B --page-size 64 --tp 1 \
    --disaggregation-mode prefill --host 0.0.0.0 \
    --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
    --disaggregation-transfer-backend nixl &>/tmp/prefill.log &
CUDA_VISIBLE_DEVICES=1 DYN_SYSTEM_PORT=8083 python3 -m dynamo.sglang \
    --model-path "$MODEL" --served-model-name Qwen3-8B --page-size 64 --tp 1 \
    --disaggregation-mode decode --host 0.0.0.0 \
    --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
    --disaggregation-transfer-backend nixl &>/tmp/decode.log &
wait_server 180
bench sglang-oai-chat 50 5 "--model Qwen3-8B --tokenizer $MODEL" benchmark_phase5_dynamo_pd.log
cleanup; pkill -f nats-server 2>/dev/null; pkill -f etcd 2>/dev/null

echo "=== High Concurrency: TP=2 (200@20) ==="
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 --tp 2 &>/tmp/sglang.log &
wait_server 120
bench sglang 200 20 "" benchmark_highload_tp2.log
cleanup

echo "=== High Concurrency: PD (200@20) ==="
nats-server -js &>/tmp/nats.log &
etcd &>/tmp/etcd.log &
sleep 2
python3 -m dynamo.frontend --router-mode kv --router-reset-states &>/tmp/frontend.log &
sleep 3
CUDA_VISIBLE_DEVICES=0 DYN_SYSTEM_PORT=8081 python3 -m dynamo.sglang \
    --model-path "$MODEL" --served-model-name Qwen3-8B --page-size 64 --tp 1 \
    --disaggregation-mode prefill --host 0.0.0.0 \
    --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
    --disaggregation-transfer-backend nixl &>/tmp/prefill.log &
CUDA_VISIBLE_DEVICES=1 DYN_SYSTEM_PORT=8083 python3 -m dynamo.sglang \
    --model-path "$MODEL" --served-model-name Qwen3-8B --page-size 64 --tp 1 \
    --disaggregation-mode decode --host 0.0.0.0 \
    --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
    --disaggregation-transfer-backend nixl &>/tmp/decode.log &
wait_server 180
bench sglang-oai-chat 200 20 "--model Qwen3-8B --tokenizer $MODEL" benchmark_highload_pd.log
cleanup; pkill -f nats-server 2>/dev/null; pkill -f etcd 2>/dev/null

echo "========== 8B All Done =========="
