#!/usr/bin/env python
# GRPO quick-train  (3.5 k GSM8K, ≤30 min, 显存≈55 GB)

import os, torch, torch._dynamo, re, gc
os.environ["ACCELERATE_DISABLE_TORCH_COMPILE"] = "1"
torch.compile = lambda m,*a,**k: m
torch._dynamo.disable()

from transformers.generation.utils import GenerationMixin
_gen = GenerationMixin.generate
GenerationMixin.generate = lambda s,*a,**k: _gen(s,*a, **{kk:v for kk,v in k.items() if kk!="torch_compile"})

from collections import Counter
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig
from config import init, close, is_bfloat16_supported, get_gsm8k_questions, Config


# ---------- Reward helpers ----------
XML_RE = re.compile(r"<answer>(.*?)</answer>", re.S)
_num   = lambda x: re.sub(r"[%$,]", "", x).strip()
def _extract_nums(txt): return [_num(m) for m in XML_RE.findall(txt)]

def fmt_reward(completions, **_):
    ok = r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$"
    return [1.0 if re.match(ok, c[0]["content"]) else 0.0 for c in completions]

def cor_reward(completions, **kw):
    answers = kw.get("answer") or kw.get("answers") or []
    out = []
    for cand_list, gt in zip(completions, answers):
        nums = [n
                for c in cand_list
                for n in _extract_nums(c["content"])]
        if not nums:
            out.append(0.0); continue
        vote = Counter(nums).most_common(1)[0][0]
        diff = abs(int(vote)-int(gt)) if vote.isdigit() and gt.isdigit() else 999
        out.append(2.0 if diff==0 else 1.0 if diff==1 else 0.0)
    return out
# ------------------------------------

if __name__ == "__main__":
    init(); P = Config()

    ds = get_gsm8k_questions("train").shuffle(seed=42).select(range(3_500))

    lora = LoraConfig(
        r=64, lora_alpha=64, lora_dropout=0, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])

    model = AutoModelForCausalLM.from_pretrained(
        P.MODEL_NAME, attn_implementation="eager",
        device_map="auto", torch_dtype="auto")
    model.config.use_cache = False
    model.generation_config.torch_compile = False
    tok = AutoTokenizer.from_pretrained(P.MODEL_NAME)

    args = GRPOConfig(
        gradient_checkpointing=False,
        per_device_train_batch_size=8,
        gradient_accumulation_steps=2,  # 有效 16
        num_generations=8,
        max_prompt_length=256,
        max_completion_length=128,
        max_steps=180,
        learning_rate=1e-5, beta=0.005,
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        logging_steps=20,
        output_dir="grpo_fast",
        report_to="none",
    )

    trainer = GRPOTrainer(
        model=model, processing_class=tok,
        train_dataset=ds, peft_config=lora,
        reward_funcs=[cor_reward, fmt_reward], args=args)
    trainer.train()

    out_dir = "gemma-grpo-only"
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(out_dir, safe_serialization=True)
    tok.save_pretrained(out_dir)
    close()
