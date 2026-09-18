# Chapter 4: Fine-Tuning Models for the Edge

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇)

## Code listings from the book

| Section | File | Description |
|---|---|---|
| 4.1 | [`notes/4.1_training_time_and_batch_size_formulas.txt`](notes/4.1_training_time_and_batch_size_formulas.txt) | 训练时间与全局批大小的估算公式 |
| 4.1.2 | [`4.1.2_training_arguments_full_example.py`](4.1.2_training_arguments_full_example.py) | 一个完整的 TrainingArguments 配置示例 |
| 4.1.3–4.1.9 | [`4.1_training_arguments_snippets.py`](4.1_training_arguments_snippets.py) | 批大小、学习率调度、优化器、BF16、评估/保存步骤的参数片段 |
| 4.1.10 | [`4.1.10_lora_config.py`](4.1.10_lora_config.py) | LoRA 的 r / alpha / target_modules 设置 |
| 4.2.2 | [`samples/4.2.2_first_attempt_data_sample.txt`](samples/4.2.2_first_attempt_data_sample.txt) | 首次微调时的小规模数据样例（含模型错误输出） |
| 4.2.4 | [`samples/4.2.4_cot_english_data_sample.txt`](samples/4.2.4_cot_english_data_sample.txt) | 引入链式推理后的英文训练样例 |
| 4.2.5 | [`samples/4.2.5_random_swapping_augmentation_sample.txt`](samples/4.2.5_random_swapping_augmentation_sample.txt) | 随机交换代码行的数据增强样例 |
| 4.2.7 | [`samples/4.2.7_special_tokens_map_eos_fragment.txt`](samples/4.2.7_special_tokens_map_eos_fragment.txt) | Phi-3.5 special_tokens_map.json 中 eos_token 定义片段 |
| 4.2.7 | [`4.2.7_phi35_dataset_formatting.py`](4.2.7_phi35_dataset_formatting.py) | Phi-3.5 分词器特殊标记、系统提示与训练样本格式化 |
| 4.3.3 | [`4.3.3_florence2_download_dataset.py`](4.3.3_florence2_download_dataset.py) | 下载 Roboflow 目标检测数据集（florence2-od 格式） |
| 4.3.3 | [`samples/4.3.3_florence2_annotations_sample.jsonl`](samples/4.3.3_florence2_annotations_sample.jsonl) | annotations.jsonl 标注格式样例 |
| 4.3.3 | [`4.3.3_florence2_lora_train.py`](4.3.3_florence2_lora_train.py) | Florence-2 LoRA 微调训练循环、启动与保存 |
| 4.3.3 | [`samples/4.3.3_florence2_adapter_files.txt`](samples/4.3.3_florence2_adapter_files.txt) | 训练产出的 adapter 目录内容 |
| 4.3.3 | [`4.3.3_florence2_lora_inference.py`](4.3.3_florence2_lora_inference.py) | 加载基础模型 + LoRA adapter 做目标检测推理并可视化 |
| 4.3.3 | [`samples/4.3.3_florence2_inference_output.txt`](samples/4.3.3_florence2_inference_output.txt) | 推理输出示例 |

## Full project snapshots (projects/)

Snapshots of the david-share projects that the chapter cites or that the listings were taken from, including full scripts, notebooks and write-ups; images link back to the original folders.

| Folder | Section | Content | Original location |
|---|---|---|---|
| [`projects/Phi-Model-Family/`](projects/Phi-Model-Family/) | §4.2 | Phi-3.5 代码生成微调实践（数据集 Phi3.5_20241031） | [`Deep-Learning/Phi-Model-Family`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Phi-Model-Family) |
| [`projects/Florence-2/`](projects/Florence-2/) | §4.3 | Florence-2 LoRA / 全参数微调 Notebook | [`Multimodal-Models/Florence-2`](https://github.com/david-xinyuwei/david-share/tree/master/Multimodal-Models/Florence-2) |

## Environment

```bash
pip install -r requirements.txt
```

The experiments in the book were run on Azure GPU VMs (A100 / H100); adjust model paths, data paths and memory-related settings as needed.

## Differences from the printed text

- §4.1.3–4.1.9: `...` placeholders were turned into comments so the snippets parse.
- §4.3.3: imports and the `DEVICE` definition that exist in the notebook but were omitted in print are added; see `projects/Florence-2/` for the full notebook.

## License

MIT
