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
    echo "Usage: $0 {phase1|phase2|phase3|phase5|highload_tp2|highload_pd|32b|docker|all}"
    echo ""
    echo "8B Phases (Qwen3-8B):"
    echo "  phase1       - Baseline single GPU"
    echo "  phase2       - TP=2 tensor parallel"
    echo "  phase3       - Prefix cache (cold/warm/flush)"
    echo "  phase5       - Dynamo PD disaggregation (requires NATS+etcd+nixl)"
    echo "  highload_tp2 - High concurrency TP=2 (200 prompts @ 20 req/s)"
    echo "  highload_pd  - High concurrency Dynamo PD"
    echo "  all          - Run all 8B phases sequentially"
    echo ""
    echo "32B Phases (Qwen2.5-32B-Instruct):"
    echo "  32b          - C1 baseline + C4 FP8 KV + C5 no chunked + C7 TP=2 + C6 PD"
    echo ""
    echo "Docker Phases:"
    echo "  docker       - D1 Docker baseline + D2 Docker PD (requires Docker + nvidia runtime)"
    echo ""
    echo "Environment variables:"
    echo "  MODEL_PATH   - Path to 8B model (default: /root/models/Qwen3-8B)"
    echo "  MODEL_32B    - Path to 32B model (default: /root/models/Qwen2.5-32B-Instruct)"
    echo "  LOG_DIR      - Directory for benchmark logs (default: /root)"
}

