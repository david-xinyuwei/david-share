# Math Reasoning Agent Tutorial

This tutorial demonstrates how to train a math reasoning agent using Agent Lightning with Reinforcement Learning.

## Overview

We train a math agent to solve complex mathematical problems using the MATH dataset. The tutorial shows:
- How to set up training with RL
- How to convert checkpoints for inference
- How to evaluate model performance
- How to analyze qualitative improvements

## Quick Start

### 1. Training

```bash
# Train the math agent
python train_math_agent_vllm.py
```

### 2. Convert Checkpoint

After training, convert the checkpoint to HuggingFace format:

```bash
python convert_checkpoint.py
```

### 3. Evaluate

Run evaluation on both base and trained models:

```bash
# Sequential evaluation (recommended for limited GPU memory)
bash run_full_evaluation_sequential.sh

# Or parallel evaluation (requires more GPU memory)
bash run_full_evaluation.sh
```

## Files in This Tutorial

### Core Training Scripts
- `train_math_agent_vllm.py` - Main training script using vLLM backend
- `train_math_agent.py` - Alternative training script
- `convert_checkpoint.py` - Convert trained checkpoints to HuggingFace format

### Evaluation Scripts
- `inference_validation_sequential.py` - Sequential model evaluation
- `inference_compare.py` - Compare base vs trained models
- `judge_with_llm.py` - Use LLM to judge answer correctness

### Dataset Preparation
- `prepare_math.py` - Prepare MATH dataset
- `prepare_gsm8k.py` - Prepare GSM8K dataset
- `generate_training_data_gpt5.py` - Generate synthetic training data

### Analysis Tools
- `analyze_math_wins.py` - Analyze performance improvements
- `inspect_failures.py` - Inspect failure cases

## Results

| Model | Accuracy (MATH Subset) |
|-------|------------------------|
| Base Model (Qwen2.5-3B) | 69.00% |
| RL-Trained Model | 73.00% |
| **Improvement** | **+4.00%** |

## Key Insights

The RL training improves not just accuracy but also reasoning quality:

1. **Logic Repair**: Fixes specific logical flaws in reasoning chains
2. **Constraint Handling**: Avoids hallucinated constraints
3. **Step-by-Step Reasoning**: Maintains steady logical progression

See the main README for a detailed case study.

## Environment Variables

Key environment variables you can set:

```bash
# Model paths
export BASE_MODEL_PATH="path/to/base/model"
export CHECKPOINT_PATH="path/to/checkpoint"

# Azure OpenAI (for LLM judge)
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="your-endpoint"

# vLLM settings
export VLLM_API_KEY="EMPTY"  # Use "EMPTY" for local vLLM
export VLLM_PORT="8001"
```

## Troubleshooting

### Out of Memory Errors
- Use sequential evaluation instead of parallel
- Reduce `gpu_memory_utilization` in training config
- Use smaller batch sizes

### Checkpoint Conversion Issues
- Ensure base model is downloaded first
- Check that checkpoint path contains `model_world_size_1_rank_0.pt`
- Verify sufficient disk space for converted model

### Evaluation Failures
- Verify vLLM server is running: `curl http://localhost:8001/v1/models`
- Check log files: `vllm_base.log`, `vllm_trained.log`
- Ensure test data is present in `data/` directory

## Next Steps

1. Try training with different reward functions
2. Experiment with larger models
3. Test on other mathematical reasoning datasets
4. Fine-tune hyperparameters for better performance

## References

- [Agent Lightning Paper](https://arxiv.org/abs/2508.03680)
- [MATH Dataset](https://github.com/hendrycks/math)
- [vLLM Documentation](https://docs.vllm.ai/)
