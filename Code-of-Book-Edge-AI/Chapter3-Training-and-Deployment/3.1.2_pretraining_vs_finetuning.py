# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.1.2 预训练与微调区别核心代码示例

# （1）预训练阶段关键代码
from transformers import GPT2Config, GPT2LMHeadModel, GPT2Tokenizer
from datasets import load_dataset
# 模型随机初始化，未加载任何预训练参数
config = GPT2Config()
model = GPT2LMHeadModel(config)
# 使用预训练分词器，保证两个阶段分词规则一致
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
# 加载大规模无标注数据，用于预训练语言建模
dataset = load_dataset("wikitext", "wikitext-2-raw-v1")

# （2）微调阶段关键代码
from transformers import AutoModelForCausalLM
model_name="gpt2"
# 加载预训练模型权重，进一步微调
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    attn_implementation="flash_attention_2",
    device_map={"": 0}
)
# 开启梯度检查点节省显存，利于微调大规模模型
model.gradient_checkpointing_enable(
    gradient_checkpointing_kwargs={'use_reentrant': True}
)