case "${1:-all}" in
    phase1) phase1 ;;
    phase2) phase2 ;;
    phase3) phase3 ;;
    phase5) phase5 ;;
    highload_tp2) highload_tp2 ;;
    highload_pd) highload_pd ;;
    32b)
        # 32B benchmarks: C1 baseline, C4 FP8 KV, C5 no chunked, C6 PD, C7 TP=2
        MODEL_32B="${MODEL_32B:-/root/models/Qwen2.5-32B-Instruct}"
        WAIT=720
        echo "========== 32B Benchmarks (100 prompts @ 10 req/s) =========="

        echo "=== C1: 32B Baseline (single GPU) ==="
        cleanup
        python3 -m sglang.launch_server --model-path "$MODEL_32B" --port $PORT --host 0.0.0.0 &>/tmp/sglang_32b.log &
        wait_for_server $WAIT
        run_sglang_bench sglang benchmark_32b_C1_baseline.log 100 10 "--model $MODEL_32B"
        cleanup

        echo "=== C4: 32B FP8 KV Cache ==="
        python3 -m sglang.launch_server --model-path "$MODEL_32B" --port $PORT --host 0.0.0.0 --kv-cache-dtype fp8_e5m2 &>/tmp/sglang_32b.log &
        wait_for_server $WAIT
        run_sglang_bench sglang benchmark_32b_C4_fp8kv.log 100 10 "--model $MODEL_32B"
        cleanup

        echo "=== C5: 32B No Chunked Prefill ==="
        python3 -m sglang.launch_server --model-path "$MODEL_32B" --port $PORT --host 0.0.0.0 --chunked-prefill-size -1 &>/tmp/sglang_32b.log &
        wait_for_server $WAIT
        run_sglang_bench sglang benchmark_32b_C5_nochunk.log 100 10 "--model $MODEL_32B"
        cleanup

        echo "=== C7: 32B TP=2 ==="
        python3 -m sglang.launch_server --model-path "$MODEL_32B" --port $PORT --host 0.0.0.0 --tp 2 &>/tmp/sglang_32b.log &
        wait_for_server $WAIT
        run_sglang_bench sglang benchmark_32b_C7_tp2.log 100 10 "--model $MODEL_32B"
        cleanup

        echo "=== C6: 32B Dynamo PD 1P1D ==="
        nats-server -js &>/tmp/nats.log &
        etcd &>/tmp/etcd.log &
        sleep 2
        python3 -m dynamo.frontend --router-mode kv --router-reset-states &>/tmp/dynamo_frontend.log &
        sleep 3
        CUDA_VISIBLE_DEVICES=0 DYN_SYSTEM_PORT=8081 python3 -m dynamo.sglang \
            --model-path "$MODEL_32B" --served-model-name QWEN32B --page-size 64 --tp 1 \
            --disaggregation-mode prefill --host 0.0.0.0 \
            --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
            --disaggregation-transfer-backend nixl &>/tmp/dynamo_prefill.log &
        CUDA_VISIBLE_DEVICES=1 DYN_SYSTEM_PORT=8083 python3 -m dynamo.sglang \
            --model-path "$MODEL_32B" --served-model-name QWEN32B --page-size 64 --tp 1 \
            --disaggregation-mode decode --host 0.0.0.0 \
            --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
            --disaggregation-transfer-backend nixl &>/tmp/dynamo_decode.log &
        wait_for_server $WAIT
        run_sglang_bench sglang-oai-chat benchmark_32b_C6_pd.log 100 10 "--model QWEN32B --tokenizer $MODEL_32B"
        cleanup
        pkill -f nats-server 2>/dev/null; pkill -f etcd 2>/dev/null

        echo "========== 32B Benchmarks complete =========="
        ;;
    docker)
        # Docker deployment benchmarks (requires: docker pull nvcr.io/nvidia/ai-dynamo/sglang-runtime:1.0.1)
        MODEL_32B="${MODEL_32B:-/root/models/Qwen2.5-32B-Instruct}"
        echo "========== Docker Benchmarks =========="
        echo "Requires: docker with --runtime=nvidia and model at $MODEL_32B"

        docker rm -f dynamo-docker-bench 2>/dev/null
        docker run -d --name dynamo-docker-bench --runtime=nvidia --network host --ipc=host \
            -v "$(dirname $MODEL_32B):/models" \
            nvcr.io/nvidia/ai-dynamo/sglang-runtime:1.0.1 sleep infinity

        echo "=== D1: Docker Single GPU Baseline ==="
        docker exec -d dynamo-docker-bench python3 -m sglang.launch_server \
            --model-path /models/$(basename $MODEL_32B) --port 8000 --host 0.0.0.0
        echo "Waiting for Docker server..."
        for i in $(seq 1 300); do
            curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "Qwen" && echo "D1 ready at ${i}s" && break
            sleep 1
        done
        docker exec dynamo-docker-bench python3 -m sglang.bench_serving --backend sglang --port 8000 \
            --model /models/$(basename $MODEL_32B) --dataset-name random \
            --random-input-len 1024 --random-output-len 256 --num-prompts 100 --request-rate 10 --seed 1 \
            2>&1 | tee "$LOG_DIR/benchmark_32b_D1_docker_baseline.log"
        docker exec dynamo-docker-bench bash -c "pkill -f sglang" && sleep 5

        echo "=== D2: Docker Dynamo PD ==="
        docker exec -d dynamo-docker-bench bash -c "nats-server -js & etcd &"
        sleep 3
        docker exec -d dynamo-docker-bench python3 -m dynamo.frontend --router-mode kv --router-reset-states --http-port 8000
        sleep 3
        docker exec -d -e CUDA_VISIBLE_DEVICES=0 -e DYN_SYSTEM_PORT=8081 dynamo-docker-bench python3 -m dynamo.sglang \
            --model-path /models/$(basename $MODEL_32B) --served-model-name QWEN32B --page-size 64 --tp 1 \
            --disaggregation-mode prefill --host 0.0.0.0 \
            --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5557"}' \
            --disaggregation-transfer-backend nixl
        docker exec -d -e CUDA_VISIBLE_DEVICES=1 -e DYN_SYSTEM_PORT=8083 dynamo-docker-bench python3 -m dynamo.sglang \
            --model-path /models/$(basename $MODEL_32B) --served-model-name QWEN32B --page-size 64 --tp 1 \
            --disaggregation-mode decode --host 0.0.0.0 \
            --kv-events-config '{"publisher":"zmq","topic":"kv-events","endpoint":"tcp://*:5560"}' \
            --disaggregation-transfer-backend nixl
        for i in $(seq 1 300); do
            curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "QWEN32B" && echo "D2 ready at ${i}s" && break
            sleep 1
        done
        docker exec dynamo-docker-bench python3 -m sglang.bench_serving --backend sglang-oai-chat --port 8000 \
            --model QWEN32B --tokenizer /models/$(basename $MODEL_32B) --dataset-name random \
            --random-input-len 1024 --random-output-len 256 --num-prompts 100 --request-rate 10 --seed 1 \
            2>&1 | tee "$LOG_DIR/benchmark_32b_D2_docker_pd.log"

        docker rm -f dynamo-docker-bench 2>/dev/null
        echo "========== Docker Benchmarks complete =========="
        ;;
    all)
        phase1
        phase2
        phase3
        phase5
        highload_tp2
        highload_pd
        echo "========== All 8B phases complete =========="
        echo "For 32B benchmarks: bash $0 32b"
        echo "For Docker benchmarks: bash $0 docker"
        ;;
    *) usage ;;
esac
