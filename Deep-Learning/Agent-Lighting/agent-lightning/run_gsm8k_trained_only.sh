#!/bin/bash

# Configuration
export HF_ENDPOINT=https://hf-mirror.com
BASE_MODEL_PATH="$(pwd)/Qwen/Qwen2.5-3B-Instruct"
TRAINED_MODEL_PATH="$(pwd)/checkpoints/AgentLightningTutorial/math_agent_3b_h100_v4_deepthink/global_step_100/actor/huggingface"
GSM8K_DATA="gsm8k_100_test.parquet"
BASE_OUTPUT="gsm8k_base_responses.parquet"
TRAINED_OUTPUT="gsm8k_trained_responses.parquet"
BASE_JUDGED="gsm8k_base_judged.parquet"
TRAINED_JUDGED="gsm8k_trained_judged.parquet"

# Function to kill processes
cleanup() {
    echo "🧹 Cleaning up processes..."
    pkill -9 -f vllm
    pkill -9 -f python
    sleep 5
}

# Initial Cleanup
cleanup

# Check if data exists
if [ ! -f "$GSM8K_DATA" ]; then
    echo "❌ Failed to find $GSM8K_DATA. Please run prepare_gsm8k.py first."
    exit 1
fi

# 2. Evaluate Trained Model
echo "=================================================="
echo "Step 2: Evaluating Trained Model on GSM8K"
echo "=================================================="
echo "🚀 Starting vLLM for Trained Model..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $TRAINED_MODEL_PATH \
    --served-model-name "trained-model" \
    --port 8000 \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 > vllm_trained_gsm8k.log 2>&1 &

# Wait for server
echo "⏳ Waiting for Trained Model server..."
for i in {1..60}; do
    if grep -q "Uvicorn running on" vllm_trained_gsm8k.log; then
        echo "✅ Server is ready!"
        break
    fi
    sleep 5
    echo -n "."
done

echo "🧠 Running Inference..."
python inference_gsm8k.py $GSM8K_DATA $TRAINED_OUTPUT 8000

cleanup

# 3. LLM Judge
echo "=================================================="
echo "Step 3: Running LLM Judge (GPT-5)"
echo "=================================================="
# We can re-judge base model just to be sure, or skip it if it's already done.
# But let's judge both to have a clean output.
if [ -f "$BASE_OUTPUT" ]; then
    echo "⚖️ Judging Base Model..."
    python judge_with_llm.py $BASE_OUTPUT $BASE_JUDGED
else
    echo "⚠️ Base model output not found, skipping base judgment."
fi

echo "⚖️ Judging Trained Model..."
python judge_with_llm.py $TRAINED_OUTPUT $TRAINED_JUDGED

echo "=================================================="
echo "🎉 GSM8K Evaluation Complete!"
echo "=================================================="
