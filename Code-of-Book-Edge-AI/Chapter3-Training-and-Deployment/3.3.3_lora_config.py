# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.3.3 全微调、LoRA 和 QLoRA 代码示例

from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM
model_name = "model_name"
model = AutoModelForCausalLM.from_pretrained(model_name)
# LoRA配置
lora_config = LoraConfig(
    r=128,                          # LoRA低秩参数的秩
    lora_alpha=32,    # LoRA的缩放参数
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",    # 自注意力（Attention）模块
        "gate_proj", "up_proj", "down_proj",       # 前馈（FFN）模块
        # 如果是普通微调任务，一般无须加 embed_tokens 和 lm_head
        # "embed_tokens", "lm_head"
    ],
    lora_dropout=0.0,
    bias="none",
)
model = get_peft_model(model, lora_config)
model.train()
