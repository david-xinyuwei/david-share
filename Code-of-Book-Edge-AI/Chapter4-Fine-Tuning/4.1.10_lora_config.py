# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.1.10 LoRA 超参数与实现方法

from peft import LoraConfig
peft_config = LoraConfig(
    r=16,                 # 秩
    lora_alpha=16,         # Alpha 参数
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=[
        'k_proj', 'q_proj', 'v_proj', 'o_proj',  # 自注意力相关投影矩阵
        'gate_proj', 'down_proj', 'up_proj'      # MLP相关矩阵
    ]
)
