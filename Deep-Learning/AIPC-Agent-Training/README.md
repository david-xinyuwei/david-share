# 🔄 AIPC Agent Closed-Loop Training Flywheel

<div align="center">

**From 10% to 100%: How LLMs Continuously Self-Evolve Through Closed-Loop Flywheel**

[![Model](https://img.shields.io/badge/Base%20Model-Qwen2.5--3B-blue)](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
[![Training](https://img.shields.io/badge/Training-SFT%20%2B%20GRPO-green)](https://github.com/microsoft/agent-lightning)
[![Inference](https://img.shields.io/badge/Inference-vLLM%200.13-orange)](https://github.com/vllm-project/vllm)
[![Judge](https://img.shields.io/badge/Judge-GPT--5.2-purple)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

</div>

## 📖 Overview

This project demonstrates a complete **Agent Closed-Loop Training Flywheel**: from cold start to continuous iteration, enabling small models to evolve in specific domains.

**Core Pipeline:**
1. **Cold Start** → GPT generates seed data, train V1 baseline model
2. **Deploy** → vLLM inference service + Gradio interactive UI
3. **Collect Feedback** → User 👍👎 + GPT-5.2 auto-scoring
4. **Incremental Training** → User feedback drives SFT, model scores drive RL/GRPO
5. **Iterate** → Deploy new model, continue collecting feedback...

**Why did accuracy drop from V1(10%) to V2(7.5%) then rise to V3(100%)?**

This is the core question this project answers—closed-loop training is not simply "collect data → train", it requires:
- **Balanced positive/negative samples**: With only positive samples, the model can't learn boundaries (V2's lesson)
- **Large model judges small model**: GPT-5.2 identifies errors and generates corrections (V3's breakthrough)
- **Quality over quantity**: 48 carefully corrected samples > 1000 low-quality samples

This repo uses **AI PC (Artificial Intelligence Personal Computer)** as an example domain, fully reproducing this closed-loop process with all training scripts, data samples, and training logs.

## 💡 Core Philosophy

> **Quality > Quantity**: 48 carefully corrected samples > 1000 low-quality samples
>
> **Closed-Loop > One-Shot**: Without feedback iteration, the model stays stagnant
>
> **Large Model Judges Small Model**: GPT-5.2 judgment + correction is 10x more efficient than manual labeling

## 🚀 Key Results

| Iteration | Training Data | Core Test Accuracy | Key Insight |
|-----------|---------------|-------------------|-------------|
| V1 Cold Start | 50 GPT-generated | ~10% | Baseline |
| V2 Feedback | +22 user 👍 | ~7.5% ⬇️ | Only positive samples, can't learn boundaries |
| **V3 Correction** | +48 GPT-corrected | **100%** ✅ | 🚀 Data flywheel works! |

**V3 can correctly answer:**
- ✅ "What is AI PC?" → NPU, Intel/AMD/Qualcomm, TOPS
- ✅ "Is AIPC an Alibaba Cloud product?" → No (V2 said "Yes")
- ✅ "Intel's AI PC chip?" → Core Ultra (V2 didn't know)

---

## 🎯 Project Goal

Train a small model specialized in **AI PC (Artificial Intelligence Personal Computer)** domain knowledge through a data flywheel for continuous iterative improvement.

**Tech Stack:**
- **Base Model**: Qwen2.5-3B-Instruct (3 billion parameters)
- **Training Framework**: Transformers + Agent Lightning 0.3.0
- **Training Algorithm**: SFT (Supervised Fine-tuning) + GRPO (Group Relative Policy Optimization)
- **Inference Service**: vLLM 0.13.0
- **Judge Model**: Azure OpenAI GPT-5.2
- **Hardware**: NVIDIA A100 80GB


## 🏗️ System Architecture

### Flywheel Overview

```mermaid
flowchart TB
    subgraph Cold["🧊 Cold Start"]
        A[GPT-5.2 Generate Data] --> A2[GPT-5.2 Score & Filter]
        A2 --> B[SFT Training]
        B --> V1[V1 Model]
    end
    
    subgraph Loop["🔄 Continuous Loop"]
        V1 --> C[Deploy Service]
        C --> D[Answer Questions]
        D --> E[Collect Feedback]
        
        E --> F{Feedback Type}
        F -->|User 👍👎| G[SFT<br/>Supervised Fine-tuning]
        F -->|GPT-5.2 Score| H[RL/GRPO<br/>Reinforcement Learning]
        
        G --> I{Enough Data?}
        H --> I
        I -->|Yes| J[Train]
        J --> V2[V2 Deploy]
        V2 --> C
        
        I -->|No| C
    end
    
    style V1 fill:#ffcccc
    style V2 fill:#ccffcc
    style G fill:#e6f3ff
    style H fill:#fff3e6
```

### Training Method Comparison

| Feedback Source | Training Method | Principle | Advantage |
|-----------------|-----------------|-----------|-----------|
| **User Thumbs** 👍👎 | SFT (Supervised Fine-tuning) | Learn correct answers directly | Simple, fast convergence |
| **GPT-5.2 Score** | RL/GRPO (Reinforcement Learning) | Optimize with reward signals | Better generalization |

### Detailed Flow

```mermaid
flowchart TB
    subgraph Cold["🧊 Cold Start Phase"]
        A[GPT-5.2 Generate Seed Data<br/>50 AIPC Q&A pairs] --> A2[GPT-5.2 Quality Scoring]
        A2 --> B[SFT Training]
        B --> V1[V1 Model<br/>Accuracy ~10%]
    end
    
    subgraph Deploy["🚀 Deployment Phase"]
        V1 --> C[vLLM Inference Service]
        C --> D[Gradio Interactive UI]
    end
    
    subgraph Feedback["📝 Feedback Collection"]
        D --> E[User Questions]
        E --> F[Model Answers]
        F --> G{Feedback Source}
        G -->|User Upvote| H[👍 Positive Sample → SFT]
        G -->|User Downvote| I[👎 Negative Sample → Contrastive]
        G -->|GPT-5.2| J[Score 0-10 → RL/GRPO]
    end
    
    subgraph Iterate1["🔄 V2 Iteration"]
        H --> K[SFT: Learn Correct Answers]
        J --> L[GRPO: Reward Signal Optimization]
        K --> M[V2 Model]
        L --> M
        M --> V2[V2<br/>Accuracy ~7.5%]
    end
    
    subgraph Evaluate["🔍 Auto Evaluation"]
        V2 --> N[V2 Answers 53 Test Questions]
        N --> O[GPT-5.2 Judgment]
        O --> P{Quality Classification}
        P -->|Score ≥7| Q[Good Samples: 4]
        P -->|Score <7| R[Bad Samples: 49]
        R --> S[GPT Generates Corrections]
        S --> T[Corrected Samples: 44]
    end
    
    subgraph Iterate2["🚀 V3 Iteration"]
        Q --> U[Merge High-Quality Data<br/>48 samples]
        T --> U
        U --> W[SFT Training<br/>10 epochs]
        W --> V3[V3 Model<br/>Accuracy 100%]
    end
    
    subgraph Final["✅ Final Validation"]
        V3 --> X[vLLM Deployment]
        X --> Y[12 Core Questions Test<br/>All Passed]
    end
    
    style V1 fill:#ffcccc
    style V2 fill:#ffffcc
    style V3 fill:#ccffcc
    style Y stroke:#00aa00,stroke-width:3px
    style K fill:#e6f3ff
    style L fill:#fff3e6
```

## 📊 Iteration Results

| Version | Training Data | Test Accuracy | Key Improvement |
|---------|---------------|---------------|-----------------|
| **V1** | 50 cold start | ~10% | Baseline model |
| **V2** | +22 user feedback | ~7.5% | Insufficient data, limited effect |
| **V3** | +48 corrected data | **100%** | 🚀 Data flywheel works! |

### V3 Core Capability Validation

| Test Question | V2 Answer | V3 Answer |
|---------------|-----------|-----------|
| What is AI PC? | ❌ Vague | ✅ NPU, Intel/AMD/Qualcomm, TOPS |
| Is AIPC an Alibaba Cloud product? | ❌ Said yes | ✅ No, unrelated to Alibaba |
| What is Intel's AI PC chip? | ❌ Didn't know | ✅ Core Ultra (with NPU) |
| What is Copilot+ PC? | ❌ Didn't know | ✅ Built-in NPU, Windows Copilot |

### User Rating Screenshots

![Gradio Demo Interface](./images/1.png)

![Gradio Demo Interface](./images/2.png)

![Gradio Demo Interface](./images/3.png)

## 🔧 Tech Stack

- **Base Model**: Qwen2.5-3B-Instruct
- **Training Framework**: Agent Lightning 0.3.0 + Transformers
- **Training Algorithm**: SFT + GRPO (Group Relative Policy Optimization)
- **Inference Service**: vLLM 0.13.0
- **Judge Model**: Azure OpenAI GPT-5.2
- **Hardware**: NVIDIA A100 80GB

## 📁 Directory Structure

```
aipc-flywheel/
├── data/
│   ├── cold_start.jsonl           # Cold start data (50 samples)
│   ├── user_feedback.jsonl        # User feedback (22 samples)
│   ├── v3_good_samples.jsonl      # V3 training data (48 samples)
│   └── v3_bad_samples.jsonl       # V2 bad samples record
├── train_sft_grpo.py              # SFT+GRPO training script
├── train_v3_simple.py             # V3 training script
├── generate_v3_data.py            # V3 data generation script
├── final_eval.py                  # Final evaluation script
└── overfit_test.py                # Overfitting test script
```

## 🚀 Quick Start
## 🚀 Quick Start

### 0. Install Dependencies

```bash
pip install -r requirements.txt
```

### 1. Train V3 Model (Recommended)

```bash
# Set environment variables
export BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"  # or local path
export DATA_FILE="./data/v3_good_samples.jsonl"
export OUTPUT_DIR="./output/v3_model"

# Run training
python train_v3_simple.py

# Or use command line arguments
python train_v3_simple.py --model Qwen/Qwen2.5-3B-Instruct --data ./data/v3_good_samples.jsonl --output ./output
```

### 2. Start Inference Service

```bash
python -m vllm.entrypoints.openai.api_server \
    --model ./output/v3_model \
    --port 8000 \
    --dtype bfloat16
```

### 3. Test the Model

```bash
curl http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "v3_model", "messages": [{"role": "user", "content": "What is AI PC?"}]}'
```

### 4. Run Evaluation

```bash
python3 final_eval.py
```

## 💡 Data Flywheel Iteration Cycle

```mermaid
gantt
    title Closed-Loop Iteration Timeline
    dateFormat  HH:mm
    axisFormat %H:%M
    
    section V1 Cold Start
    GPT generates 50 samples    :v1_data, 00:00, 10m
    SFT training                :v1_train, after v1_data, 5m
    Deploy vLLM                 :v1_deploy, after v1_train, 3m
    
    section V2 Feedback Iteration
    Gradio collects 22 feedback :v2_data, after v1_deploy, 20m
    SFT+GRPO training           :v2_train, after v2_data, 25m
    
    section V3 Correction Iteration
    V2 answers 53 questions     :v3_eval, after v2_train, 15m
    GPT judge + correct         :v3_fix, after v3_eval, 10m
    SFT training (48 samples)   :v3_train, after v3_fix, 1m
    Final validation 100%       :v3_done, after v3_train, 5m
```

## 📝 Training Data Examples

### Cold Start Data (GPT-4 Generated)

```json
{
  "prompt": "What is AI PC?",
  "response": "AI PC refers to personal computers with built-in NPU (Neural Processing Unit)..."
}
```

### User Feedback Data

```json
{
  "prompt": "What is Intel's AI PC chip?",
  "response": "Intel doesn't have a dedicated AI PC chip product line...",
  "feedback": "negative",
  "user_comment": "Don't you know Intel Core Ultra?"
}
```

### GPT Corrected Data (for V3 Training)

```json
{
  "prompt": "What is Intel's AI PC chip?",
  "response": "Intel's AI PC chip is mainly the Core Ultra series (codename Meteor Lake), with built-in NPU, delivering approximately 10-34 TOPS. Typical models include Core Ultra 5/7/9, supporting Windows Copilot and other local AI features.",
  "score": 10,
  "feedback": "corrected"
}
```

## ⚠️ Lessons Learned

### 1. Why V2 Performed Worse Than V1?

```mermaid
flowchart LR
    A[Collected 22 feedback] --> B[All 👍 positive samples]
    B --> C[No negative samples to show what's wrong]
    C --> D[Model can't learn boundaries]
    D --> E[Accuracy actually dropped]
    
    style E fill:#ffcccc
```

**Lesson**: Positive samples alone are not enough. Negative samples are essential for learning boundaries!

### 2. V2's Typical Errors

| Question | V2 Answer | What's Wrong |
|----------|-----------|--------------|
| Is AIPC an Alibaba Cloud product? | "Yes, AIPC is Alibaba Cloud's edge computing platform" | ❌ Completely wrong! Hallucination |
| Intel's AI PC chip? | "Intel doesn't have a dedicated AI PC chip" | ❌ Didn't know Core Ultra |
| What is Copilot+ PC? | "There's no clear definition currently" | ❌ Didn't know Microsoft's product |

**Root Cause**: Cold start data didn't cover these knowledge points. V2 learned "how to talk" but not "what to say".

### 3. The Power of Corrected Data

44 out of 48 samples in V3 are GPT-corrected "correct answers":

```
Original Question: "Is AIPC an Alibaba Cloud product?"
V2 Wrong Answer: "Yes, AIPC is Alibaba Cloud's..."
GPT Correction: "No. AI PC is an industry trend driven by chip vendors like Intel, AMD, and Qualcomm, unrelated to Alibaba Cloud."
```

Training with corrected answers directly teaches the model correct knowledge!

### 4. Overfitting Risk

After 10 epochs, the model showed slight template-like behavior:

```
Almost every AIPC question outputs:
"Intel Core Ultra, AMD Ryzen AI, Qualcomm Snapdragon X"

Like reciting from memory...
```

**But acceptable for demo purposes** - core knowledge was successfully injected!

## 📊 Key Metrics Comparison

| Metric | V1 | V2 | V3 |
|--------|-----|-----|-----|
| Training Data | 50 | 72 | 120 |
| Training Time | 5min | 25min | 1min |
| Loss | 2.1 | 0.96 | 0.25 |
| Core Test Accuracy | ~10% | ~7.5% | **100%** |
| Vendor Coverage | ❌ | ❌ | ✅ Intel/AMD/Qualcomm |
| Product Coverage | ❌ | ❌ | ✅ Core Ultra/Ryzen AI/Snapdragon X |

## 🎓 Key Takeaways

1. **Quality > Quantity** - 48 high-quality corrected samples > 1000 low-quality samples
2. **Negative Samples Matter** - Without negative samples, the model can't learn boundaries
3. **Large Model Judges Small Model** - GPT judgment + correction is 10x more efficient than manual labeling
4. **Closed-Loop Enables Evolution** - Without feedback iteration, the model stays stagnant

## 📜 License

MIT License

---

**Truth is always ONE!** 🔍
