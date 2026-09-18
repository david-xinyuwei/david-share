# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第2章 §2.2.4 样本边界标记（EOS）的设置方法

# 方法一：初始化分词器时指定 add_eos_token=True
from transformers import AutoTokenizer
# 设置模型名称
model_name = "microsoft/Phi-3.5-Mini-instruct"
# 加载分词器
tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True,
    add_eos_token=True,
    use_fast=True
)

# 方法二：手动在文本末尾加入 EOS 标记（system_prompt 与 row 由调用方提供）
def format_dataset(row):
    # 返回字符串而不是字典
    return f"{system_prompt}<|user|>\n{row['Question']}\n<|assistant|>\n{row['Answer']}{tokenizer.eos_token}\n"
