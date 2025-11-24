# 🚀 H100 Migration Guide

This guide will help you migrate your Agent Lightning training environment from the A10 machine to a new H100 machine.

## 📦 What's Included in this Pack
1.  **`agentL_h100.yml`**: Optimized Conda environment file for H100.
2.  **`setup_h100.sh`**: One-click script to set up the environment and download models.
3.  **`data/`**: Contains your generated training data (`train_gpt5_large.parquet`, etc.).
4.  **`train_math_agent_vllm.py`**: The latest training script.

## 🛠 Migration Steps

### 1. Upload Files to H100
Use `scp` or your preferred method to upload the entire `agent-lightning` folder to the new H100 machine.

```bash
# Example (run from your local machine):
scp -r agent-lightning root@<H100_IP>:~/
```

### 2. Run the Setup Script
SSH into the H100 machine and run the setup script. This will install Conda, create the environment, and download the 3B model.

```bash
ssh root@<H100_IP>
cd agent-lightning
chmod +x setup_h100.sh
./setup_h100.sh
```

### 3. Start Training (3B Model)
Once the setup is complete, you can start the training with the 3B model configuration.

**Note:** Before running, ensure `train_math_agent_vllm.py` is configured for the 3B model (it might be set to 0.5B for A10 verification).
Edit `train_math_agent_vllm.py`:
- Change `model_path` to `"Qwen/Qwen2.5-3B-Instruct"`
- Change `gpu_memory_utilization` to `0.5` or higher (H100 has 80GB, so you can be generous!)

```bash
# Activate environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate agentL

# Run training
nohup python -u train_math_agent_vllm.py > training_h100.log 2>&1 &
tail -f training_h100.log
```

## 💡 H100 Optimization Tips
- **Batch Size**: On H100, you can increase `train_batch_size` in the config (e.g., to 8 or 16).
- **VLLM Memory**: Set `gpu_memory_utilization` to `0.6` or `0.7` to allow for longer context and larger batches.
