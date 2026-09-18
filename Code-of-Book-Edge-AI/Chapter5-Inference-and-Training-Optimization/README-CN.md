# 第5章 边缘端高效推理与性能优化

[English](README.md) | 中文

> **作者**: 魏新宇 (Xinyu Wei)

## 书中代码清单

| 章节 | 文件 | 说明 |
|---|---|---|
| 5.1/5.3 | [`notes/5_memory_estimation_formulas.txt`](notes/5_memory_estimation_formulas.txt) | 训练激活值与推理显存的估算公式 |
| 5.2.3 | [`5.2.3_peft_lora_rank_stepping.py`](5.2.3_peft_lora_rank_stepping.py) | PEFT 起步与 rank 逐步提升 |
| 5.2.3 | [`5.2.3_activation_checkpointing.py`](5.2.3_activation_checkpointing.py) | 开启 Activation Checkpointing |
| 5.2.3 | [`5.2.3_deepspeed_zero3_offload.json`](5.2.3_deepspeed_zero3_offload.json) | DeepSpeed ZeRO Stage 3 + CPU offload 配置 |
| 5.2.4 | [`5.2.4_distributed_dpo/deepspeed_config.json`](5.2.4_distributed_dpo/deepspeed_config.json) | DeepSpeed ZeRO-3 训练配置（deepspeed_config.json） |
| 5.2.4 | [`5.2.4_distributed_dpo/deepspeed_dpo.py`](5.2.4_distributed_dpo/deepspeed_dpo.py) | Qwen2.5-72B + QLoRA + DeepSpeed ZeRO-3 的 DPO 训练脚本 |
| 5.2.4 | [`5.2.4_distributed_dpo/config_fsdp.yaml`](5.2.4_distributed_dpo/config_fsdp.yaml) | Accelerate FSDP 配置（config_fsdp.yaml） |
| 5.2.4 | [`5.2.4_distributed_dpo/fsdp_qlora_dpo.py`](5.2.4_distributed_dpo/fsdp_qlora_dpo.py) | Qwen2.5-72B + QLoRA + FSDP 的 DPO 训练脚本 |
| 5.2.4 | [`5.2.4_distributed_dpo/run.sh`](5.2.4_distributed_dpo/run.sh) | 两种分布式训练的启动命令 |

## 完整项目副本（projects/）

以下目录是书中引用或本章代码所出自的 david-share 项目的快照，含完整脚本、Notebook 与说明；图片链接指向原目录。

| 目录 | 对应章节 | 内容 | 原始位置 |
|---|---|---|---|
| [`projects/LLM-Fine-Tuning-and-Alignment/`](projects/LLM-Fine-Tuning-and-Alignment/) | §5.2.4 | DeepSpeed ZeRO 与 FSDP 分布式 DPO 训练的完整说明 | [`Deep-Learning/LLM-Fine-Tuning-and-Alignment`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment) |

## 环境

```bash
pip install -r requirements.txt
```

书中实验在 Azure GPU VM（A100 / H100）上完成；各脚本按需修改模型路径、数据路径与显存相关参数。

## 与印刷版的差异说明

- §5.2.4 `config_fsdp.yaml`：书中 `num_processes:2` 缺少冒号后的空格（非法 YAML），已修正为 `num_processes: 2`。
- §5.2.4：书中文件名 `deepspeed.py` 会与 `deepspeed` 包同名导致导入冲突，此处改名为 `deepspeed_dpo.py`；`fsdp+QLoRA.py` 改名为 `fsdp_qlora_dpo.py`，`run.sh` 中给出对应命令。

## 许可证

MIT
