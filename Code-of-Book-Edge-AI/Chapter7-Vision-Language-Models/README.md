# Chapter 7: Vision-Language Models and Computer Vision on the Edge

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇)

## Code listings from the book

| Section | File | Description |
|---|---|---|
| 7.1.1 | [`7.1.1_passport_ocr_prompt.txt`](7.1.1_passport_ocr_prompt.txt) | 护照 OCR 的 JSON 提取 Prompt |
| 7.1.1 | [`7.1.1_passport_ground_truth.json`](7.1.1_passport_ground_truth.json) | 护照样本 Ground Truth |
| 7.1.2 | [`7.1.2_burberry_download_dataset.py`](7.1.2_burberry_download_dataset.py) | 下载 Burberry 商品图片并生成 CSV |
| 7.1.2 | [`samples/7.1.2_phi3_vision_training_sample_format.txt`](samples/7.1.2_phi3_vision_training_sample_format.txt) | Phi-3-Vision 训练语料格式 |
| 7.1.2 | [`7.1.2_phi35_vision_train_config.py`](7.1.2_phi35_vision_train_config.py) | Phi-3.5-vision 微调核心配置 |
| 7.3.3 | [`samples/7.3.3_biomedparse_2d_data_layout.txt`](samples/7.3.3_biomedparse_2d_data_layout.txt) | “文件名即提示词”的 2D 数据目录结构 |
| 7.3.3 | [`7.3.3_biomedparse_2d_key_snippets.py`](7.3.3_biomedparse_2d_key_snippets.py) | 2D 微调的三个关键细节（0–255 输入、提示词提取、Dice Loss） |
| 7.3.4 | [`7.3.4_prepare_3d_data.py`](7.3.4_prepare_3d_data.py) | NIfTI → NPZ 数据转换 |
| 7.3.4 | [`7.3.4_finetune_3d_core.py`](7.3.4_finetune_3d_core.py) | 3D 微调主流程（逐切片训练） |

## Full project snapshots (projects/)

Snapshots of the david-share projects that the chapter cites or that the listings were taken from, including full scripts, notebooks and write-ups; images link back to the original folders.

| Folder | Section | Content | Original location |
|---|---|---|---|
| [`projects/Phi3-vision-Inference-on-Edge/`](projects/Phi3-vision-Inference-on-Edge/) | §7.1.1 | 护照 OCR 多 VLM 推理对比脚本 | [`Multimodal-Models/Phi3-vision-Inference-on-Edge`](https://github.com/david-xinyuwei/david-share/tree/master/Multimodal-Models/Phi3-vision-Inference-on-Edge) |
| [`projects/Phi3-vision-Fine-tuning/`](projects/Phi3-vision-Fine-tuning/) | §7.1.2 | Phi-3-Vision Burberry 商品识别微调 | [`Multimodal-Models/Phi3-vision-Fine-tuning`](https://github.com/david-xinyuwei/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning) |
| [`projects/BiomedParse-Fine-Tuning/`](projects/BiomedParse-Fine-Tuning/) | §7.3 | BiomedParse 2D/3D 微调与可视化脚本 | [`Multimodal-Models/BiomedParse-Fine-Tuning`](https://github.com/david-xinyuwei/david-share/tree/master/Multimodal-Models/BiomedParse-Fine-Tuning) |

## Environment

```bash
pip install -r requirements.txt
```

The experiments in the book were run on Azure GPU VMs (A100 / H100); adjust model paths, data paths and memory-related settings as needed.

## Differences from the printed text

- §7.1.2 `7.1.2_burberry_download_dataset.py`: `import pandas as pd` and output-directory creation added.

## License

MIT
