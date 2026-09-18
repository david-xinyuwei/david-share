# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第5章 §5.2.4 DeepSpeed 训练代码
# 书中文件名为 deepspeed.py；为避免与 deepspeed 包同名冲突，此处改为 deepspeed_dpo.py

import torch
import os
import multiprocessing
from datasets import load_dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed
)
from trl import DPOTrainer, DPOConfig
set_seed(1234)
model_name = "Qwen/Qwen2.5-72B-Instruct"
sft_adapter = "./adapter/"  # 一个使用 SFT 微调的 LoRA 适配器
compute_dtype = torch.bfloat16
# 如果在使用 FlashAttention 时遇到问题，可以改用 'sdpa'
attn_implementation = 'flash_attention_2'
# 如果内存不足，可以修改以下三个训练参数
bs = 1        # 每个设备的批大小（训练和验证）
gas = 16        # 梯度累积步数
mseqlen = 512 # 最大序列长度
lr = 1e-5     # 学习率
QLoRA = True  # 是否量化基模型
output_dir = "./DPO"
# 初始化分词器
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = "<|image_pad|>"
tokenizer.pad_token_id = 151655
tokenizer.padding_side = 'right'  # 对于 Qwen2.5，左右 padding 都可以
# 加载并处理数据集
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)
ds_train = ds['train']
ds_test = ds['test']
def process(row):
    # 第一个消息是提示
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token
    row["prompt"] = prompt_messages
    row["chosen"] = chosen_messages
    row["rejected"] = rejected_messages
    return row
ds_train = ds_train.map(
    process,
    num_proc=multiprocessing.cpu_count(),
    load_from_cache_file=False,
)
ds_test = ds_test.map(
    process,
    num_proc=multiprocessing.cpu_count(),
    load_from_cache_file=False,
)
if QLoRA:
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_storage=compute_dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )
    # 冻结基模型的参数
    for name, param in model.named_parameters():
        param.requires_grad = False
    # 让输入嵌入支持梯度
    def make_inputs_require_grad(module, input, output):
        output.requires_grad_(True)
    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
else:
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': True})
# 加载 LoRA 适配器
model = PeftModel.from_pretrained(
    model,
    sft_adapter,
    is_trainable=True,
    adapter_name="DPO"
)
model.load_adapter(sft_adapter, adapter_name="reference")
# 将模型移动到设备上
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
# 训练参数配置
training_arguments = DPOConfig(
    output_dir=output_dir,
    eval_strategy="steps",
    do_eval=True,
    optim="adamw_torch",
    per_device_train_batch_size=bs,
    gradient_accumulation_steps=gas,
    per_device_eval_batch_size=bs,
    log_level="debug",
    save_strategy="steps",
    save_steps=5,
    logging_steps=2,
    learning_rate=lr,
    bf16=True,
    beta=0.1,
    eval_steps=2,
    max_steps=10,
    warmup_ratio=0.1,
    lr_scheduler_type="linear",
    max_length=mseqlen,
    max_prompt_length=512,
    dataset_num_proc=multiprocessing.cpu_count(),
    model_adapter_name="DPO",
    ref_adapter_name="reference",
    deepspeed="deepspeed_config.json",  # 指定 DeepSpeed 配置文件
)
# 初始化训练器
trainer = DPOTrainer(
    model=model,
    args=training_arguments,
    train_dataset=ds_train,
    eval_dataset=ds_test,
    tokenizer=tokenizer,
)
# 开始训练
trainer.train()
# 保存模型
trainer.save_model(output_dir)
