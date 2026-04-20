#!/bin/bash
# NVIDIA Dynamo Agentic Inference Benchmark Suite
# Author: Xinyu Wei (魏新宇)
# Hardware: 2x NVIDIA H100 NVL 95830 MiB (NC80adis_H100_v5)
# Model: Qwen3-8B (FP16, 16GB)
# Engine: SGLang 0.5.10.post1 + ai-dynamo 1.0.1

set -e

MODEL_PATH="${MODEL_PATH:-/root/models/Qwen3-8B}"
PORT=8000
LOW_PROMPTS=50
LOW_RATE=5
HIGH_PROMPTS=200
HIGH_RATE=20
INPUT_LEN=1024
OUTPUT_LEN=256
LOG_DIR="${LOG_DIR:-/root}"

wait_for_server() {
    local max_wait=${1:-60}
    echo "Waiting up to ${max_wait}s for server on port $PORT..."
    for i in $(seq 1 $max_wait); do
        if curl -s http://localhost:$PORT/v1/models > /dev/null 2>&1; then
            echo "Server ready in ${i}s"
            return 0
        fi
        sleep 1
    done
    echo "ERROR: Server not ready after ${max_wait}s"
    return 1
}

cleanup() {
    echo "Cleaning up..."
    pkill -f sglang 2>/dev/null || true
    pkill -f dynamo 2>/dev/null || true
    sleep 2
}

run_sglang_bench() {
    local backend=$1
    local log_file=$2
    local prompts=${3:-$LOW_PROMPTS}
    local rate=${4:-$LOW_RATE}
    local extra_args="${5:-}"

    echo "=== Running: $log_file (${prompts} prompts @ ${rate} req/s, backend=$backend) ==="
    python -m sglang.bench_serving \
        --backend "$backend" \
        --port $PORT \
        --model "$MODEL_PATH" \
        --dataset-name random \
        --random-input-len $INPUT_LEN \
        --random-output-len $OUTPUT_LEN \
        --num-prompts "$prompts" \
        --request-rate "$rate" \
        $extra_args \
        2>&1 | tee "$LOG_DIR/$log_file"
}

# ============================================================
# Phase 1: Baseline (Single GPU, no Dynamo)
# ============================================================
phase1() {
    echo "========== Phase 1: Baseline Single GPU =========="
    cleanup
    CUDA_VISIBLE_DEVICES=0 python -m sglang.launch_server \
        --model-path "$MODEL_PATH" --port $PORT --host 0.0.0.0 \
        &> /tmp/sglang_baseline.log &
    wait_for_server 60
    run_sglang_bench sglang benchmark_phase1_baseline.log
    cleanup
}

# ============================================================
# Phase 2: TP=2 (Tensor Parallel, both GPUs)
# ============================================================
phase2() {
    echo "========== Phase 2: TP=2 Tensor Parallel =========="
    cleanup
    python -m sglang.launch_server \
        --model-path "$MODEL_PATH" --port $PORT --host 0.0.0.0 --tp 2 \
        &> /tmp/sglang_tp2.log &
    wait_for_server 60
    run_sglang_bench sglang benchmark_phase2_tp2.log
    cleanup
}

# ============================================================
# Phase 3-4: Prefix Cache (Cold → Warm → Flush)
# ============================================================
phase3() {
    echo "========== Phase 3-4: Prefix Cache =========="
    cleanup
    CUDA_VISIBLE_DEVICES=0 python -m sglang.launch_server \
        --model-path "$MODEL_PATH" --port $PORT --host 0.0.0.0 \
        &> /tmp/sglang_cache.log &
    wait_for_server 60

    # Round 1: Cold cache (seed=42)
    run_sglang_bench sglang benchmark_phase3_cold.log $LOW_PROMPTS $LOW_RATE "--seed 42"

    # Round 2: Warm cache (same seed=42, should hit prefix cache)
    run_sglang_bench sglang benchmark_phase3_warm.log $LOW_PROMPTS $LOW_RATE "--seed 42"

    # Round 3: Flush cache control (seed=42 but flush first)
    run_sglang_bench sglang benchmark_phase4_flush.log $LOW_PROMPTS $LOW_RATE "--seed 42 --flush-cache"

    cleanup
}

