# 嵌入式 C++ 代码生成：SFT + RL 训练方案

本项目演示如何使用 **SFT + GRPO** 训练一个嵌入式 C++ 代码生成模型，适用于白色家电厂商等有大量嵌入式代码库的客户场景。

*Author: Xinyu Wei (Microsoft GBB AI Architect)*

---

## 🎯 核心问题：代码训练如何验证正确性？

### 数学题 vs 代码生成

| 任务类型 | 答案形式 | 验证方式 |
|---------|---------|---------|
| 数学题 | 唯一数值 | `answer == gold_answer` |
| 代码题 | **多种实现** | `pass_all_tests(code)` |

**同一个功能可能有 100 种不同但都正确的实现！**

```
训练数学题时：
  问题：2x + 3 = 7，求 x
  答案：x = 2  ← 唯一正确答案，可以精确匹配

训练代码生成时：
  问题：写一个 GPIO 初始化函数
  答案：??? ← 有无数种正确写法！
```

---

## 📊 DeepSeek-R1 的代码训练方案

DeepSeek-R1 论文明确说明了代码训练的方法：

> *"For coding problems, we utilize a compiler to verify the correctness of the generated code based on predefined test cases."*

**核心方法：Rule-Based Rewards（基于规则的奖励）**

```python
def reward_code(generated_code, test_cases):
    """
    DeepSeek-R1 的代码奖励函数
    """
    # 1. 编译代码
    try:
        compiled = compile_code(generated_code)
    except:
        return 0.0  # 编译失败，奖励 0
    
    # 2. 运行测试用例
    passed = 0
    for test in test_cases:
        try:
            result = run(compiled, test["input"])
            if result == test["expected_output"]:
                passed += 1
        except:
            pass  # 运行时错误
    
    # 3. 计算通过率作为奖励
    return passed / len(test_cases)  # 0.0 ~ 1.0
```

### 关键洞察：**RL 阶段不需要标准答案！**

```
传统 SFT 思路：
  问题 → 标准答案 → 交叉熵 loss

R1 的 RL 思路：
  问题 → 模型生成代码 → 编译执行 → 测试通过？ → 奖励
```

**只要测试通过，不管代码怎么写都给奖励！**

---

## 🔧 嵌入式代码的奖励函数设计

| 验证方式 | 适用场景 | 奖励分数 |
|---------|---------|---------|
| **语法检查** | 所有代码 | +3 (通过) / -2 (失败) |
| **编译通过** | 可编译代码 | +5 (通过) / -1 (失败) |
| **静态分析** | 代码质量 | +1 (无警告) |
| **单元测试** | 有测试用例 | +10 × 通过率 |
| **硬件状态验证** | 嵌入式专用 | +5 (状态正确) |

### 本项目的奖励函数

```python
# 1. 格式奖励 - 检查必要标记
def reward_format(completions):
    # 检查 <think>...</think> 和 <code>...</code> 标记
    ...

# 2. 语法奖励 - 快速语法检查（毫秒级）
def reward_syntax(completions):
    # 使用 clang -fsyntax-only 检查
    ...

# 3. 编译奖励 - 完整交叉编译
def reward_compile(completions):
    # 使用 arm-none-eabi-gcc 交叉编译
    ...

# 4. 静态分析奖励
def reward_static_analysis(completions):
    # 使用 cppcheck 检查代码质量
    ...
```

---

## 📋 训练流程

### 阶段 1：SFT（监督微调）

**目的**：教模型代码格式和风格

```json
{
  "instruction": "初始化 UART1，波特率 115200",
  "output": "<think>需要配置 UART 外设...</think>\n<code>\nvoid UART1_Init() {...}\n</code>"
}
```

**这里需要示例代码，但只是教模型"怎么写"，不是唯一正确答案。**

### 阶段 2：RL/GRPO（强化学习）

**目的**：用可验证奖励提升代码正确性

| 训练阶段 | 需要标准答案？ | 验证方式 |
|---------|--------------|---------|
| **SFT** | ✅ 需要示例 | 交叉熵 loss |
| **RL** | ❌ 不需要 | 可验证奖励（编译/测试） |

---

## 🚀 快速开始

### 环境要求

- GPU: H100 / A100 (推荐 80GB 显存)
- 工具链: `arm-none-eabi-gcc`, `clang`, `cppcheck`

### 安装依赖

```bash
# 系统依赖
apt-get install -y clang cppcheck gcc-arm-none-eabi

# Python 依赖
pip install unsloth trl transformers datasets accelerate peft vllm
```

