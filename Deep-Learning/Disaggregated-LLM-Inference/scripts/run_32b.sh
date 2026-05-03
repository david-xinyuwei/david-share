#!/bin/bash
# 32B Benchmark Suite (Qwen2.5-32B-Instruct on 2×H100 NVL)
# Author: Xinyu Wei
# Results 4-5: Baseline, FP8 KV, No Chunked, TP=2, Dynamo PD

set -e
MODEL="${MODEL_32B:-/root/models/Qwen2.5-32B-Instruct}"
PORT=8000
LOG="${LOG_DIR:-/root}"
WAIT=720  # 32B cold start needs ~10 min

cleanup() { pkill -f sglang 2>/dev/null || true; pkill -f dynamo 2>/dev/null || true; sleep 2; }
wait_server() {
    local t=${1:-$WAIT}
    for i in $(seq 1 $t); do curl -s http://localhost:$PORT/v1/models >/dev/null 2>&1 && echo "Ready ${i}s" && return 0; sleep 1; done
    echo "ERROR: not ready after ${t}s"; return 1
}
bench() { python3 -m sglang.bench_serving --backend "$1" --port $PORT --model "$2" --dataset-name random --random-input-len 1024 --random-output-len 256 --num-prompts 100 --request-rate 10 --seed 1 $3 2>&1 | tee "$LOG/$4"; }

echo "=== C1: Baseline Single GPU ==="
cleanup
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 &>/tmp/sglang.log &
wait_server
bench sglang "$MODEL" "" benchmark_32b_C1_baseline.log
cleanup

echo "=== C4: FP8 KV Cache ==="
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 --kv-cache-dtype fp8_e5m2 &>/tmp/sglang.log &
wait_server
bench sglang "$MODEL" "" benchmark_32b_C4_fp8kv.log
cleanup

echo "=== C5: No Chunked Prefill ==="
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 --chunked-prefill-size -1 &>/tmp/sglang.log &
wait_server
bench sglang "$MODEL" "" benchmark_32b_C5_nochunk.log
cleanup

echo "=== C7: TP=2 ==="
python3 -m sglang.launch_server --model-path "$MODEL" --port $PORT --host 0.0.0.0 --tp 2 &>/tmp/sglang.log &
wait_server
bench sglang "$MODEL" "" benchmark_32b_C7_tp2.log
cleanup

echo "=== C6: Dynamo PD 1P1D ==="
nats-server -js &>/tmp/nats.log &
etcd &>/tmp/etcd.log &
sleep 2
python3 -m dynamo.frontend --router-mode kv --router-reset-states &>/tmp/frontend.log &
sleep 3
CUDA_VISIBLE_DEVICES=0 DYN_SYSTEM_PORT=8081 python3 -m dynamo.sglang \
    --model-path "$MODEL" --served-model-name QWEN32B --page-size 64 --tp 1 \
    --disaggregation-mode prefill --host 0.0.0.0 \
    --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
    --disaggregation-transfer-backend nixl &>/tmp/prefill.log &
CUDA_VISIBLE_DEVICES=1 DYN_SYSTEM_PORT=8083 python3 -m dynamo.sglang \
    --model-path "$MODEL" --served-model-name QWEN32B --page-size 64 --tp 1 \
    --disaggregation-mode decode --host 0.0.0.0 \
    --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
    --disaggregation-transfer-backend nixl &>/tmp/decode.log &
wait_server
bench sglang-oai-chat QWEN32B "--tokenizer $MODEL" benchmark_32b_C6_pd.log
cleanup; pkill -f nats-server 2>/dev/null; pkill -f etcd 2>/dev/null

echo "========== 32B All Done =========="
