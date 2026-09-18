# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第2章 §2.3.3 批量生成回答
# 依赖 2.3.2 生成的 llm 与 question_prompts；书中此处误印为 prompt_messages 且缺逗号，已按上下文修正

from vllm import SamplingParams
sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=1024)
outputs = llm.chat(messages=question_prompts,
                  sampling_params=sampling_params,
                  use_tqdm=True)
generated_dataset = []
deduper = set()
for output in outputs:
    example = {}
    # 从prompt中提取原始的指令(prompt文本)
    example['prompt'] = output.prompt.split("<|im_start|>user\n")[1].split("<|im_end|>\n")[0]
    # 从prompt中分别提取出问题(question)和人设(persona)
    segments = output.prompt.split("\n\nAnswer the following question:\n")
    example['question'] = segments[-1].split("<|im_end|>\n")[0]
    example['persona'] = segments[0].split("You are this persona: ")[-1]
    # 提取模型生成的答案(answer)
    example['answer'] = output.outputs[0].text
    # 进行去重处理，若重复则跳过当前内容
    unique_key = example['question'] + example['answer']
    if unique_key in deduper:
        continue  # 发现重复，跳过
    deduper.add(unique_key)
    # 生成对话消息格式(messages)，方便后续微调工具使用
    example['messages'] = [
        {'content': example['question'], 'role': 'user'},
        {'content': example['answer'], 'role': 'assistant'}
    ]
    generated_dataset.append(example)
