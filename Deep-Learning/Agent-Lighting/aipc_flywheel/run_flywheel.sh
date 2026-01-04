#!/bin/bash
#
# AIPC Agent Training Flywheel
# ============================
#
# One-click script to run the complete closed-loop training pipeline.
#
# Usage:
#   bash run_flywheel.sh [OPTIONS]
#
# Options:
#   --iterations N    Number of feedback iterations (default: 3)
#   --skip-data       Skip data generation (use existing data)
#   --skip-sft        Skip SFT training (use existing checkpoint)
#   --from-version N  Start from version N (skip previous iterations)
#   --dry-run         Print commands without executing
#
# Prerequisites:
#   - Conda environment with Agent Lightning installed
#   - Azure OpenAI credentials set in environment
#   - GPU with 60GB+ VRAM (A100/H100)
#
# Author: Xinyu Wei (xinyuwei@microsoft.com)
# License: MIT

set -e  # Exit on error

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
ITERATIONS=3
SKIP_DATA=false
SKIP_SFT=false
FROM_VERSION=1
DRY_RUN=false

# Model settings
BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"
NUM_TRAIN_SAMPLES=1000
NUM_TEST_SAMPLES=100

# Training settings
SFT_EPOCHS=3
SFT_BATCH_SIZE=4
GRPO_ITERATIONS=100
GRPO_ROLLOUTS=4
FEEDBACK_ITERATIONS=50

# Paths
DATA_DIR="data"
CHECKPOINT_DIR="checkpoints"
RESULTS_DIR="results"

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        --skip-data)
            SKIP_DATA=true
            shift
            ;;
        --skip-sft)
            SKIP_SFT=true
            shift
            ;;
        --from-version)
            FROM_VERSION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            head -30 "$0" | tail -25
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

run_cmd() {
    local cmd="$1"
    log "Running: $cmd"
    if [ "$DRY_RUN" = true ]; then
        echo "(dry-run) $cmd"
    else
        eval "$cmd"
    fi
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Python
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python not found"
        exit 1
    fi
    
    # Check agentlightning
    if ! python -c "import agentlightning" 2>/dev/null; then
        echo "WARNING: agentlightning not installed. Install with: pip install agentlightning>=0.3.0"
    fi
    
    # Check Azure credentials
    if [ -z "$AZURE_OPENAI_ENDPOINT" ] || [ -z "$AZURE_OPENAI_API_KEY" ]; then
        echo "WARNING: Azure OpenAI credentials not set"
        echo "Set: AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
    fi
    
    # Check GPU
    if command -v nvidia-smi &> /dev/null; then
        log "GPU detected:"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    else
        echo "WARNING: nvidia-smi not found. GPU may not be available."
    fi
    
    log "Prerequisites check completed"
}

# =============================================================================
# Main Pipeline
# =============================================================================

