#!/usr/bin/env python3
"""
Translate README-CN.md to English README.md
Uses line-by-line approach: Chinese lines get translated, English lines kept as-is.
All translations are hardcoded in this script (no API needed).
"""
import re, os

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

# ========== HEADING TRANSLATIONS ==========
HEADING_MAP = {
    # Repo A headings
    "# Part 1: SFT 超参调优最佳实践": "# Part 1: SFT Hyperparameter Tuning Best Practices",
    "# Part 2: 各种微调方法全景对比": "# Part 2: Overview of Various Fine-Tuning Methods",
    "# Part 3: 强化学习与微调的本质区别": "# Part 3: Fundamental Differences Between RL and Fine-Tuning",
    "# Part 4: 七种微调技术对比总表": "# Part 4: Comparison Table of Seven Fine-Tuning Techniques",
    "# Part 5: LoRA/QLoRA 微调机制与 GaLore 全量微调": "# Part 5: LoRA/QLoRA Fine-Tuning Mechanisms and GaLore Full Fine-Tuning",
    "# Part 6: DPO 理论深入与对齐实践": "# Part 6: DPO Theory Deep Dive and Alignment Practice",
    "# Part 7: DPO 微调代码与训练结果分析": "# Part 7: DPO Fine-Tuning Code and Training Result Analysis",
    "# Part 8: 大模型 DPO 分布式训练 (DeepSpeed & FSDP)": "# Part 8: Large Model DPO Distributed Training (DeepSpeed & FSDP)",
    # Repo B headings
    "# Part 1: 强化学习三种训练模式": "# Part 1: Three RL Training Modes",
    "# Part 2: DeepSeek R1 训练范式与技术对比": "# Part 2: DeepSeek R1 Training Paradigm and Technical Comparison",
    "# Part 3: PPO/RLHF 角色详解 —— \"Film Crew\" 类比": '# Part 3: PPO/RLHF Role Details — "Film Crew" Analogy',
    "# Part 4: GRPO 方法详解": "# Part 4: GRPO Method Deep Dive",
    "# Part 5: 奖励函数设计实战": "# Part 5: Reward Function Design in Practice",
    "# Part 6: DeepSeekMath-V2 自验证证明训练架构": "# Part 6: DeepSeekMath-V2 Self-Verifiable Proof Training Architecture",
    "# Part 7: SFT + GRPO 实操（代码与训练日志）": "# Part 7: SFT + GRPO Hands-On (Code and Training Logs)",
    "# Part 8: Phi-4 GRPO 训练代码": "# Part 8: Phi-4 GRPO Training Code",
    "# Part 9: GSPO — Dense 模型 vs MoE 模型的 RL 训练": "# Part 9: GSPO — RL Training for Dense vs MoE Models",
    "# Part 10: Test-time Compute Scaling — SLM 如何击败大模型": "# Part 10: Test-time Compute Scaling — How SLMs Beat Large Models",
    "# Part 11: Mind Evolution 与遗传算法": "# Part 11: Mind Evolution and Genetic Algorithms",
    "# Part 12: SLM 微调实验": "# Part 12: SLM Fine-Tuning Experiments",
    "# Part 13: 三种 RL 训练方法对比": "# Part 13: Comparison of Three RL Training Approaches",
}

