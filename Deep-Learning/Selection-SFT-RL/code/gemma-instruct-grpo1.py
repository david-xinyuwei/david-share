#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ================================================================
#   gemma-instruct-grpo.py  ―  SFT (LIMO) + GRPO (GSM8K)
# ================================================================

# ---- 0. 全局屏蔽 torch.compile / torch._dynamo ------------------
import os, torch
os.environ["ACCELERATE_DISABLE_TORCH_COMPILE"] = "1"
def _no_compile(model=None, *a, **kw):     # 空实现
    return model
torch.compile = _no_compile                # 覆盖全局 compile
import torch._dynamo
torch._dynamo.disable()                    # 彻底禁用 dynamo
# ----------------------------------------------------------------

# -- 0.1  monkey-patch generate()，忽略 torch_compile kwarg --------
from transformers.generation.utils import GenerationMixin
_orig_generate = GenerationMixin.generate
def _generate_no_compile(self, *a, **kw):
    kw.pop("torch_compile", None)
    return _orig_generate(self, *a, **kw)
GenerationMixin.generate = _generate_no_compile
# ----------------------------------------------------------------

import re, gc, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import GRPOConfig, GRPOTrainer, SFTConfig, SFTTrainer
from peft import LoraConfig
from config import (
    init,
    close,
    is_bfloat16_supported,
    get_gsm8k_questions,
    get_limo,
    Config,
)

# ------------------------- 工具函数 ------------------------------
def extract_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    m = re.search(re.escape(start_tag) + r"(.*?)" + re.escape(end_tag), text, re.S)
    return re.sub(r"[%$]", "", m.group(1)).strip() if m else ""


def extract_last_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    matches = re.findall(re.escape(start_tag) + r"(.*?)" + re.escape(end_tag), text, re.S)
    return re.sub(r"[%$]", "", matches[-1]).strip() if matches else ""


def format_reward_func(completions, **_):
    pat = r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$"
    return [1.0 if re.match(pat, c[0]["content"]) else 0.0 for c in completions]


def correctness_reward_func(completions, answer, **_):
    preds = [extract_last_xml_answer(c[0]["content"]) for c in completions]
    return [2.0 if p == g else 0.0 for p, g in zip(preds, answer)]


# --------------------------- 主流程 ------------------------------
if __name__ == "__main__":
    init()
    params = Config()

    # 1) LoRA 配置（SFT 与 GRPO 共用）
    peft_config = LoraConfig(
        r=64,
        lora_alpha=64,
        lora_dropout=0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )

    # 2) 加载基础模型（eager-attention）
    model = AutoModelForCausalLM.from_pretrained(
        params.MODEL_NAME,
        torch_dtype="auto",
        attn_implementation="eager",
        device_map="auto",
    )
    model.config.use_cache = False
    model.generation_config.torch_compile = False  # 防御式再关一次

    tokenizer = AutoTokenizer.from_pretrained(params.MODEL_NAME)

    # ====================  第一阶段：SFT on LIMO  ====================
    limo_train = get_limo(split="train")

    sft_args = SFTConfig(
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        max_seq_length=2048,
        optim="adamw_8bit",
        learning_rate=2e-4,
        weight_decay=0.01,
        max_grad_norm=0.3,
        lr_scheduler_type="linear",
        num_train_epochs=1,
        warmup_ratio=0.05,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        remove_unused_columns=False,
        label_names=[],
        dataset_num_proc=4,
        packing=False,
        save_steps=100,
        report_to="tensorboard",
        logging_dir="logs/sft_runs",
        output_dir="sft_output",
        overwrite_output_dir=True,
        seed=0,
    )

    def formatting_func(example):
        return example["prompt"]

    sft_trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=limo_train,
        peft_config=peft_config,
        formatting_func=formatting_func,
    )

    print("\n**********  SFT Fine-Tuning on LIMO  **********")
    sft_trainer.train()

    # 释放内存
    del sft_trainer, sft_args, limo_train
    torch.cuda.empty_cache()
    gc.collect()

    # ====================  第二阶段：GRPO on GSM8K  ====================
    gsm8k_train = get_gsm8k_questions(split="train")

    grpo_args = GRPOConfig(
        # ——优化器—————————————
        learning_rate=1e-5,
        adam_beta1=0.9,
        adam_beta2=0.99,
        weight_decay=0.1,
        warmup_ratio=0.05,
        beta=0.005,
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        # ——精度 & 显存—————————
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        gradient_accumulation_steps=4,
        per_device_train_batch_size=4,
        # ——生成—————————————
        num_generations=4,
        temperature=0.5,
        max_prompt_length=params.max_prompt_length,
        max_completion_length=params.max_completion_length,
        # ——训练日程———————————
        num_train_epochs=2,
        max_steps=1024,          # 如想按 epoch 控制可注释掉
        # ——日志 / 保存—————————
        logging_steps=100,
        save_steps=500,
        report_to="tensorboard",
        logging_dir="logs/grpo_runs",
        output_dir="grpo_output",
        overwrite_output_dir=True,
        max_grad_norm=0.1,
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[correctness_reward_func, format_reward_func],
        args=grpo_args,
        train_dataset=gsm8k_train,
        peft_config=peft_config,
    )

    print("\n**********  RL Fine-Tuning on GSM8K  **********")
    trainer.train()

    # ====================  保存最终模型  ====================
    merged = trainer.model.merge_and_unload()
    tokenizer.save_pretrained(params.OUTPUT_MODEL)
    merged.save_pretrained(params.OUTPUT_MODEL)

    close()