main() {
    log "=============================================="
    log "AIPC Agent Training Flywheel"
    log "=============================================="
    log "Iterations: $ITERATIONS"
    log "Skip data: $SKIP_DATA"
    log "Skip SFT: $SKIP_SFT"
    log "From version: $FROM_VERSION"
    log "=============================================="
    
    check_prerequisites
    
    # Create directories
    mkdir -p "$DATA_DIR" "$CHECKPOINT_DIR" "$RESULTS_DIR"
    
    # =========================================================================
    # Stage 1: Data Generation
    # =========================================================================
    
    if [ "$SKIP_DATA" = false ]; then
        log "========== Stage 1: Data Generation =========="
        
        run_cmd "python generate_aipc_data_agl.py \\
            --output $DATA_DIR/aipc_train.jsonl \\
            --num_samples $NUM_TRAIN_SAMPLES \\
            --model gpt-5.2 \\
            --generate_test \\
            --test_output $DATA_DIR/aipc_test.jsonl \\
            --test_samples $NUM_TEST_SAMPLES"
        
        log "Data generation completed"
    else
        log "Skipping data generation (using existing data)"
    fi
    
    # =========================================================================
    # Stage 2: SFT Training
    # =========================================================================
    
    if [ "$SKIP_SFT" = false ]; then
        log "========== Stage 2: SFT Training =========="
        
        run_cmd "python train_sft_agl.py \
            --data $DATA_DIR/aipc_train.jsonl \
            --model $BASE_MODEL \
            --output $CHECKPOINT_DIR/aipc_sft_v1 \
            --num_epochs $SFT_EPOCHS \
            --batch_size $SFT_BATCH_SIZE"
        
        log "SFT training completed"
    else
        log "Skipping SFT training (using existing checkpoint)"
    fi
    
    # =========================================================================
    # Stage 3: Initial GRPO Training
    # =========================================================================
    
    if [ "$FROM_VERSION" -le 1 ]; then
        log "========== Stage 3: GRPO Training (V1) =========="
        
        run_cmd "python train_grpo_agl.py \
            --model $CHECKPOINT_DIR/aipc_sft_v1 \
            --output $CHECKPOINT_DIR/aipc_grpo_v1 \
            --data $DATA_DIR/aipc_train.jsonl \
            --num_iterations $GRPO_ITERATIONS \
            --rollouts_per_prompt $GRPO_ROLLOUTS"
        
        log "GRPO V1 training completed"
    fi
    
    # =========================================================================
    # Stage 4-5: Iterative Evaluation and Feedback Training
    # =========================================================================
    
    for ((i=FROM_VERSION; i<=ITERATIONS; i++)); do
        log "========== Iteration $i/$ITERATIONS =========="
        
        CURRENT_MODEL="$CHECKPOINT_DIR/aipc_grpo_v$i"
        NEXT_MODEL="$CHECKPOINT_DIR/aipc_grpo_v$((i+1))"
        EVAL_DIR="$RESULTS_DIR/eval_v$i"
        FEEDBACK_FILE="$DATA_DIR/feedback_v$i.jsonl"
        
        # -----------------------------------------------------------------
        # Stage 4: Evaluation
        # -----------------------------------------------------------------
        log "--- Evaluation (V$i) ---"
        
        run_cmd "python evaluate_agl.py \\
            --model $CURRENT_MODEL \\
            --test_data $DATA_DIR/aipc_test.jsonl \\
            --output $EVAL_DIR \\
            --judge_model gpt-5.2"
        
        # Check if pass rate is already high enough
        if [ -f "$EVAL_DIR/eval_result.json" ]; then
            PASS_RATE=$(python -c "import json; print(json.load(open('$EVAL_DIR/eval_result.json'))['stats']['pass_rate'])" 2>/dev/null || echo "0")
            log "V$i Pass rate: $PASS_RATE"
            
            # If pass rate >= 0.95, stop early
            if [ "$(echo "$PASS_RATE >= 0.95" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
                log "Pass rate >= 95%, stopping early"
                break
            fi
        fi
        
        # -----------------------------------------------------------------
        # Stage 5a: Generate Feedback Data
        # -----------------------------------------------------------------
        if [ -f "$EVAL_DIR/failed_cases.jsonl" ]; then
            log "--- Feedback Generation (V$i → V$((i+1))) ---"
            
            run_cmd "python generate_feedback_agl.py \\
                --failed $EVAL_DIR/failed_cases.jsonl \\
                --output $FEEDBACK_FILE \\
                --model gpt-5.2 \\
                --format preference"
            
            # -----------------------------------------------------------------
            # Stage 5b: Feedback Training
            # -----------------------------------------------------------------
            if [ -f "$FEEDBACK_FILE" ]; then
                FEEDBACK_COUNT=$(wc -l < "$FEEDBACK_FILE" 2>/dev/null || echo "0")
                
                if [ "$FEEDBACK_COUNT" -gt 0 ]; then
                    log "--- Feedback Training (V$i → V$((i+1))) ---"
                    log "Training on $FEEDBACK_COUNT feedback samples"
                    
                    run_cmd "python train_feedback_agl.py \
                        --model $CURRENT_MODEL \
                        --data $FEEDBACK_FILE \
                        --output $NEXT_MODEL \
                        --num_iterations $FEEDBACK_ITERATIONS"
                else
                    log "No feedback samples to train on"
                    cp -r "$CURRENT_MODEL" "$NEXT_MODEL"
                fi
            else
                log "No feedback file generated"
                cp -r "$CURRENT_MODEL" "$NEXT_MODEL"
            fi
        else
            log "No failed cases found, all tests passed!"
            cp -r "$CURRENT_MODEL" "$NEXT_MODEL"
        fi
    done
    
    # =========================================================================
    # Final Summary
    # =========================================================================
    
    log "=============================================="
    log "Training Flywheel Completed!"
    log "=============================================="
    log "Checkpoints:"
    ls -la "$CHECKPOINT_DIR"/ 2>/dev/null || true
    log "Results:"
    ls -la "$RESULTS_DIR"/ 2>/dev/null || true
    log "=============================================="
    
    # Print final pass rates
    log "Iteration Summary:"
    for ((i=1; i<=ITERATIONS; i++)); do
        EVAL_FILE="$RESULTS_DIR/eval_v$i/eval_result.json"
        if [ -f "$EVAL_FILE" ]; then
            PASS_RATE=$(python -c "import json; print(f'{json.load(open(\"$EVAL_FILE\"))[\"stats\"][\"pass_rate\"]*100:.1f}%')" 2>/dev/null || echo "N/A")
            log "  V$i: $PASS_RATE pass rate"
        fi
    done
}

# =============================================================================
# Entry Point
# =============================================================================

main "$@"
