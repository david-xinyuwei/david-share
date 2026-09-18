# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第2章 §2.3.4 导出数据集

import json
from datasets import load_dataset, DatasetDict
# 将生成的数据集保存到JSON文件
with open('qa_dataset.json', 'w') as fp:
    json.dump(generated_dataset, fp)
# 从JSON文件加载数据并进行训练/测试拆分
data_files = {"train": "qa_dataset.json"}
qa_dataset = load_dataset("json", data_files=data_files, split="train").train_test_split(test_size=0.05)
# 构建DatasetDict对象，包含训练和测试数据
train_test = DatasetDict({
    'train': qa_dataset['train'],
    'test': qa_dataset['test']
})
# 将数据集推送到Hugging Face Hub的私有仓库(请自行替换仓库名称)
train_test.push_to_hub("my_repo", private=True)