### 运行训练

```bash
# 快速测试（5 步 GRPO）
./run_train.sh test

# 仅 SFT
./run_train.sh sft

# 仅 GRPO
./run_train.sh grpo

# 完整 SFT + GRPO
./run_train.sh full

# 完整训练（含编译验证，较慢）
./run_train.sh full_compile
```

### 推理测试

```bash
python embedded_infer.py \
    --model_dir outputs_embedded/embedded_coder_final \
    --task "Initialize GPIO PA5 as output for LED"
```

---

## 📁 项目结构

```
embedded_sft_rl/
├── embedded_grpo_train.py   # 主训练脚本
├── embedded_infer.py        # 推理脚本
├── run_train.sh             # 训练启动脚本
├── requirements.txt         # Python 依赖
└── README.md                # 本文档
```

---

## 📊 训练效果

### 测试环境

| 配置 | 规格 |
|------|------|
| GPU | NVIDIA H100 80GB |
| 基座模型 | Qwen2.5-Coder-7B |
| 训练框架 | Unsloth + TRL (GRPOTrainer) |
| 总训练时间 | ~6 分钟 |

### SFT 阶段

| Epoch | Loss | 下降幅度 |
|-------|------|----------|
| Step 10 | 1.36 | - |
| Step 20 | 0.56 | -59% |
| Step 30 | 0.14 | -90% |
| Step 40 | 0.07 | -95% |
| Step 50 | 0.03 | **-98%** |

**SFT 耗时**: 44 秒

### GRPO 阶段

| Step | Total Reward | Format | Syntax | 说明 |
|------|--------------|--------|--------|------|
| 10 | 1.75 | 1.75 | 0.0 | 初始阶段 |
| 20 | 3.50 | 3.50 | 0.0 | 格式学习中 |
| 30 | 3.88 | 3.50 | 0.38 | 开始通过语法 |
| 40 | **4.95** | 3.50 | 1.45 | 峰值奖励 |
| 50 | 3.88 | 3.50 | 0.38 | 稳定 |

**GRPO 耗时**: 333 秒 (50 steps)

### 关键指标

| 指标 | 初始值 | 最终值 | 变化 |
|------|--------|--------|------|
| SFT Loss | 1.36 | 0.03 | ↓98% |
| Total Reward | 1.75 | 3.88 | ↑122% |
| KL Divergence | - | 0.39 | 正常范围 |

### 推理验证

```
任务: Initialize GPIO PA5 as output for LED control

生成代码:
void GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_5;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

语法检查: ✅ PASSED
```

---

## ⚠️ 踩坑记录

### 问题 1: `stm32f4xx_hal.h` 找不到

**症状**:
```
fatal error: 'stm32f4xx_hal.h' file not found
```

**原因**: 嵌入式代码依赖 STM32 HAL 库头文件，但训练环境没有安装完整的 STM32 SDK。

**解决方案**: 使用 stub 头文件，只定义必要的类型和宏：

```c
// stub 头文件示例
typedef struct { uint32_t Pin; uint32_t Mode; ... } GPIO_InitTypeDef;
#define GPIO_PIN_5 0x0020
#define GPIO_MODE_OUTPUT_PP 0x01
void HAL_GPIO_Init(void* port, GPIO_InitTypeDef* init);
```

### 问题 2: `GPIO_PIN_RESET` 未定义

**症状**:
```
error: use of undeclared identifier 'GPIO_PIN_RESET'
```

**原因**: 生成的代码使用了 HAL 库的枚举值，但 stub 头文件遗漏了。

**解决方案**: 在 stub 头文件中添加宏定义：

```c
#define GPIO_PIN_RESET 0
#define GPIO_PIN_SET 1
```

### 问题 3: 生成代码缺少 `#include`

**症状**: 模型有时生成的代码不包含头文件引用，导致语法检查失败。

**解决方案**: 在推理脚本中自动 prepend stub 头文件：

```python
# embedded_infer.py
full_code = STM32_STUB_HEADERS + "\n" + extracted_code
```

---

## 🎯 客户场景实操建议

```
Step 1: 收集客户的代码库
       ↓
Step 2: 从代码库提取 "任务-代码" 对（用于 SFT）
       ↓
Step 3: 为常见任务编写测试用例（用于 RL 奖励）
       ↓
Step 4: SFT 教模型格式和风格
       ↓
Step 5: RL 用测试通过率作为奖励，提升功能正确性
```

### 嵌入式代码测试用例格式

