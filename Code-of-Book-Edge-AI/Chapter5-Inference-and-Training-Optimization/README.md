# Chapter 5: Efficient Inference and Performance Optimization on the Edge

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇)

## Code listings from the book

| Section | File | Description |
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

## Full project snapshots (projects/)

Snapshots of the david-share projects that the chapter cites or that the listings were taken from, including full scripts, notebooks and write-ups; images link back to the original folders.

| Folder | Section | Content | Original location |
|---|---|---|---|
| [`projects/LLM-Fine-Tuning-and-Alignment/`](projects/LLM-Fine-Tuning-and-Alignment/) | §5.2.4 | DeepSpeed ZeRO 与 FSDP 分布式 DPO 训练的完整说明 | [`Deep-Learning/LLM-Fine-Tuning-and-Alignment`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment) |

## Environment

```bash
pip install -r requirements.txt
```

The experiments in the book were run on Azure GPU VMs (A100 / H100); adjust model paths, data paths and memory-related settings as needed.

## Differences from the printed text

- §5.2.4 `config_fsdp.yaml`: the printed `num_processes:2` lacks a space (invalid YAML); fixed to `num_processes: 2`.
- §5.2.4: `deepspeed.py` would shadow the `deepspeed` package, so it is renamed `deepspeed_dpo.py`; `fsdp+QLoRA.py` becomes `fsdp_qlora_dpo.py` (see `run.sh`).

## License

MIT
