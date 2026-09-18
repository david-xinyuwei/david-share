# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.2.2 训练范式代码展现 —— 2. GRPO训练Phi-4的Reasoning能力

from unsloth import FastLanguageModel, PatchFastRL
import re
PatchFastRL("GRPO", FastLanguageModel)
max_seq_length = 1024
lora_rank = 16
# 加载 Phi-4 模型并启用 4-bit 量化和 LoRA 微调
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "microsoft/phi-4",
    max_seq_length = max_seq_length,
    load_in_4bit = True,
    fast_inference = True,
    max_lora_rank = lora_rank,
    gpu_memory_utilization = 0.6,
)
model = FastLanguageModel.get_peft_model(
    model,
    r = lora_rank,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha = lora_rank,
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

# 三个奖励函数：分别检查宽松格式、严格格式和 aha 出现次数
def very_loose_format_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion has a specific format."""
    responses = [completion[0]["content"] for completion in completions]
    return [0.5 if "<reasoning>" in r and "</reasoning>" in r else 0.0 for r in responses]
def strict_format_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion has a specific format."""
    pattern = r"^<reasoning>.*?</reasoning>\s*<answer>.*?</answer>\s*<aha>.*?</aha>$"
    responses = [completion[0]["content"] for completion in completions]
    matches = [re.match(pattern, r, re.DOTALL) for r in responses]
    return [0.5 if match else 0.0 for match in matches]
def aha_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion contains "aha" times, 2 for the tags, and one more, wherever it wants."""
    responses = [completion[0]["content"] for completion in completions]
    matches = [re.findall(r'\baha\b', r, re.IGNORECASE) for r in responses]
    return [0.5 if len(match) == 3 else 0.0 for match in matches]

from datasets import load_dataset
import multiprocessing
ds = load_dataset("cognitivecomputations/dolphin-r1", "reasoning-deepseek", split="train[:10000]")
ds = ds.rename_columns({'messages':'prompt'})

from trl import GRPOConfig, GRPOTrainer
training_args = GRPOConfig(
    use_vllm = True,                       # 使用 vLLM 快速推理
    learning_rate = 1e-6,
    warmup_ratio = 0.1,
    optim = "paged_adamw_8bit",
    bf16 = True,
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 4,
    num_generations = 6,                   # 每个输入生成多个输出进行评估
    max_prompt_length = 256,
    max_completion_length = 512,
    max_steps = 250,
    logging_steps = 5,
    output_dir = "outputs",
)
reward_funcs = [very_loose_format_reward_func, strict_format_reward_func, aha_reward_func]
trainer = GRPOTrainer(
    model = model,
    processing_class = tokenizer,
    reward_funcs = reward_funcs,
    args = training_args,
    train_dataset = ds,
)
trainer.train()