```json
{
  "task": "实现一个 LED 闪烁函数",
  "test_cases": [
    {
      "description": "LED 初始化后应为低电平",
      "expected_state": {"PA5": 0}
    },
    {
      "description": "调用 toggle 后应为高电平",
      "expected_state": {"PA5": 1}
    }
  ]
}
```

### 使用 QEMU 模拟验证（高级）

```python
def reward_hardware_state(code, expected_state):
    """在模拟器中运行代码，验证硬件状态"""
    emulator = QEMUEmulator("stm32f4")
    emulator.load_code(code)
    emulator.run(timeout=1000)
    
    score = 0
    if emulator.gpio_state("PA5") == expected_state["PA5"]:
        score += 5.0
    return score
```

---

## ⚠️ 常见问题

1. **开放式任务**：对于难以定义测试用例的任务，可以使用 LLM-as-Judge 作为奖励
2. **长代码处理**：拆分成小函数，每个函数单独测试
3. **编译依赖**：确保 STM32 HAL 头文件可用（本项目使用 stub 头文件）

---

## 📚 参考资料

- [DeepSeek-R1 论文](https://arxiv.org/abs/2401.02954) - Rule-based rewards for code
- [TRL GRPO Trainer](https://huggingface.co/docs/trl/main/grpo_trainer) - GRPO 训练框架
- [Unsloth](https://github.com/unslothai/unsloth) - 高效微调框架

---

## 📝 License

MIT License

---

*Last Updated: 2025-12-16*

---

## 📖 附录：SFT 调参最佳实践

> 本节总结了通过 **7 轮参数优化** 将模型准确率从 0% 提升到 100% 的经验。

### 常见问题诊断

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 训练后回答完全无关 | 数据集太小 / 格式错误 | 检查数据格式，扩充数据集 |
| Validation loss 下降太慢 | 过拟合 | 增加 dropout、扩充数据 |
| 训练正常但答案错误 | 模型没学到知识 | 添加 CoT、改用英文语料 |
| 同一问题答案不一致 | 采样随机性 | 推理时设 `temperature=0` |

### 7 轮调参经验

| 轮次 | 调整内容 | 效果 |
|------|----------|------|
| 1 | 基础训练 | ❌ 回答完全无关 |
| 2 | `lora_dropout=0.05`, epochs 30→100 | ❌ 仍过拟合 |
| 3 | 数据集 30→3000 条，train/val=0.7/0.3 | ⚠️ 过拟合解决，但答案仍错 |
| 4 | 添加 **Chain of Thought (CoT)**，改全英文语料 | ⚠️ 50% 准确率 |
| 5 | **数据增强**：随机插入/交换/删除/回译 | ⚠️ 准确率 +10% |
| 6 | LoRA → **Full Fine-tuning** | ⚠️ 大幅提升，但答案不稳定 |
| 7 | `learning_rate=5e-4`, 推理 `temperature=0` | ✅ 100% 准确率 |

### 关键参数设置

```python
# 训练参数
training_args = TrainingArguments(
    num_train_epochs=100,
    learning_rate=5e-4,           # 比默认 5e-5 高 10 倍
    gradient_accumulation_steps=32,
    per_device_train_batch_size=1,
    warmup_steps=100,
    eval_strategy="steps",
    eval_steps=25,
)

# 推理参数 - 确保答案一致性
output = model.generate(
    inputs,
    do_sample=False,              # 禁用随机采样
    temperature=0.0,              # 最确定性的生成
    max_new_tokens=512,
)
```

### 数据增强技巧

为单条知识生成多条训练数据：

| 方法 | 说明 | 示例 |
|------|------|------|
| **随机插入** | 在句子中插入无关词 | "初始化 GPIO" → "初始化 **端口** GPIO" |
| **随机交换** | 交换相邻词顺序 | "配置 UART 波特率" → "配置 波特率 UART" |
| **随机删除** | 删除非关键词 | "请初始化一个 GPIO 引脚" → "初始化 GPIO 引脚" |
| **回译** | 中→英→中 | "初始化串口" → "Initialize serial" → "初始化串行端口" |

### CoT (Chain of Thought) 示例

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

### 核心教训

1. **数据量 > 参数调优**：从 30 条扩到 3000 条是关键转折点
2. **CoT 对代码生成有效**：让模型先分析再写代码
3. **Full Fine-tuning > LoRA**：复杂任务需要更大调整幅度
4. **推理参数很重要**：`temperature=0` 确保输出稳定
