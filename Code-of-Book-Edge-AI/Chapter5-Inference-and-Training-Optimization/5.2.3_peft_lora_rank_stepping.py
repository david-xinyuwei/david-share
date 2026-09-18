# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第5章 §5.2.3 节约训练开销的工程化选择

# pip install peft

# 1. 优先进行 PEFT 类型微调（LoRA/QLoRA 为起点）
# 导入PEFT所需模块
from peft import LoraConfig, get_peft_model, TaskType
# 定义LoRA参数
peft_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM, # 例如选CAUSAL_LM（自回归语言模型任务）
    inference_mode=False,                 # 训练模式
    r=8,                                  # 初始LoRA rank值(推荐从较小值8开始)
    lora_alpha=32,                        # LoRA 缩放因子
    target_modules=["q_proj", "v_proj"]    # 根据模型结构决定适配模块
)
# 与基础模型结合，生成PEFT模型
peft_model = get_peft_model(model, peft_config)

# 2. 对 rank 逐步提升（8 → 16）
# 调整rank参数
peft_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    inference_mode=False,
    r=16,         # rank逐步增加为16
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"]
)
# 重新实例化PEFT模型(LoRA规模变大后显存占用会增加)
peft_model = get_peft_model(model, peft_config)
