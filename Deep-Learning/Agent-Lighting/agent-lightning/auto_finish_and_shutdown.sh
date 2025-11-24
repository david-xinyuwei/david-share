#!/bin/bash

# 1. Find the training process ID
PID=$(pgrep -f "train_math_agent_vllm.py")

if [ -z "$PID" ]; then
    echo "❌ Training process not found! Aborting."
    exit 1
fi

echo "⏳ Found Training PID: $PID. Waiting for it to finish..."

# 2. Wait for training to complete
tail --pid=$PID -f /dev/null

echo "✅ Training completed."

# 3. Run Evaluation
echo "🚀 Starting Evaluation Pipeline..."
export HF_ENDPOINT=https://hf-mirror.com
cd ~/agent-lightning

# Ensure the script is executable
chmod +x run_full_evaluation.sh

# Run evaluation and save output
./run_full_evaluation.sh > final_evaluation_report.log 2>&1

echo "✅ Evaluation completed. Report saved to ~/agent-lightning/final_evaluation_report.log"

# 4. Shutdown
echo "🛑 Shutting down VM in 60 seconds to save costs..."
sleep 60
shutdown -h now
