# Embedded C++ Code Generation: SFT + RL Training

This project demonstrates how to train an embedded C++ code generation model using **SFT + GRPO**, suitable for customers with large embedded codebases (e.g., home appliance manufacturers).

*Author: Xinyu Wei (Microsoft GBB AI Architect)*

---

## 🎯 Core Problem: How to Verify Code Correctness?

### Math Problems vs Code Generation

| Task Type | Answer Form | Verification |
|-----------|-------------|--------------|
| Math | Single value | `answer == gold_answer` |
| Code | **Multiple implementations** | `pass_all_tests(code)` |

**The same function can have 100 different but correct implementations!**

```
Training math problems:
  Question: 2x + 3 = 7, find x
  Answer: x = 2  ← Only one correct answer, exact match

Training code generation:
  Question: Write a GPIO initialization function
  Answer: ??? ← Countless correct implementations!
```

---

## 📊 DeepSeek-R1's Code Training Approach

DeepSeek-R1 paper explicitly describes their code training method:

> *"For coding problems, we utilize a compiler to verify the correctness of the generated code based on predefined test cases."*

**Core Method: Rule-Based Rewards**

```python
def reward_code(generated_code, test_cases):
    """
    DeepSeek-R1's code reward function
    """
    # 1. Compile code
    try:
        compiled = compile_code(generated_code)
    except:
        return 0.0  # Compilation failed, reward 0
    
    # 2. Run test cases
    passed = 0
    for test in test_cases:
        try:
            result = run(compiled, test["input"])
            if result == test["expected_output"]:
                passed += 1
        except:
            pass  # Runtime error
    
    # 3. Calculate pass rate as reward
    return passed / len(test_cases)  # 0.0 ~ 1.0
```

### Key Insight: **RL Phase Doesn't Need Ground Truth!**

```
Traditional SFT approach:
  Question → Ground truth → Cross-entropy loss

R1's RL approach:
  Question → Model generates code → Compile & execute → Test passed? → Reward
```

**As long as tests pass, reward regardless of code style!**

---

## 🔧 Reward Function Design for Embedded Code

| Verification | Use Case | Reward Score |
|--------------|----------|--------------|
| **Syntax check** | All code | +3 (pass) / -2 (fail) |
| **Compilation** | Compilable code | +5 (pass) / -1 (fail) |
| **Static analysis** | Code quality | +1 (no warnings) |
| **Unit tests** | With test cases | +10 × pass_rate |
| **Hardware state** | Embedded-specific | +5 (correct state) |

### Reward Functions in This Project

```python
# 1. Format reward - Check required markers
def reward_format(completions):
    # Check <think>...</think> and <code>...</code> markers
    ...

# 2. Syntax reward - Fast syntax check (milliseconds)
def reward_syntax(completions):
    # Use clang -fsyntax-only
    ...

# 3. Compile reward - Full cross-compilation
def reward_compile(completions):
    # Use arm-none-eabi-gcc cross compiler
    ...

# 4. Static analysis reward
def reward_static_analysis(completions):
    # Use cppcheck for code quality
    ...
```

---

## 📋 Training Pipeline

### Phase 1: SFT (Supervised Fine-Tuning)

**Purpose**: Teach the model code format and style

```json
{
  "instruction": "Initialize UART1 with baud rate 115200",
  "output": "<think>Need to configure UART peripheral...</think>\n<code>\nvoid UART1_Init() {...}\n</code>"
}
```

**Example code is needed here, but only to teach "how to write", not the only correct answer.**

### Phase 2: RL/GRPO (Reinforcement Learning)

**Purpose**: Use verifiable rewards to improve code correctness

| Training Phase | Need Ground Truth? | Verification |
|----------------|-------------------|--------------|
| **SFT** | ✅ Need examples | Cross-entropy loss |
| **RL** | ❌ Not needed | Verifiable rewards (compile/test) |

---

## 🚀 Quick Start

### Requirements

- GPU: H100 / A100 (80GB VRAM recommended)
- Toolchain: `arm-none-eabi-gcc`, `clang`, `cppcheck`

### Install Dependencies

```bash
# System dependencies
apt-get install -y clang cppcheck gcc-arm-none-eabi

# Python dependencies
pip install unsloth trl transformers datasets accelerate peft vllm
```

### Run Training

```bash
# Quick test (5 GRPO steps)
./run_train.sh test

# SFT only
./run_train.sh sft

# GRPO only
./run_train.sh grpo

# Full SFT + GRPO
./run_train.sh full

# Full training with compile verification (slower)
./run_train.sh full_compile
```

