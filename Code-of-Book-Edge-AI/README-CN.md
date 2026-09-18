# 《边缘侧AI小模型训练、优化与部署》配套代码

[English](README.md) | 中文

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师  
> **出版社**: 机械工业出版社（2026）

本目录收录《边缘侧AI小模型训练、优化与部署》一书中出现的全部代码，以及书中引用的、位于本仓库其他目录下的完整项目快照，按章节组织，供读者随书下载使用。

## 目录结构

| 目录 | 章节 | 内容 |
|---|---|---|
| — | 第1章 AI on Edge：边缘侧人工智能的价值、能力与落地路径 | 无代码 |
| [`Chapter2-Dataset-Preparation/`](Chapter2-Dataset-Preparation/) | 第2章 边缘端高质量数据集的准备与增强 | 20 个代码/样例文件，2 个完整项目快照 |
| [`Chapter3-Training-and-Deployment/`](Chapter3-Training-and-Deployment/) | 第3章 边缘侧模型训练与部署 | 19 个代码/样例文件，4 个完整项目快照 |
| [`Chapter4-Fine-Tuning/`](Chapter4-Fine-Tuning/) | 第4章 边缘端模型的微调 | 15 个代码/样例文件，2 个完整项目快照 |
| [`Chapter5-Inference-and-Training-Optimization/`](Chapter5-Inference-and-Training-Optimization/) | 第5章 边缘端高效推理与性能优化 | 9 个代码/样例文件，1 个完整项目快照 |
| [`Chapter6-Multimodal-Assistant-CSharp/`](Chapter6-Multimodal-Assistant-CSharp/) | 第6章 AIPC边缘端多模态智能助手构建 | 9 个代码/样例文件 |
| [`Chapter7-Vision-Language-Models/`](Chapter7-Vision-Language-Models/) | 第7章 边缘端视觉语言模型与计算机视觉应用 | 9 个代码/样例文件，3 个完整项目快照 |

每章目录内：

- `N.N.N_*.py / .sh / .cs / .json / .yaml` —— 书中对应小节的代码，按印刷版整理为可直接解析的文件；分步展示的代码已合并，省略的 import 以“补充”标注。
- `samples/` —— 书中展示的数据样例、Prompt 模板与运行输出。
- `notes/` —— 书中以代码块排版的公式。
- `projects/` —— 书中引用的完整项目快照（脚本、Notebook、说明），原始位置见各章 README；图片链接指向原目录。
- `README-CN.md` / `README.md` —— 小节 → 文件对照表，以及与印刷版的差异说明。

## 书中引用的仓库地址

| 书中位置 | 书中链接 | 现行目录 |
|---|---|---|
| §3.1.2 | `Deep-Learning/SmolLM-Full-Fine-Tuning` | [`Deep-Learning/SmolLM-Full-Fine-Tuning`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/SmolLM-Full-Fine-Tuning)（副本：`Chapter3-Training-and-Deployment/projects/`） |
| §3.2.2 | `Deep-Learning/SLM-DeepSeek-R1` | [`Deep-Learning/LLM-RL-Training-and-Reasoning`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/LLM-RL-Training-and-Reasoning)（副本：`Chapter3-Training-and-Deployment/projects/`） |
| §3.6.3 | `davidwei-ai/AIPC-Agent-Training` | [`Deep-Learning/AIPC-Agent-Training`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/AIPC-Agent-Training)（副本：`Chapter3-Training-and-Deployment/projects/`） |

## 使用方法

```bash
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Code-of-Book-Edge-AI/Chapter3-Training-and-Deployment
pip install -r requirements.txt
python 3.2.2_sft_phi4_reasoning.py
```

书中实验均在 Azure GPU VM（NVIDIA A100 80GB / H100）上完成，第 6 章为 Windows AI PC 上的 C#/WPF 示例。运行前请按需修改模型、数据路径与显存相关参数。

## 许可证

MIT
