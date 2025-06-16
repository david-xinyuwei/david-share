#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ================================================================
#   gemma-grpo.py  ―  GRPO 微调 Gemma-2-2B-IT（无 vLLM 版）
# ================================================================

# ---- 0. 全局关闭 torch.compile / torch._dynamo -----------------
import os, torch
os.environ["ACCELERATE_DISABLE_TORCH_COMPILE"] = "1"  # 防止 accelerate 侧调用
def _no_compile(model=None, *args, **kwargs):         # 空实现
    return model
torch.compile = _no_compile                           # 覆盖全局 compile
import torch._dynamo
torch._dynamo.disable()                               # 彻底禁用 dynamo
# ----------------------------------------------------------------

import re
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig
from config import (
    init,
    close,
    is_bfloat16_supported,
    get_gsm8k_questions,
    Config,
)


# ------------------------- 辅助函数 ------------------------------
def extract_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    match = re.search(pattern, text, re.S)
    return re.sub(r"[%$]", "", match.group(1)).strip() if match else ""


def extract_last_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    matches = re.findall(pattern, text, re.S)
    return re.sub(r"[%$]", "", matches[-1]).strip() if matches else ""


def format_reward_func(completions, **kwargs):
    """+1 : 完全符合 XML 模板"""
    pattern = r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$"
    return [1.0 if re.match(pattern, c[0]["content"]) else 0.0 for c in completions]


def correctness_reward_func(completions, answer, **kwargs):
    """+2 : 提取出的最终答案与真值完全一致"""
    preds = [extract_last_xml_answer(c[0]["content"]) for c in completions]
    return [2.0 if p == g else 0.0 for p, g in zip(preds, answer)]


# --------------------------- 主流程 ------------------------------
if __name__ == "__main__":
    init()
    params = Config()

    # 1) 数据集
    gsm8k_train = get_gsm8k_questions(split="train")

    # 2) LoRA 配置
    peft_config = LoraConfig(
        r=64,
        lora_alpha=64,
        lora_dropout=0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    # 3) 加载基础模型（eager attention，禁 cache）
    model = AutoModelForCausalLM.from_pretrained(
        params.MODEL_NAME,
        torch_dtype="auto" if is_bfloat16_supported() else "auto",
        attn_implementation="eager",
        device_map="auto",  # 单卡时即 cuda:0
    )
    model.config.use_cache = False
    model.generation_config.torch_compile = False  # 再保险一层

    tokenizer = AutoTokenizer.from_pretrained(params.MODEL_NAME)

    # 4) GRPOConfig（无 vLLM 字段）
    training_args = GRPOConfig(
        # ——优化器参数——————————————————————————
        learning_rate=1e-5,
        adam_beta1=0.9,
        adam_beta2=0.99,
        weight_decay=0.1,
        warmup_ratio=0.1,
        beta=0.005,
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        # ——精度 / 显存—————————————————————————
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        gradient_accumulation_steps=4,
        per_device_train_batch_size=4,
        # ——生成参数——————————————————————————
        num_generations=4,
        temperature=0.5,
        max_prompt_length=params.max_prompt_length,
        max_completion_length=params.max_completion_length,
        # ——训练日程——————————————————————————
        num_train_epochs=2,
        # max_steps=1024,  # 如需步数优先生效可取消注释
        # ——日志 / 保存—————————————————————————
        logging_steps=100,
        save_steps=500,
        max_grad_norm=0.1,
        report_to="tensorboard",
        logging_dir="logs/runs",
        output_dir="outputs",
    )

    # 5) Trainer
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[correctness_reward_func, format_reward_func],
        args=training_args,
        train_dataset=gsm8k_train,
        peft_config=peft_config,
    )

    # 6) 开始训练
    trainer.train()

    # 7) 合并 LoRA 权重并保存
    merged_model = trainer.model.merge_and_unload()
    tokenizer.save_pretrained(params.OUTPUT_MODEL)
    merged_model.save_pretrained(params.OUTPUT_MODEL)

    close()
