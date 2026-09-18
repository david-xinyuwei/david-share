# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.2.7 EOS Token调整与模型输出格式优化

# 补充：导入语句与模型名
import pandas as pd
from transformers import AutoTokenizer
model_name = "microsoft/Phi-3.5-mini-instruct"

# 加载分词器
tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True,
    add_eos_token=True,
    use_fast=True
)
tokenizer.pad_token = tokenizer.unk_token
tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
tokenizer.padding_side = 'left'
# 定义系统提示
system_prompt = (
    "<|system|>\n"
    "You are an expert in .NET/.NET Framework and are familiar with the functions provided by NEBULA SDK. You know how to use NEBULA SDK to develop application systems on the CAMP platform.When providing the user with results, no explanation or thought process is needed. Ensure the code format is correct, indentation is standard, and it can compile successfully. Avoid repeating the same code output. "
)
# 如果您的分词器没有包含特殊标记，需要将其添加
special_tokens = {'additional_special_tokens': ['<|system|>', '<|user|>', '<|assistant|>','<|endoftext|>']}
tokenizer.add_special_tokens(special_tokens)
# 读取训练数据集
df = pd.read_csv("/home/david/Phi3.5_20241031_1question.csv")
# 移除包含缺失值的行
df = df.dropna(subset=['Question', 'Answer'])
# 确保所有数据都是字符串类型
df['Question'] = df['Question'].astype(str)
df['Answer'] = df['Answer'].astype(str)
# 定义函数：格式化数据集，包含系统提示
def format_dataset(row):
    # 返回字符串而不是字典
    return f"{system_prompt}<|user|>\n{row['Question']}\n<|assistant|>\n{row['Answer']}{tokenizer.eos_token}\n"
