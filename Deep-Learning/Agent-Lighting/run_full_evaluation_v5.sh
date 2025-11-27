#!/bin/bash
# ============================================================
# Full Evaluation Pipeline
# Start base model -> Start trained model -> Run comparative evaluation
# ============================================================

set -e  # Exit on error

# ============================================================
# Configuration - Modify as needed
# ============================================================
BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"
BASE_PORT=8000
TRAINED_PORT=8001
GPU_MEMORY_UTIL=0.35

# ============================================================
# Auto-detect trained model path
# ============================================================
get_trained_model_path() {
    # Method 1: Read from convert_checkpoint.py generated file
    if [ -f "last_converted_model.txt" ]; then
        TRAINED_MODEL=$(cat last_converted_model.txt)
        if [ -d "$TRAINED_MODEL" ]; then
            echo "Reading model path from last_converted_model.txt"
            echo "$TRAINED_MODEL"
            return 0
        fi
    fi
    
    # Method 2: Read from train_math_agent_vllm.py generated file
    if [ -f "last_checkpoint.txt" ]; then
        TRAINED_MODEL=$(cat last_checkpoint.txt)
        if [ -d "$TRAINED_MODEL" ]; then
            echo "Reading checkpoint path from last_checkpoint.txt"
            echo "$TRAINED_MODEL"
            return 0
        fi
    fi
    
    # Method 3: Check default conversion directory
    if [ -d "./converted_model" ]; then
        echo "Using default conversion directory ./converted_model"
        echo "$(pwd)/converted_model"
        return 0
    fi
    
    # Method 4: Scan checkpoints directory for latest
    CHECKPOINT_BASE="checkpoints/AgentLightningTutorial"
    if [ -d "$CHECKPOINT_BASE" ]; then
        LATEST_EXP=$(ls -t "$CHECKPOINT_BASE" 2>/dev/null | head -1)
        if [ -n "$LATEST_EXP" ]; then
            LATEST_STEP=$(ls -t "$CHECKPOINT_BASE/$LATEST_EXP" 2>/dev/null | grep "global_step_" | head -1)
            if [ -n "$LATEST_STEP" ]; then
                TRAINED_MODEL="$CHECKPOINT_BASE/$LATEST_EXP/$LATEST_STEP/actor/huggingface"
                if [ -d "$TRAINED_MODEL" ]; then
                    echo "Auto-detected latest checkpoint"
                    echo "$(pwd)/$TRAINED_MODEL"
                    return 0
                fi
            fi
        fi
    fi
    
    # Not found
    return 1
}

# ============================================================
# Main Flow
# ============================================================
echo "============================================================"
echo "Agent Lightning Full Evaluation Pipeline"
echo "============================================================"

# 1. Clean up environment
echo -e "\nCleaning up old processes..."
pkill -9 -f "vllm.entrypoints" 2>/dev/null || true
sleep 2

# 2. Activate Conda environment
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    conda activate agentL 2>/dev/null || echo "Warning: agentL environment not found, using current environment"
fi

# 3. Get trained model path
echo -e "\nGetting model path..."
TRAINED_MODEL_PATH=$(get_trained_model_path)
if [ -z "$TRAINED_MODEL_PATH" ]; then
    echo "Error: Cannot find trained model!"
    echo ""
    echo "Please complete the following steps first:"
    echo "  1. Run training: python train_math_agent_vllm.py"
    echo "  2. Convert model: python convert_checkpoint.py"
    echo ""
    echo "Or manually specify the model path:"
    echo "  export TRAINED_MODEL=/path/to/your/model"
    echo "  bash run_full_evaluation_v5.sh"
    exit 1
fi

# Support environment variable override
if [ -n "$TRAINED_MODEL" ]; then
    TRAINED_MODEL_PATH="$TRAINED_MODEL"
    echo "Using model path from environment variable"
fi

echo "  Base Model:    $BASE_MODEL"
echo "  Trained Model: $TRAINED_MODEL_PATH"

# 4. Start base model (Port 8000)
echo -e "\nStarting base model (Port $BASE_PORT)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model $BASE_MODEL \
    --served-model-name "base-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization $GPU_MEMORY_UTIL \
    --port $BASE_PORT > vllm_base.log 2>&1 &
BASE_PID=$!

# 5. Start trained model (Port 8001)
echo "Starting trained model (Port $TRAINED_PORT)..."
nohup python -m vllm.entrypoints.openai.api_server \
    --model "$TRAINED_MODEL_PATH" \
    --served-model-name "trained-model" \
    --trust-remote-code \
    --dtype bfloat16 \
    --gpu-memory-utilization $GPU_MEMORY_UTIL \
    --port $TRAINED_PORT > vllm_trained.log 2>&1 &
TRAINED_PID=$!

# 6. Wait for models to start
echo -e "\nWaiting for models to start..."
timeout=300
elapsed=0
while true; do
    BASE_READY=$(grep -c "Uvicorn running on" vllm_base.log 2>/dev/null || echo 0)
    TRAINED_READY=$(grep -c "Uvicorn running on" vllm_trained.log 2>/dev/null || echo 0)
    
    if [ "$BASE_READY" -ge 1 ] && [ "$TRAINED_READY" -ge 1 ]; then
        echo -e "\nBoth models started!"
        break
    fi
    
    sleep 5
    elapsed=$((elapsed+5))
    
    if [ $elapsed -ge $timeout ]; then
        echo -e "\nError: Model startup timeout (${timeout}s)"
        echo "--- Base Model Log ---"
        tail -n 20 vllm_base.log
        echo "--- Trained Model Log ---"
        tail -n 20 vllm_trained.log
        pkill -9 -f vllm 2>/dev/null || true
        exit 1
    fi
    
    echo -n "."
done

# 7. Run comparative evaluation script
echo -e "\nRunning comparative evaluation..."
if [ -f "inference_validation.py" ]; then
    python inference_validation.py
else
    echo "Warning: inference_validation.py not found, skipping"
fi

# 8. Run LLM judge script (use AGL version)
echo -e "\nRunning LLM judge..."
if [ -f "judge_with_llm_agl.py" ]; then
    python judge_with_llm_agl.py
elif [ -f "judge_with_llm.py" ]; then
    echo "Warning: Using old version judge_with_llm.py"
    python judge_with_llm.py
else
    echo "Warning: Judge script not found, skipping"
fi

# 9. Cleanup
echo -e "\nCleaning up processes..."
pkill -9 -f "vllm.entrypoints" 2>/dev/null || true

echo ""
echo "============================================================"
echo "Evaluation Complete!"
echo "============================================================"
echo "View results:"
echo "   - Evaluation report: validation_report.txt"
echo "   - Detailed data: validation_llm_judged.parquet"
echo "============================================================"