### Run Inference

```bash
python embedded_infer.py \
    --model_dir outputs_embedded/embedded_coder_final \
    --task "Initialize GPIO PA5 as output for LED"
```

---

## 📁 Project Structure

```
embedded_sft_rl/
├── embedded_grpo_train.py   # Main training script
├── embedded_infer.py        # Inference script
├── run_train.sh             # Training launcher
├── requirements.txt         # Python dependencies
├── README.md                # Chinese documentation
└── README-EN.md             # English documentation (this file)
```

---

## 📊 Training Results

### Test Environment

| Config | Specification |
|--------|---------------|
| GPU | NVIDIA H100 80GB |
| Base Model | Qwen2.5-Coder-7B |
| Training Framework | Unsloth + TRL (GRPOTrainer) |
| Total Training Time | ~6 minutes |

### SFT Phase

| Step | Loss | Reduction |
|------|------|-----------|
| Step 10 | 1.36 | - |
| Step 20 | 0.56 | -59% |
| Step 30 | 0.14 | -90% |
| Step 40 | 0.07 | -95% |
| Step 50 | 0.03 | **-98%** |

**SFT Duration**: 44 seconds

### GRPO Phase

| Step | Total Reward | Format | Syntax | Notes |
|------|--------------|--------|--------|-------|
| 10 | 1.75 | 1.75 | 0.0 | Initial |
| 20 | 3.50 | 3.50 | 0.0 | Learning format |
| 30 | 3.88 | 3.50 | 0.38 | Starting to pass syntax |
| 40 | **4.95** | 3.50 | 1.45 | Peak reward |
| 50 | 3.88 | 3.50 | 0.38 | Stable |

**GRPO Duration**: 333 seconds (50 steps)

### Key Metrics

| Metric | Initial | Final | Change |
|--------|---------|-------|--------|
| SFT Loss | 1.36 | 0.03 | ↓98% |
| Total Reward | 1.75 | 3.88 | ↑122% |
| KL Divergence | - | 0.39 | Normal range |

### Inference Verification

```
Task: Initialize GPIO PA5 as output for LED control

Generated Code:
void GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_5;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

Syntax Check: ✅ PASSED
```

---

## ⚠️ Troubleshooting

### Issue 1: `stm32f4xx_hal.h` not found

**Symptom**:
```
fatal error: 'stm32f4xx_hal.h' file not found
```

**Cause**: Embedded code depends on STM32 HAL library headers, but the training environment doesn't have the full STM32 SDK installed.

**Solution**: Use stub headers that define only necessary types and macros:

```c
// Stub header example
typedef struct { uint32_t Pin; uint32_t Mode; ... } GPIO_InitTypeDef;
#define GPIO_PIN_5 0x0020
#define GPIO_MODE_OUTPUT_PP 0x01
void HAL_GPIO_Init(void* port, GPIO_InitTypeDef* init);
```

### Issue 2: `GPIO_PIN_RESET` undefined

**Symptom**:
```
error: use of undeclared identifier 'GPIO_PIN_RESET'
```

**Cause**: Generated code uses HAL library enum values, but stub headers missed them.

**Solution**: Add macro definitions to stub headers:

```c
#define GPIO_PIN_RESET 0
#define GPIO_PIN_SET 1
```

### Issue 3: Generated code missing `#include`

**Symptom**: Model sometimes generates code without header includes, causing syntax check failures.

**Solution**: Auto-prepend stub headers in inference script:

```python
# embedded_infer.py
full_code = STM32_STUB_HEADERS + "\n" + extracted_code
```

---

## 🎯 Customer Deployment Guide

```
Step 1: Collect customer's codebase
       ↓
Step 2: Extract "task-code" pairs from codebase (for SFT)
       ↓
Step 3: Write test cases for common tasks (for RL rewards)
       ↓
Step 4: SFT to teach model format and style
       ↓
Step 5: RL using test pass rate as reward to improve correctness
```

### Embedded Code Test Case Format

```json
{
  "task": "Implement an LED blink function",
  "test_cases": [
    {
      "description": "LED should be LOW after initialization",
      "expected_state": {"PA5": 0}
    },
    {
      "description": "LED should be HIGH after toggle",
      "expected_state": {"PA5": 1}
    }
  ]
}
```

### Using QEMU for Verification (Advanced)

