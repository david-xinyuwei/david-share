#!/usr/bin/env python
# ==========================================================
#  gemma-instruct-grpo.py  – 30-min 快跑（SFT + GRPO）
#    SFT : 817 LIMO  (batch 2 × accum 4)
#    GRPO: 2k GSM8K  (batch 8 × accum 2, gen 8)
# ==========================================================

# ---------- 全局关闭 torch.compile / dynamo ----------
import os, torch, torch._dynamo, re, gc
os.environ["ACCELERATE_DISABLE_TORCH_COMPILE"] = "1"
torch.compile = lambda m,*a,**k: m
torch._dynamo.disable()

# 让 generate() 忽略 torch_compile kwarg
from transformers.generation.utils import GenerationMixin
_gen = GenerationMixin.generate
GenerationMixin.generate = (
    lambda self,*a,**k: _gen(
        self, *a, **{kk:v for kk,v in k.items() if kk != "torch_compile"}
    )
)
# -------------------------------------------------------

from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import SFTConfig, SFTTrainer, GRPOConfig, GRPOTrainer
from peft import LoraConfig
from config import (
    init, close,
    is_bfloat16_supported,
    get_limo, get_gsm8k_questions, Config,
)

# ---------------- Reward helpers ----------------
XML_FMT = r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$"

def _last_ans(txt: str):
    m = re.findall(r"<answer>(.*?)</answer>", txt, re.S)
    return re.sub(r"[%$,]", "", m[-1]).strip() if m else ""

def fmt_reward(completions, **kw):
    return [
        1.0 if re.match(XML_FMT, c[0]["content"]) else 0.0
        for c in completions
    ]

def cor_reward(completions, **kw):
    answers = kw.get("answer") or kw.get("answers") or []
    preds   = [_last_ans(c[0]["content"]) for c in completions]
    return [2.0 if p == g else 0.0 for p, g in zip(preds, answers)]
# ------------------------------------------------

if __name__ == "__main__":
    init()
    cfg = Config()

    # 1) LoRA
    lora_cfg = LoraConfig(
        r=64, lora_alpha=64, lora_dropout=0, bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj","k_proj","v_proj","o_proj",
            "gate_proj","up_proj","down_proj",
        ],
    )

    # 2) Base model
    model = AutoModelForCausalLM.from_pretrained(
        cfg.MODEL_NAME,
        attn_implementation="eager",
        device_map="auto",
        torch_dtype="auto",
    )
    model.config.use_cache = False
    model.generation_config.torch_compile = False
    tok = AutoTokenizer.from_pretrained(cfg.MODEL_NAME)

    # ====================  SFT  ====================
    print("\n*****  SFT | 817 LIMO  *****")
    limo = get_limo("train").map(lambda ex: {"completion": ""})   # 补空 completion

    sft_cfg = SFTConfig(
        gradient_checkpointing=False,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        max_seq_length=2048,
        optim="adamw_8bit",
        learning_rate=2e-4,
        num_train_epochs=1,
        logging_steps=50,
        output_dir="sft_fast",
        report_to="none",
        completion_only_loss=False,
    )

    SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=limo,
        peft_config=lora_cfg,
    ).train()

    del limo, sft_cfg
    gc.collect(); torch.cuda.empty_cache()

    # ====================  GRPO  ====================
    print("\n*****  GRPO | 2 k GSM8K  *****")
    gsm = get_gsm8k_questions("train").shuffle(seed=42).select(range(2_000))

    grpo_cfg = GRPOConfig(
        gradient_checkpointing=False,
        per_device_train_batch_size=8,
        gradient_accumulation_steps=2,     # 有效 batch 16
        num_generations=8,
        max_prompt_length=256,
        max_completion_length=128,
        max_steps=180,

        learning_rate=1e-5,
        adam_beta1=0.9, adam_beta2=0.99,
        weight_decay=0.1, warmup_ratio=0.05,
        beta=0.005, lr_scheduler_type="cosine",
        optim="adamw_8bit",

        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),

        logging_steps=20,
        output_dir="grpo_fast",
        report_to="none",
    )

    grpo_trainer = GRPOTrainer(
        model=model,
        processing_class=tok,
        train_dataset=gsm,
        peft_config=lora_cfg,
        reward_funcs=[cor_reward, fmt_reward],
        args=grpo_cfg,
    )
    grpo_trainer.train()

    # --------------- save merged model ---------------
    out_dir = "gemma-sft-grpo"
    peft_model = grpo_trainer.model

    if hasattr(peft_model, "merge_and_unload"):          # peft >= 0.4
        merged_model = peft_model.merge_and_unload()
    else:                                                # older peft fallback
        peft_model.merge_adapter()
        merged_model = peft_model.base_model

    merged_model.save_pretrained(out_dir, safe_serialization=True)
    tok.save_pretrained(out_dir)
    print(f"\nMerged model saved to  {out_dir}")

    close()
