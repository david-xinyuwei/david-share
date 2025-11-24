# Repository File Mapping

Use this guide to organize your local files into the recommended repository structure.

| Recommended Repo Path | Local File Path | Description |
| --------------------- | --------------- | ----------- |
| `data/generate_training_data_gpt5.py` | `agent-lightning/generate_training_data_gpt5.py` | Script used to generate synthetic math problems using a high-intelligence model. |
| `training/train_math_agent_vllm.py` | `agent-lightning/train_math_agent_vllm.py` | **Main Training Script**. Contains the v4 "Deep Thinking" reward function and GRPO config. |
| `evaluation/inference_validation_sequential.py` | `agent-lightning/inference_validation_sequential.py` | Script for validating the model on the test set (sequential execution to save memory). |
| `evaluation/run_full_evaluation.sh` | `agent-lightning/run_full_evaluation.sh` | Shell script that orchestrates the full evaluation pipeline (Base vs Trained). |
| `scripts/setup_h100.sh` | `agent-lightning/setup_h100.sh` | Setup script for the H100 environment (dependencies, etc.). |
| `README.md` | `README_PROJECT_REPORT.md` (Created just now) | The comprehensive project documentation. |

## Action Plan for Repo Creation:

1.  Create a new folder named `AI-Super-Agent-Repo`.
2.  Create the subfolders: `data`, `training`, `evaluation`, `scripts`.
3.  Copy the files listed above into their respective folders.
4.  Initialize git and push to GitHub.
