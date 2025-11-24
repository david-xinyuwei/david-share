# Archive Folder

This folder contains experimental and legacy scripts that are not part of the main project workflow.

## Contents

- `train_math_agent_large.py` - Early experiment using GGUF format and custom FastGGUFRLAlgorithm
- `train_math_agent_large_correct.py` - Variant of the above
- `train_math_agent.py` - Legacy training script without vLLM optimization

## Current Production Scripts

The main project uses:
- **`train_math_agent_vllm.py`** - Production training script with GRPO + Deep Thinking
- **`inference_gsm8k.py`** - Generic inference script for evaluation
- **`judge_with_llm.py`** - LLM-based answer verification

These archived scripts are kept for reference but should not be used for new experiments.
