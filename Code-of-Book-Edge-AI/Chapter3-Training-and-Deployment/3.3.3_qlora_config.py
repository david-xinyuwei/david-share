# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.3.3 全微调、LoRA 和 QLoRA 代码示例

# 补充：导入语句
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

# 使用bitsandbytes（bnb）进行4-bit量化配置
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,              # 以4-bit精度量化加载模型
    bnb_4bit_use_double_quant=True, # 使用双量化节约显存
    bnb_4bit_quant_type="nf4",      # 使用nf4量化类型（推荐）
    bnb_4bit_compute_dtype=torch.bfloat16 # 使用bf16计算提高性能
)
# 配置QLoRA微调（指定模块）
lora_config = LoraConfig(
    r=128,
    lora_alpha=32,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
        # 如果领域差距较大或继续领域特定预训练，则启用以下两项
        # "embed_tokens", "lm_head"
    ],
    lora_dropout=0.0,
    bias="none",
)
# 补充：书中省略的闭合与装配语句
model = AutoModelForCausalLM.from_pretrained("model_name", quantization_config=bnb_config)
model = get_peft_model(model, lora_config)
