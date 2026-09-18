# Chapter 2: Preparing and Augmenting High-Quality Datasets for the Edge

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇)

## Code listings from the book

| Section | File | Description |
|---|---|---|
| 2.2.1 | [`samples/2.2.1_instruction_sample_format.txt`](samples/2.2.1_instruction_sample_format.txt) | 指令/输入/回答 三段式样本模板 |
| 2.2.2 | [`samples/2.2.2_audio_asr_sample.jsonl`](samples/2.2.2_audio_asr_sample.jsonl) | 语音识别样本记录格式 |
| 2.2.3 | [`samples/2.2.3_prompt_completion_sample.json`](samples/2.2.3_prompt_completion_sample.json) | prompt-completion 格式样本 |
| 2.2.3 | [`samples/2.2.3_llama3_chat_template_sample.txt`](samples/2.2.3_llama3_chat_template_sample.txt) | Llama 3 Instruct 聊天模板样本 |
| 2.2.3 | [`samples/2.2.3_custom_multirole_template_sample.txt`](samples/2.2.3_custom_multirole_template_sample.txt) | 自定义多角色对话模板样本 |
| 2.2.4 | [`samples/2.2.4_without_eos_sample.txt`](samples/2.2.4_without_eos_sample.txt) | 缺少 EOS 标记时的失控输出示例 |
| 2.2.4 | [`samples/2.2.4_with_eos_sample.txt`](samples/2.2.4_with_eos_sample.txt) | 加入 EOS 标记后的输出示例 |
| 2.2.4 | [`2.2.4_eos_token_setup.py`](2.2.4_eos_token_setup.py) | 两种为样本添加 EOS 标记的方法 |
| 2.3.1 | [`2.3.1_persona_to_prompt.py`](2.3.1_persona_to_prompt.py) | 从 FinePersonas 选取 5000 个教育类 Persona 并生成提问 Prompt |
| 2.3.1 | [`samples/2.3.1_prompt_template.txt`](samples/2.3.1_prompt_template.txt) | Persona → Prompt 模板 |
| 2.3.2 | [`2.3.2_generate_questions_vllm.py`](2.3.2_generate_questions_vllm.py) | 用 vLLM + Qwen2.5-7B-Instruct 为每个 Persona 生成 5 个问题 |
| 2.3.3 | [`samples/2.3.3_answer_prompt_sample.txt`](samples/2.3.3_answer_prompt_sample.txt) | 回答生成阶段的 Prompt 样例 |
| 2.3.3 | [`samples/2.3.3_messages_format_sample.json`](samples/2.3.3_messages_format_sample.json) | messages 字段（对话消息格式）样例 |
| 2.3.3 | [`2.3.3_generate_answers_vllm.py`](2.3.3_generate_answers_vllm.py) | 批量生成回答、去重并组装 messages 字段 |
| 2.3.4 | [`2.3.4_export_dataset.py`](2.3.4_export_dataset.py) | 保存 JSON、拆分训练/测试集并推送到 Hugging Face Hub |
| 2.4 | [`samples/2.4_preference_dataset_schema.txt`](samples/2.4_preference_dataset_schema.txt) | 偏好数据集结构（preferred / non_preferred） |
| 2.5.2 | [`2.5.2_generate_paired_answers.py`](2.5.2_generate_paired_answers.py) | 同一 Prompt 用不同 top_p 生成成对回答 |
| 2.5.2 | [`samples/2.5.2_judge_prompt_sample_zh.txt`](samples/2.5.2_judge_prompt_sample_zh.txt) | 让模型判断 A/B 回答优劣的中文提示样例 |
| 2.5.2 | [`samples/2.5.2_preference_record_sample.json`](samples/2.5.2_preference_record_sample.json) | 判定后形成的偏好训练语料样例 |
| 2.5.2 | [`samples/2.5.2_judge_prompt_leaderboard_en.txt`](samples/2.5.2_judge_prompt_leaderboard_en.txt) | 更严谨的英文评审提示词模板 |

## Full project snapshots (projects/)

Snapshots of the david-share projects that the chapter cites or that the listings were taken from, including full scripts, notebooks and write-ups; images link back to the original folders.

| Folder | Section | Content | Original location |
|---|---|---|---|
| [`projects/4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice/`](projects/4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice/) | §2.3 | Persona 合成指令数据集的完整流程 | [`Deep-Learning/4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice) |
| [`projects/LLM-Judgment/`](projects/LLM-Judgment/) | §2.5 | 用 LLM 评审成对回答、构造偏好数据 | [`Agents/LLM-Judgment`](https://github.com/david-xinyuwei/david-share/tree/master/Agents/LLM-Judgment) |

## Environment

```bash
pip install -r requirements.txt
```

The experiments in the book were run on Azure GPU VMs (A100 / H100); adjust model paths, data paths and memory-related settings as needed.

## Differences from the printed text

- §2.3.3 `2.3.3_generate_answers_vllm.py`: the printed `llm.chat(messages=prompt_messages` misses a comma and the variable should be `question_prompts` from §2.3.2; fixed.

## License

MIT
