#!/usr/bin/env python
# 30-min SFT+GRPO   (LIMO 1 600  +  GSM8K 3 500)

import os, torch, torch._dynamo, re, gc, collections
os.environ["ACCELERATE_DISABLE_TORCH_COMPILE"]="1"
torch.compile=lambda m,*a,**k:m; torch._dynamo.disable()

from transformers.generation.utils import GenerationMixin
_gen=GenerationMixin.generate
GenerationMixin.generate=lambda s,*a,**k:_gen(s,*a,**{kk:v for kk,v in k.items() if kk!="torch_compile"})

from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import SFTConfig, SFTTrainer, GRPOConfig, GRPOTrainer
from peft import LoraConfig
from config import init, close, is_bfloat16_supported, get_limo, get_gsm8k_questions, Config

# ---------- reward helpers ----------
XML_RE = re.compile(r"<answer>(.*?)</answer>", re.S)
def _num(x:str): return re.sub(r"[%$,]","",x).strip()
def _nums(txt:str): return [_num(m) for m in XML_RE.findall(txt)]
def fmt_reward(completions, **_):
    ok = r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$"
    return [1.0 if re.match(ok,c[0]["content"]) else 0.0 for c in completions]
def cor_reward(completions, **kw):
    gts = kw.get("answer") or kw.get("answers") or []
    outs=[]
    for cand,gt in zip(completions,gts):
        votes=_nums(" ".join(m["content"] for m in cand))
        if not votes: outs.append(0.0);continue
        vote=collections.Counter(votes).most_common(1)[0][0]
        diff=abs(int(vote)-int(gt)) if vote.isdigit()and gt.isdigit() else 999
        outs.append(2.0 if diff==0 else 1.0 if diff==1 else 0.0)
    return outs
# ------------------------------------

if __name__=="__main__":
    init(); cfg=Config()

    lora=LoraConfig(
        r=64,lora_alpha=64,lora_dropout=0,bias="none",task_type="CAUSAL_LM",
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])

    base=AutoModelForCausalLM.from_pretrained(
        cfg.MODEL_NAME,attn_implementation="eager",
        device_map="auto",torch_dtype="auto")
    base.config.use_cache=False
    base.generation_config.torch_compile=False
    tok=AutoTokenizer.from_pretrained(cfg.MODEL_NAME)

    # -------- SFT (LIMO 1600) --------
    limo=get_limo("train")
    limo=limo.shuffle(seed=42)
    limo=limo.select(range(min(1600,len(limo)))).map(lambda x:{"completion":""})
    sft=SFTConfig(
        gradient_checkpointing=False,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        bf16=is_bfloat16_supported(), fp16=not is_bfloat16_supported(),
        num_train_epochs=1, max_seq_length=2048,
        learning_rate=2e-4, optim="adamw_8bit",
        logging_steps=50, output_dir="sft_fast", report_to="none",
        completion_only_loss=False,
    )
    SFTTrainer(model=base,args=sft,train_dataset=limo,peft_config=lora).train()
    del limo,sft; gc.collect(); torch.cuda.empty_cache()

    # -------- GRPO (GSM8K 3500) --------
    gsm=get_gsm8k_questions("train").shuffle(seed=42).select(range(3_500))
    gcfg=GRPOConfig(
        gradient_checkpointing=False,
        per_device_train_batch_size=8, gradient_accumulation_steps=2,
        num_generations=8, max_prompt_length=256, max_completion_length=128,
        max_steps=180, learning_rate=1e-5, beta=0.005,
        bf16=is_bfloat16_supported(), fp16=not is_bfloat16_supported(),
        logging_steps=20, output_dir="grpo_fast", report_to="none",
    )
    gtrainer=GRPOTrainer(
        model=base,processing_class=tok,train_dataset=gsm,
        peft_config=lora,reward_funcs=[cor_reward,fmt_reward],args=gcfg)
    gtrainer.train()

    out="gemma-sft-grpo"
    pmodel=gtrainer.model
    merged=pmodel.merge_and_unload() if hasattr(pmodel,"merge_and_unload") else (pmodel.merge_adapter() or pmodel.base_model)
    merged.save_pretrained(out,safe_serialization=True); tok.save_pretrained(out)
    close()
