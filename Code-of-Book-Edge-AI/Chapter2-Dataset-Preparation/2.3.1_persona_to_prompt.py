# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第2章 §2.3.1 基于Persona生成合成样本提示

import sys
from tqdm import tqdm
from datasets import load_dataset
# 加载数据集并按"Education"标签过滤
dataset = load_dataset("argilla/FinePersonas-v0.1", split="train", streaming=True)
dataset = dataset.filter(lambda example: "Education" in example["labels"])
questions = []
counter = 0
max_personas = 5000
# 为每条persona创建对应的prompt
for d in tqdm(dataset):
    questions.append({
        "role": "user",
        "content": f"Generate a question that this persona can answer with expertise:\n\n{d['persona']}"
    })
    counter += 1
    if counter >= max_personas:
        break
print(len(questions))
