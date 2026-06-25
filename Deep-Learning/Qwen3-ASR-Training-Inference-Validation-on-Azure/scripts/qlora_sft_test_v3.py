#!/usr/bin/env python3
"""QLoRA SFT test v3: train PEFT-wrapped thinker directly."""
from __future__ import annotations
import importlib.util, json, re, time
from pathlib import Path
import numpy as np, torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from qwen_asr import Qwen3ASRModel
from transformers import BitsAndBytesConfig, Trainer, TrainingArguments
RESULTS=Path('/root/asr_results'); TRAIN_FILE='/root/fleurs_sft/train.jsonl'; BASE_MODEL='Qwen/Qwen3-ASR-0.6B'

def load_mod():
    spec=importlib.util.spec_from_file_location('qwen3_asr_sft_mod','/root/Qwen3-ASR/finetuning/qwen3_asr_sft.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def norm(t):
    t=t.strip().lower(); t=re.sub(r'[\u3000\s]+',' ',t); t=re.sub(r'[，。！？、；：,.!?;:\"\'()\[\]{}<>《》“”‘’\-·…—]+','',t); return t.replace(' ','')

def cer(ref,hyp):
    r,h=list(norm(ref)),list(norm(hyp));
    if not r: return 0.0 if not h else 1.0
    prev=list(range(len(h)+1))
    for i,rc in enumerate(r,1):
        cur=[i]+[0]*len(h)
        for j,hc in enumerate(h,1): cur[j]=min(prev[j]+1,cur[j-1]+1,prev[j-1]+(0 if rc==hc else 1))
        prev=cur
    return prev[-1]/len(r)

def prep_ds(mod,processor):
    ds=load_dataset('json',data_files={'train':TRAIN_FILE})
    ds=ds.map(mod.make_preprocess_fn_prefix_only(processor),num_proc=1)
    keep={'prompt','audio','target','prefix_text'}; drop=[c for c in ds['train'].column_names if c not in keep]
    if drop: ds['train']=ds['train'].remove_columns(drop)
    return ds['train']

def eval_asr(asr,n=80):
    ds=load_dataset('google/fleurs','cmn_hans_cn',split='test').select(range(n)); refs=[s['transcription'] for s in ds]
    wavs=sorted(Path('/root/asr_results/fleurs_wav').glob('*.wav'))[:n]; hyps=[]; st=time.time()
    for w in wavs: hyps.append(asr.transcribe([str(w)])[0].text)
    elapsed=time.time()-st; cers=[cer(r,h) for r,h in zip(refs,hyps)]
    return {'samples':n,'cer_mean':round(float(np.mean(cers)),4),'cer_median':round(float(np.median(cers)),4),'num_perfect':int(sum(x==0 for x in cers)),'elapsed_s':round(elapsed,1),'examples':[{'ref':refs[i],'hyp':hyps[i]} for i in range(5)]}

def main():
    mod=load_mod(); bnb=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype=torch.float32)
    asr=Qwen3ASRModel.from_pretrained(BASE_MODEL,quantization_config=bnb,device_map='cuda')
    thinker=prepare_model_for_kbit_training(asr.model.thinker)
    lora=LoraConfig(r=16,lora_alpha=32,lora_dropout=0.05,target_modules=['q_proj','k_proj','v_proj','o_proj'],task_type=TaskType.CAUSAL_LM)
    thinker=get_peft_model(thinker,lora)
    asr.model.thinker=thinker
    trainable=sum(p.numel() for p in thinker.parameters() if p.requires_grad); total=sum(p.numel() for p in asr.model.parameters())
    ds=prep_ds(mod,asr.processor); collator=mod.DataCollatorForQwen3ASRFinetuning(processor=asr.processor,sampling_rate=16000)
    args=TrainingArguments(output_dir='/tmp/qwen3_qlora_v3',per_device_train_batch_size=1,gradient_accumulation_steps=4,learning_rate=5e-6,num_train_epochs=3,logging_steps=5,lr_scheduler_type='linear',warmup_ratio=0.1,save_strategy='no',eval_strategy='no',bf16=False,fp16=False,remove_unused_columns=False,report_to='none',max_grad_norm=1.0)
    trainer=Trainer(model=thinker,args=args,train_dataset=ds,data_collator=collator,tokenizer=asr.processor.tokenizer)
    st=time.time(); out=trainer.train(); runtime=time.time()-st
    ev=eval_asr(asr,80)
    res={'test':'qlora_sft_nf4_rank16_train_thinker','status':'completed','trainable_params':trainable,'total_params':total,'trainable_ratio':round(trainable/total*100,4),'train_runtime_s':round(runtime,1),'train_loss':float(getattr(out,'training_loss',0.0)),'logs':trainer.state.log_history,'eval':ev}
    (RESULTS/'qlora_sft_result.json').write_text(json.dumps(res,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(res,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':
    try: main()
    except Exception as e:
        res={'test':'qlora_sft_nf4_rank16_train_thinker','status':'failed','error':repr(e)}
        (RESULTS/'qlora_sft_result.json').write_text(json.dumps(res,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(res,indent=2,ensure_ascii=False),flush=True); raise
