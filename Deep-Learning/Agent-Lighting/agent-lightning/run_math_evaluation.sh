#!/bin/bash

# Configuration
export HF_ENDPOINT=https://hf-mirror.com
BASE_MODEL_PATH="$(pwd)/Qwen/Qwen2.5-3B-Instruct"
TRAINED_MODEL_PATH="$(pwd)/checkpoints/AgentLightningTutorial/math_agent_3b_h100_v4_deepthink/global_step_100/actor/huggingface"
MATH_DATA="math_100_test.parquet"
BASE_OUTPUT="math_base_responses.parquet"
TRAINED_OUTPUT="math_trained_responses.parquet"
BASE_JUDGED="math_base_judged.parquet"
TRAINED_JUDGED="math_trained_judged.parquet"

# Function to kill processes
cleanup() {
    echo "🧹 Cleaning up processes..."
    pkill -9 -f vllm
    pkill -9 -f python
    sleep 5
}

# Initial Cleanup
cleanup

# 0. Prepare Data
echo "=================================================="
echo "Step 0: Preparing MATH Data (100 samples)"
echo "=================================================="
python prepare_math.py

if [ ! -f "$MATH_DATA" ]; then
    echo "❌ Failed to find $MATH_DATA. Please upload it."
    exit 1
fi

# 1. Evaluate Base Model
cleanup
echo "=================================================="
echo "Step 1: Evaluating Base Model on MATH"
echo "=================================================="
echo "🚀 Starting vLLM for Base Model..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $BASE_MODEL_PATH \
    --served-model-name "base-model" \
    --port 8000 \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 > vllm_base_math.log 2>&1 &

# Wait for server
echo "⏳ Waiting for Base Model server..."
for i in {1..60}; do
    if grep -q "Uvicorn running on" vllm_base_math.log; then
        echo "✅ Server is ready!"
        break
    fi
    sleep 5
    echo -n "."
done

echo "🧠 Running Inference..."
# Reusing inference_gsm8k.py as it is generic
python inference_gsm8k.py $MATH_DATA $BASE_OUTPUT 8000

# 2. Evaluate Trained Model
cleanup
echo "=================================================="
echo "Step 2: Evaluating Trained Model on MATH"
echo "=================================================="
echo "🚀 Starting vLLM for Trained Model..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $TRAINED_MODEL_PATH \
    --served-model-name "trained-model" \
    --port 8000 \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 > vllm_trained_math.log 2>&1 &

# Wait for server
echo "⏳ Waiting for Trained Model server..."
for i in {1..60}; do
    if grep -q "Uvicorn running on" vllm_trained_math.log; then
        echo "✅ Server is ready!"
        break
    fi
    sleep 5
    echo -n "."
done

echo "🧠 Running Inference..."
python inference_gsm8k.py $MATH_DATA $TRAINED_OUTPUT 8000

cleanup

# 3. LLM Judge
echo "=================================================="
echo "Step 3: Running LLM Judge (GPT-5)"
echo "=================================================="
echo "⚖️ Judging Base Model..."
python judge_with_llm.py $BASE_OUTPUT $BASE_JUDGED

echo "⚖️ Judging Trained Model..."
python judge_with_llm.py $TRAINED_OUTPUT $TRAINED_JUDGED

echo "=================================================="
echo "🎉 MATH Evaluation Complete!"
echo "=================================================="
