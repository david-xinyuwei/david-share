# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第7章 §7.1.2 微调实战：Burberry商品识别

# 补充：导入语句
import torch
import torch.optim as optim
import wandb
from transformers import AutoModelForCausalLM

# 训练核心配置
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/Phi-3.5-vision-instruct",
    device_map="cuda",
    torch_dtype=torch.float16,
    attn_implementation="flash_attention_2"
)
optimizer = optim.AdamW(model.parameters(), lr=5e-5)
gradient_accumulation_steps = 64
eval_steps = 150
# 使用Weights & Biases监控
wandb.init(project="davidwei-phi35-v")
