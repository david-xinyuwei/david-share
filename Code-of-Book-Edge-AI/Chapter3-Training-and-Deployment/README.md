# Chapter 3: Training and Deploying Models on the Edge

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇)

## Code listings from the book

| Section | File | Description |
|---|---|---|
| 3.1.2 | [`3.1.2_pretraining_vs_finetuning.py`](3.1.2_pretraining_vs_finetuning.py) | 预训练（随机初始化）与微调（加载预训练权重）的关键差异 |
| 3.2.2 | [`3.2.2_sft_phi4_reasoning.py`](3.2.2_sft_phi4_reasoning.py) | 用 dolphin-r1 数据集 + LoRA 对 Phi-4 做 SFT 推理能力训练 |
| 3.2.2 | [`3.2.2_grpo_phi4_reasoning.py`](3.2.2_grpo_phi4_reasoning.py) | Unsloth + TRL GRPOTrainer，用三个格式奖励函数训练 Phi-4 |
| 3.2.2 | [`samples/3.2.2_grpo_target_format.txt`](samples/3.2.2_grpo_target_format.txt) | GRPO 训练要求模型遵循的输出结构 |
| 3.2.2 | [`samples/3.2.2_grpo_test_prompt.txt`](samples/3.2.2_grpo_test_prompt.txt) | 训练后测试泛化推理的提问 |
| 3.2.2 | [`samples/3.2.2_grpo_expected_output.txt`](samples/3.2.2_grpo_expected_output.txt) | GRPO 训练后 Phi-4 的实际输出 |
| 3.3.3 | [`3.3.3_lora_config.py`](3.3.3_lora_config.py) | LoRA 目标模块配置 |
| 3.3.3 | [`3.3.3_qlora_config.py`](3.3.3_qlora_config.py) | QLoRA：bitsandbytes 4-bit 量化 + LoRA 配置 |
| 3.3.4 | [`3.3.4_merge_lora_adapter.py`](3.3.4_merge_lora_adapter.py) | 把 LoRA 适配器合并回基础模型并保存 |
| 3.4.2 | [`3.4.2_multi_lora_vllm_offline.py`](3.4.2_multi_lora_vllm_offline.py) | vLLM 离线推理中按请求切换多个 LoRA 适配器 |
| 3.4.2 | [`3.4.2_vllm_serve_multi_lora.sh`](3.4.2_vllm_serve_multi_lora.sh) | vLLM 服务同时挂载多个 LoRA 适配器 |
| 3.4.2 | [`3.4.2_multi_lora_openai_client.py`](3.4.2_multi_lora_openai_client.py) | 用 OpenAI 兼容接口请求不同适配器 |
| 3.6.3 | [`samples/3.6.3_sft_data_sample.jsonl`](samples/3.6.3_sft_data_sample.jsonl) | 训练飞轮 SFT 阶段数据格式示例 |
| 3.6.3 | [`3.6.3_flywheel_sft_train.py`](3.6.3_flywheel_sft_train.py) | AI PC 领域 SFT 训练核心配置 |
| 3.6.3 | [`samples/3.6.3_sft_training_log.txt`](samples/3.6.3_sft_training_log.txt) | SFT 训练日志（实际输出） |
| 3.6.3 | [`3.6.3_flywheel_grpo_reward_function.py`](3.6.3_flywheel_grpo_reward_function.py) | AI PC Expert 奖励函数（关键词/长度/结构/无幻觉） |
| 3.6.3 | [`samples/3.6.3_dpo_data_sample.json`](samples/3.6.3_dpo_data_sample.json) | DPO 偏好数据格式示例（V1.2 风格优化） |
| 3.6.3 | [`3.6.3_flywheel_ast_code_validator.py`](3.6.3_flywheel_ast_code_validator.py) | 用 AST 校验代码块语法，自动划分 chosen / rejected |
| 3.6.3 | [`3.6.3_flywheel_dpo_train.py`](3.6.3_flywheel_dpo_train.py) | DPO 训练配置（极小学习率防止灾难性遗忘） |

## Full project snapshots (projects/)

Snapshots of the david-share projects that the chapter cites or that the listings were taken from, including full scripts, notebooks and write-ups; images link back to the original folders.

| Folder | Section | Content | Original location |
|---|---|---|---|
| [`projects/SmolLM-Full-Fine-Tuning/`](projects/SmolLM-Full-Fine-Tuning/) | §3.1.2 | 书中引用：本小节完整代码 | [`Deep-Learning/SmolLM-Full-Fine-Tuning`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/SmolLM-Full-Fine-Tuning) |
| [`projects/LLM-RL-Training-and-Reasoning/`](projects/LLM-RL-Training-and-Reasoning/) | §3.2.2 | SFT + GRPO 训练 Phi-4 推理能力的完整代码与训练日志（书中 SLM-DeepSeek-R1 链接的现行目录） | [`Deep-Learning/LLM-RL-Training-and-Reasoning`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/LLM-RL-Training-and-Reasoning) |
| [`projects/Multi-LoRA-adapter/`](projects/Multi-LoRA-adapter/) | §3.4 | vLLM 多 LoRA 适配器完整示例 | [`Deep-Learning/Multi-LoRA-adapter`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Multi-LoRA-adapter) |
| [`projects/AIPC-Agent-Training/`](projects/AIPC-Agent-Training/) | §3.6 | 训练飞轮 SFT → GRPO → DPO 全部脚本与数据样例（书中引用） | [`Deep-Learning/AIPC-Agent-Training`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/AIPC-Agent-Training) |

## Environment

```bash
pip install -r requirements.txt
```

The experiments in the book were run on Azure GPU VMs (A100 / H100); adjust model paths, data paths and memory-related settings as needed.

## Differences from the printed text

- §3.3.3 `3.3.3_qlora_config.py`: the printed block stops after `target_modules`; the closing parenthesis and `get_peft_model` call are added (marked 补充).
- §3.3.4 `3.3.4_merge_lora_adapter.py`: `dvice_map` / `torch.bfloat10` are typos in print; fixed to `device_map` / `torch.bfloat16`.
- §3.2.2: the SFT and GRPO listings are shown step by step in the book; here each is merged into one runnable script with the omitted imports added.

## License

MIT