```python
def reward_hardware_state(code, expected_state):
    """Run code in emulator, verify hardware state"""
    emulator = QEMUEmulator("stm32f4")
    emulator.load_code(code)
    emulator.run(timeout=1000)
    
    score = 0
    if emulator.gpio_state("PA5") == expected_state["PA5"]:
        score += 5.0
    return score
```

---

## ⚠️ FAQ

1. **Open-ended tasks**: For tasks difficult to define test cases, use LLM-as-Judge as reward
2. **Long code**: Split into small functions, test each function individually
3. **Compile dependencies**: Ensure STM32 HAL headers are available (this project uses stub headers)

---

## 📚 References

- [DeepSeek-R1 Paper](https://arxiv.org/abs/2401.02954) - Rule-based rewards for code
- [TRL GRPO Trainer](https://huggingface.co/docs/trl/main/grpo_trainer) - GRPO training framework
- [Unsloth](https://github.com/unslothai/unsloth) - Efficient fine-tuning framework

---

## 📝 License

MIT License

---

*Last Updated: 2025-12-16*

---

## �� Appendix: SFT Tuning Best Practices

> This section summarizes experience from **7 rounds of parameter optimization** that improved model accuracy from 0% to 100%.

### Common Problem Diagnosis

| Symptom | Cause | Solution |
|---------|-------|----------|
| Completely irrelevant answers after training | Dataset too small / format error | Check data format, expand dataset |
| Validation loss decreasing too slowly | Overfitting | Increase dropout, expand data |
| Training normal but answers wrong | Model didn't learn knowledge | Add CoT, use English corpus |
| Inconsistent answers for same question | Sampling randomness | Set `temperature=0` during inference |

### 7 Rounds of Tuning Experience

| Round | Adjustment | Result |
|-------|------------|--------|
| 1 | Baseline training | ❌ Completely irrelevant answers |
| 2 | `lora_dropout=0.05`, epochs 30→100 | ❌ Still overfitting |
| 3 | Dataset 30→3000 samples, train/val=0.7/0.3 | ⚠️ Overfitting solved, but answers still wrong |
| 4 | Added **Chain of Thought (CoT)**, switched to English corpus | ⚠️ 50% accuracy |
| 5 | **Data augmentation**: random insert/swap/delete/back-translation | ⚠️ Accuracy +10% |
| 6 | LoRA → **Full Fine-tuning** | ⚠️ Big improvement, but unstable answers |
| 7 | `learning_rate=5e-4`, inference `temperature=0` | ✅ 100% accuracy |

### Key Parameter Settings

```python
# Training parameters
training_args = TrainingArguments(
    num_train_epochs=100,
    learning_rate=5e-4,           # 10x higher than default 5e-5
    gradient_accumulation_steps=32,
    per_device_train_batch_size=1,
    warmup_steps=100,
    eval_strategy="steps",
    eval_steps=25,
)

# Inference parameters - ensure answer consistency
output = model.generate(
    inputs,
    do_sample=False,              # Disable random sampling
    temperature=0.0,              # Most deterministic generation
    max_new_tokens=512,
)
```

### Data Augmentation Techniques

Generate multiple training samples from single knowledge:

| Method | Description | Example |
|--------|-------------|---------|
| **Random Insert** | Insert unrelated words | "Initialize GPIO" → "Initialize **port** GPIO" |
| **Random Swap** | Swap adjacent words | "Configure UART baud" → "Configure baud UART" |
| **Random Delete** | Remove non-critical words | "Please initialize a GPIO pin" → "Initialize GPIO pin" |
| **Back-translation** | EN→CN→EN | "Initialize serial" → "初始化串口" → "Initialize serial port" |

### CoT (Chain of Thought) Example

```
Prompt: How to initialize UART for .NET Framework?

Completion:
**Step-by-Step Analysis:**
1. **Define Purpose**: Initialize UART peripheral for serial communication
2. **Code Structure**: Import HAL namespace, configure baud rate
3. **Key Parameters**: Baud=115200, WordLength=8, StopBits=1

**Code Sample**:
void UART_Init() {
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    HAL_UART_Init(&huart1);
}
```

### Key Lessons

1. **Data quantity > parameter tuning**: Expanding from 30 to 3000 samples was the turning point
2. **CoT works for code generation**: Let model analyze before writing code
3. **Full Fine-tuning > LoRA**: Complex tasks need larger adjustment capacity
4. **Inference parameters matter**: `temperature=0` ensures stable output
