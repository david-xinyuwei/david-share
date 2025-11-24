# AI Super Agent: H100 训练验证项目

##  项目概述

本项目验证了在 **Azure H100 (80GB)** 环境下,使用 **Agent Lightning + GRPO 算法**训练数学推理Agent的完整流程。从数据生成、模型训练到性能评估,所有步骤均已在实际硬件上成功运行并记录。

**核心成果**:
-  使用 Azure OpenAI GPT-5.1 生成 5000+ 高质量数学训练数据
-  GRPO算法训练 Qwen2.5-3B 模型,节省50%显存
-  GSM8K准确率从81.0%提升至84.0% (+3.0%)
-  MATH数据集准确率从69.0%提升至73.0% (+4.0%)
-  实现类似OpenAI o1的深度推理能力(Deep Thinking)

---

##  快速开始(4步完整流程)

### 步骤1: 生成训练数据
```bash
python generate_training_data_gpt5.py
# 输出: data/train_gpt5_large.parquet (5000+条)
#      data/test_gpt5_large.parquet (500条)
```

### 步骤2: 训练模型
```bash
python train_math_agent_vllm.py
# 训练时长: H100约2小时, A100约3小时
# 输出: checkpoints/math_agent/global_step_100/
```

### 步骤3: 转换模型
```bash
python convert_checkpoint.py \
    --checkpoint_dir checkpoints/math_agent/global_step_100 \
    --base_model Qwen/Qwen2.5-3B-Instruct \
    --output_dir merged_model
```

### 步骤4: 评估性能
```bash
# 准备数据集
python prepare_gsm8k.py
python prepare_math.py

# 一键评估
bash run_full_evaluation_v5.sh
# 输出: validation_report.txt
```

---

## 📊 核心技术亮点

### 1. GRPO算法 - 节省50%显存
不需要Critic模型,通过对同一问题采样一组输出(n=4)计算组内相对优势来优化策略。

### 2. Deep Thinking奖励函数
多维度激励模型进行长链推理:

| 奖励类型 | 分数 | 触发条件 |
|---------|-----|---------|
| 结构奖励 | +0.5 | 包含<think>和<answer>标签 |
| 正确性奖励 | +2.0 | 答案与标准答案一致 |
| 深度奖励 | +0.5 | 思考过程存在且答案正确 |
| 长度奖励 | 0~1.0 | 根据<think>内容长度动态计算 |

### 3. 实验结果

**GSM8K**: 81.0%  84.0% (+3.0%)  
**MATH**: 69.0%  73.0% (+4.0%)

---

##  硬件适配经验

### A10 (24GB) 失败
即使0.5B模型也会OOM,原因:
- 需同时加载Actor和Reference两个模型
- vLLM引擎KV Cache预占
- Ray框架开销

### H100 (80GB) 成功
-  3B模型训练稳定
-  支持更大batch size
- **建议**: 生产环境至少40GB+显存

---

##  核心文件

- `train_math_agent_vllm.py` - 训练脚本(GRPO+Deep Thinking)
- `generate_training_data_gpt5.py` - 数据生成
- `judge_with_llm.py` - LLM评判器
- `convert_checkpoint.py` - 模型转换
- `prepare_gsm8k.py` / `prepare_math.py` - 数据集准备
- `run_full_evaluation_v5.sh` - 一键评估
- `agentL_h100.yml` - H100环境配置

---

##  环境搭建

```bash
conda create -n agentL python=3.11 -y
conda activate agentL
pip install torch==2.5.1 vllm==0.7.0 verl==0.5.0 ray==2.10.0
# 完整依赖见agentL_h100.yml
```

**环境变量**:
```bash
export AZURE_OPENAI_ENDPOINT="https://xxx.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="gpt-5.1-chat"
```

---

**维护**: David Wei | **更新**: 2025-11-24 | **硬件**: Azure H100 (80GB)