# Sub-heading translations (## and below)
SUBHEADING_MAP = {
    "## 几种技术之间的关系": "## Relationships Between Techniques",
    "## 强化学习类与有监督微调类的区别": "## Differences Between RL and Supervised Fine-Tuning",
    "## **ReFT简介**": "## **Introduction to ReFT**",
    "## **TPO的流程**": "## **TPO Workflow**",
    "## **PPO和DPO的本质区别**": "## **Fundamental Differences Between PPO and DPO**",
    "## 几种技术对比": "## Fine-Tuning Techniques Comparison",
    "## LoRA/QLoRA 微调机制与 Adapter 合并策略": "## LoRA/QLoRA Fine-Tuning Mechanism and Adapter Merging Strategy",
    "### LoRA 的原理": "### LoRA Principles",
    "### 低秩矩阵表示的数学示例": "### Mathematical Example of Low-Rank Matrix Representation",
    "### Adapter 合并策略与量化对精度的影响": "### Adapter Merging Strategy and Quantization Impact on Precision",
    "## GaLore 全量微调实验": "## GaLore Full Fine-Tuning Experiments",
    "### GaLore 优化器选项": "### GaLore Optimizer Options",
    "### 实验记录": "### Experiment Records",
    "### GaLore 实验总结": "### GaLore Experiment Summary",
    "## DPO详解": "## DPO In-Depth",
    "### RLHF与DPO": "### RLHF and DPO",
    "## DPO微调代码": "## DPO Fine-Tuning Code",
    "## 对DPO训练结果的解释": "## DPO Training Results Explanation",
    "### 通过示例解释训练过程和指标": "### Training Process and Metrics Explained with Examples",
    "### 参考模型的作用": "### Role of the Reference Model",
    "### 训练结果中的各指标": "### Training Metrics Explanation",
    "### 总结": "### Summary",
    "## DPO微调中的正则化与泛化": "## Regularization and Generalization in DPO Fine-Tuning",
    "### 正则化": "### Regularization",
    "### 泛化": "### Generalization",
    "## **强化学习三种模式**": "## **Three RL Modes**",
    "## Test Time Scale模式": "## Test Time Scaling Modes",
    "## 技术对比": "## Technical Comparison",
    "## **DS R1的范式**": "## **DS R1 Paradigm**",
    "## 选择 SFT 还是 RL": "## Choosing SFT vs RL",
    "## 常见 RL 坑点": "## Common RL Pitfalls",
    "## TRL 中的 GRPO": "## GRPO in TRL",
    "## 用 TRL 训练 Qwen（SFT + GRPO）": "## Training Qwen with TRL (SFT + GRPO)",
    "### SFT 阶段": "### SFT Phase",
    "### GRPO 阶段": "### GRPO Phase",
    "#### 奖励函数": "#### Reward Functions",
    "## GRPO 方法详解": "## GRPO Method Deep Dive",
    "## 强化学习的一个范例 法律文书RL奖励函数设计精华与性能跃升解析": "## RL Case Study: Legal Document Reward Function Design and Performance Improvement",
    "### 训练阶段性能演进（可视化）": "### Training Performance Evolution (Visualization)",
    "## 嵌入式代码的奖励函数设计": "## Reward Function Design for Embedded Code",
    "### 本项目的奖励函数": "### Reward Functions in This Project",
    "## 📋 训练流程": "## 📋 Training Pipeline",
    "## 📊 训练效果": "## 📊 Training Results",
    "### 测试环境": "### Test Environment",
    "### 关键指标": "### Key Metrics",
    "### 推理验证": "### Inference Verification",
    "## ⚠️ 踩坑记录": "## ⚠️ Troubleshooting Records",
    "## 🎯 客户场景实操建议": "## 🎯 Customer Scenario Practical Suggestions",
    "### 嵌入式代码测试用例格式": "### Embedded Code Test Case Format",
    "## ⚠️ 常见问题": "## ⚠️ FAQ",
    "## 📚 参考资料": "## 📚 References",
    "## 📝 License": "## 📝 License",
    "## 📖 附录：SFT 调参最佳实践": "## 📖 Appendix: SFT Hyperparameter Tuning Best Practices",
    "### 常见问题诊断": "### Common Issues Diagnosis",
    "### 7 轮调参经验": "### 7-Round Tuning Experience",
    "### 关键参数设置": "### Key Parameter Settings",
    "### 数据增强技巧": "### Data Augmentation Tips",
    "### 核心教训": "### Key Lessons",
    "## Phi-4 GRPO 训练代码": "## Phi-4 GRPO Training Code",
    "## Gemma 3 270M 小模型能力上限探测": "## Gemma 3 270M Small Model Capability Exploration",
    "#### 结论": "#### Conclusion",
    "### Training Loss分析": "### Training Loss Analysis",
    "#### 现象": "#### Observations",
    "#### 含义": "#### Implications",
    "### 效果评估": "### Performance Evaluation",
    "#### 示例代码": "#### Example Code",
}

def translate_prose_line(line):
    """Translate a Chinese prose line to English. Returns translated line."""
    stripped = line.strip()
    
    # Skip empty, code, images, URLs
    if not stripped or not has_chinese(stripped):
        return line
    if stripped.startswith('```') or stripped.startswith('![') or stripped.startswith('[!['):
        return line
    if stripped.startswith('http') or stripped.startswith('{'):
        return line
    # Skip lines that are mostly code with Chinese comments
    if stripped.startswith('#!') or stripped.startswith('//') or stripped.startswith('/*'):
        return line
    
    # Check heading map
    for cn, en in HEADING_MAP.items():
        if stripped == cn.strip():
            return line.replace(stripped, en.strip()) 
    for cn, en in SUBHEADING_MAP.items():
        if stripped == cn.strip():
            return line.replace(stripped, en.strip())
    
    # For remaining Chinese lines, we'll keep them (they are prose that needs manual or API translation)
    # Mark them so we can count
    return line

def process_file(cn_path, en_path):
    with open(cn_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    translated = []
    in_code_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # Track code blocks
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            translated.append(line)
            continue
        
        if in_code_block:
            translated.append(line)
            continue
        
        translated.append(translate_prose_line(line))
    
    with open(en_path, 'w', encoding='utf-8') as f:
        f.writelines(translated)
    
    # Count remaining Chinese
    remaining = sum(1 for l in translated if has_chinese(l) and not l.strip().startswith('![') and 'mmbiz' not in l)
    total = len(translated)
    print(f"  {cn_path}: {total} lines, {remaining} still have Chinese")

BASE = "/mnt/g/github/david-share/Deep-Learning"
for repo in ["LLM-Fine-Tuning-and-Alignment", "LLM-RL-Training-and-Reasoning"]:
    cn = os.path.join(BASE, repo, "README-CN.md")
    en = os.path.join(BASE, repo, "README.md")
    process_file(cn, en)
