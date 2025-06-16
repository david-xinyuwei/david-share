#!/usr/bin/env python
# GRPO quick-train (2 k GSM8K, 30 min, ≈42 GB)

# ── 关闭 torch.compile / dynamo ──
import os, torch, torch._dynamo
os.environ["ACCELERATE_DISABLE_TORCH_COMPILE"] = "1"
torch.compile = lambda m,*a,**k: m
torch._dynamo.disable()

from transformers.generation.utils import GenerationMixin
_gen = GenerationMixin.generate
GenerationMixin.generate = lambda self,*a,**k: _gen(self,*a, **{kk:v for kk,v in k.items() if kk!="torch_compile"})
# ───────────────────────────────

import re
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig
from config import init, close, is_bfloat16_supported, get_gsm8k_questions, Config


# ========== reward helpers ==========
def _last_ans(x):
    m = re.findall(r"<answer>(.*?)</answer>", x, re.S)
    return re.sub(r"[%$,]", "", m[-1]).strip() if m else ""

pat = r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$"

def fmt_reward(completions, **kw):
    return [1.0 if re.match(pat, c[0]["content"]) else 0.0 for c in completions]

def cor_reward(completions, answer, **kw):
    preds = [_last_ans(c[0]["content"]) for c in completions]
    return [2.0 if p == g else 0.0 for p, g in zip(preds, answer)]


# =============== main ===============
if __name__ == "__main__":
    init()
    P = Config()

    # 1) 取 2 000 条 GSM8K
    ds = get_gsm8k_questions("train").shuffle(seed=42).select(range(2000))

    # 2) LoRA
    lora = LoraConfig(
        r=64, lora_alpha=64, lora_dropout=0, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    )

    # 3) 基座模型
    model = AutoModelForCausalLM.from_pretrained(
        P.MODEL_NAME, attn_implementation="eager",
        device_map="auto", torch_dtype="auto",
    )
    model.config.use_cache = False
    model.generation_config.torch_compile = False
    tok = AutoTokenizer.from_pretrained(P.MODEL_NAME)

    # 4) GRPOConfig
    args = GRPOConfig(
        learning_rate=1e-5, adam_beta1=0.9, adam_beta2=0.99,
        weight_decay=0.1, warmup_ratio=0.05, beta=0.005,
        lr_scheduler_type="cosine", optim="adamw_8bit",

        bf16=is_bfloat16_supported(), fp16=not is_bfloat16_supported(),
        gradient_checkpointing=False,
        per_device_train_batch_size=8,          # ↑ batch
        gradient_accumulation_steps=1,          # 有效 16
        num_generations=8,                      # ↑ 并发生成
        temperature=0.5,
        max_prompt_length=256,
        max_completion_length=128,

        num_train_epochs=1,
        max_steps=180,                          # 30 min

        logging_steps=20,
        max_grad_norm=0.1,
        output_dir="outputs_fast",
        report_to="none",
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tok,
        reward_funcs=[cor_reward, fmt_reward],
        args=args,
        train_dataset=ds,
        peft_config=lora,
    )

    trainer.train()

    out = "gemma-grpo-only"
    merged = trainer.model.merge_and_unload()
    tok.save_pretrained(out)
    merged.save_pretrained(out)
    close()
