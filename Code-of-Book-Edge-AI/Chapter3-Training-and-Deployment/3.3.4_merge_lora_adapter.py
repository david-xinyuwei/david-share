# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.3.4 Adapter合并的选择
# 书中印刷版此处为 dvice_map / bfloat10，属笔误，已修正

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM
# 加载基础模型
base_model = AutoModelForCausalLM.from_pretrained(
    "base_model_path",
    device_map="auto",
    torch_dtype=torch.bfloat16,
)
# 加载LoRA适配器
model = PeftModel.from_pretrained(base_model, "lora_adapter_path")
# 合并适配器到基础模型
merged_model = model.merge_and_unload()
# 保存合并后的模型
merged_model.save_pretrained("merged_model_path")