# ============================================================
# Phase 5: Dynamo PD Disaggregation (1 Prefill + 1 Decode)
# Requires: nats-server, etcd, ai-dynamo, nixl
# ============================================================
phase5() {
    echo "========== Phase 5: Dynamo PD 1P1D =========="
    cleanup

    # Start infrastructure
    nats-server -js &> /tmp/nats.log &
    etcd &> /tmp/etcd.log &
    sleep 2

    # Start Dynamo frontend
    python3 -m dynamo.frontend --router-mode kv --router-reset-states \
        &> /tmp/dynamo_frontend.log &
    sleep 3

    # Start Prefill worker (GPU 0)
    CUDA_VISIBLE_DEVICES=0 DYN_SYSTEM_PORT=8081 python3 -m dynamo.sglang \
        --model-path "$MODEL_PATH" \
        --served-model-name Qwen3-8B \
        --page-size 64 --tp 1 \
        --disaggregation-mode prefill \
        --host 0.0.0.0 \
        --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
        --disaggregation-transfer-backend nixl \
        &> /tmp/dynamo_prefill.log &

    # Start Decode worker (GPU 1)
    CUDA_VISIBLE_DEVICES=1 DYN_SYSTEM_PORT=8083 python3 -m dynamo.sglang \
        --model-path "$MODEL_PATH" \
        --served-model-name Qwen3-8B \
        --page-size 64 --tp 1 \
        --disaggregation-mode decode \
        --host 0.0.0.0 \
        --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
        --disaggregation-transfer-backend nixl \
        &> /tmp/dynamo_decode.log &

    wait_for_server 90

    # Note: Dynamo frontend only exposes OpenAI-compatible API
    # Must use sglang-oai-chat backend, not sglang native
    python -m sglang.bench_serving \
        --backend sglang-oai-chat \
        --port $PORT \
        --model Qwen3-8B \
        --tokenizer "$MODEL_PATH" \
        --dataset-name random \
        --random-input-len $INPUT_LEN \
        --random-output-len $OUTPUT_LEN \
        --num-prompts $LOW_PROMPTS \
        --request-rate $LOW_RATE \
        2>&1 | tee "$LOG_DIR/benchmark_phase5_dynamo_pd.log"

    cleanup
    pkill -f nats-server 2>/dev/null || true
    pkill -f etcd 2>/dev/null || true
}

# ============================================================
# High Concurrency: TP=2 vs Dynamo PD (fair 2-GPU comparison)
# ============================================================
highload_tp2() {
    echo "========== High Concurrency: TP=2 =========="
    cleanup
    python -m sglang.launch_server \
        --model-path "$MODEL_PATH" --port $PORT --host 0.0.0.0 --tp 2 \
        &> /tmp/sglang_tp2_highload.log &
    wait_for_server 60
    run_sglang_bench sglang benchmark_highload_tp2.log $HIGH_PROMPTS $HIGH_RATE
    cleanup
}

highload_pd() {
    echo "========== High Concurrency: Dynamo PD =========="
    # Reuse phase5 setup
    phase5  # This runs low-concurrency first

    # Now restart PD and run high-concurrency
    cleanup
    pkill -f nats-server 2>/dev/null || true
    pkill -f etcd 2>/dev/null || true
    sleep 2

    nats-server -js &> /tmp/nats.log &
    etcd &> /tmp/etcd.log &
    sleep 2

    python3 -m dynamo.frontend --router-mode kv --router-reset-states \
        &> /tmp/dynamo_frontend.log &
    sleep 3

    CUDA_VISIBLE_DEVICES=0 DYN_SYSTEM_PORT=8081 python3 -m dynamo.sglang \
        --model-path "$MODEL_PATH" --served-model-name Qwen3-8B \
        --page-size 64 --tp 1 --disaggregation-mode prefill --host 0.0.0.0 \
        --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
        --disaggregation-transfer-backend nixl &> /tmp/dynamo_prefill.log &

    CUDA_VISIBLE_DEVICES=1 DYN_SYSTEM_PORT=8083 python3 -m dynamo.sglang \
        --model-path "$MODEL_PATH" --served-model-name Qwen3-8B \
        --page-size 64 --tp 1 --disaggregation-mode decode --host 0.0.0.0 \
        --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
        --disaggregation-transfer-backend nixl &> /tmp/dynamo_decode.log &

    wait_for_server 90

    python -m sglang.bench_serving \
        --backend sglang-oai-chat --port $PORT \
        --model Qwen3-8B --tokenizer "$MODEL_PATH" \
        --dataset-name random \
        --random-input-len $INPUT_LEN --random-output-len $OUTPUT_LEN \
        --num-prompts $HIGH_PROMPTS --request-rate $HIGH_RATE \
        2>&1 | tee "$LOG_DIR/benchmark_highload_pd.log"

    cleanup
    pkill -f nats-server 2>/dev/null || true
    pkill -f etcd 2>/dev/null || true
}

# ============================================================
# Main
# ============================================================
usage() {
    echo "Usage: $0 {phase1|phase2|phase3|phase5|highload_tp2|highload_pd|all}"
    echo ""
    echo "Phases:"
    echo "  phase1       - Baseline single GPU"
    echo "  phase2       - TP=2 tensor parallel"
    echo "  phase3       - Prefix cache (cold/warm/flush)"
    echo "  phase5       - Dynamo PD disaggregation (requires NATS+etcd+nixl)"
    echo "  highload_tp2 - High concurrency TP=2 (200 prompts @ 20 req/s)"
    echo "  highload_pd  - High concurrency Dynamo PD"
    echo "  all          - Run all phases sequentially"
    echo ""
    echo "Environment variables:"
    echo "  MODEL_PATH   - Path to model (default: /root/models/Qwen3-8B)"
    echo "  LOG_DIR      - Directory for benchmark logs (default: /root)"
}

case "${1:-all}" in
    phase1) phase1 ;;
    phase2) phase2 ;;
    phase3) phase3 ;;
    phase5) phase5 ;;
    highload_tp2) highload_tp2 ;;
    highload_pd) highload_pd ;;
    all)
        phase1
        phase2
        phase3
        phase5
        highload_tp2
        highload_pd
        echo "========== All phases complete =========="
        ;;
    *) usage ;;
esac
