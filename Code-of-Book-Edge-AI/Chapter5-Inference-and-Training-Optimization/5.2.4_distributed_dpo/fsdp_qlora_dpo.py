# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第5章 §5.2.4 FSDP training
# 书中文件名为 fsdp+QLoRA.py

import torch
import os
import multiprocessing
from datasets import load_dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed,
)
from peft.utils.other import fsdp_auto_wrap_policy
from accelerate import Accelerator, FullyShardedDataParallelPlugin
from trl import DPOTrainer, DPOConfig
# 设置随机种子
set_seed(1234)
# 配置FSDP插件
fsdp_plugin = FullyShardedDataParallelPlugin(
    sharding_strategy="FULL_SHARD",
    backward_prefetch="BACKWARD_PRE",
    forward_prefetch=False,
    cpu_offload=False,
    use_orig_params=True,  # Set use_orig_params to True
    auto_wrap_policy="TRANSFORMER_BASED_WRAP",
    mixed_precision_policy={
        "param_dtype": torch.float16,
        "reduce_dtype": torch.float16,
        "buffer_dtype": torch.float16,
    },
)
# 初始化Accelerator
accelerator = Accelerator(
    mixed_precision="no",
    fsdp_plugin=fsdp_plugin,
    log_with=None,
)
# 模型配置
model_name = "Qwen/Qwen2.5-72B-Instruct"
sft_adapter = "./SFT_LoRA/"  # SFT训练好的 LoRA 适配器路径
compute_dtype = torch.float16  # 计算精度float16
# 注意力实现方式(显存不足时改为eager)
attn_implementation = 'eager'
# 训练参数
bs = 1  # 单设备批大小
gas = 1  # 梯度累积步数
mseqlen = 32  # 最大序列长度
lr = 1e-6  # 学习率
QLoRA = True
lora_alpha = 16
lora_dropout = 0.0
lora_r = 4
output_dir = "/workspace/DPO_LoRA"
# 分词器初始化
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = "<|image_pad|>"
tokenizer.pad_token_id = 151655
tokenizer.padding_side = 'right'  # 右侧填充
# 数据加载与处理
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)
ds_train = ds['train']
ds_test = ds['test']
def process(row):
    # 第一条消息是用户提示
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token
    row["prompt"] = prompt_messages
    row["chosen"] = chosen_messages
    row["rejected"] = rejected_messages
    return row
ds_train = ds_train.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)
ds_test = ds_test.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)
# 模型加载与量化
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
    for name, param in model.named_parameters():
        param.requires_grad = False
    def make_inputs_require_grad(module, input, output):
        output.requires_grad_(True)
    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
else:
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )
# 加载LoRA适配器
model = PeftModel.from_pretrained(model, sft_adapter, is_trainable=True, adapter_name="DPO")
model.load_adapter(sft_adapter, adapter_name="reference")
# Ensure all model parameters are in torch.float16
model.to(torch.float16)
# Ensure all model parameters are on the correct device
model.to(accelerator.device)
# 训练参数配置
training_arguments = DPOConfig(
    output_dir=output_dir,
    eval_strategy="steps",
    do_eval=True,
    optim="adamw_hf",  # 使用PyTorch融合优化器
    per_device_train_batch_size=bs,
    gradient_accumulation_steps=gas,
    per_device_eval_batch_size=bs,
    log_level="debug",
    save_strategy="steps",
    save_steps=5,
    logging_steps=2,
    learning_rate=lr,
    bf16=True,
    fp16=False,
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
    report_to="none",
    max_grad_norm=1.0,
)
# 初始化DPO训练器
trainer = DPOTrainer(
    model=model,
    args=training_arguments,
    train_dataset=ds_train,
    eval_dataset=ds_test,
    processing_class=tokenizer,
)
# 开始训练
trainer.train()
