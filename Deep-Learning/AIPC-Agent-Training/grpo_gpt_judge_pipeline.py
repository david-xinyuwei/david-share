"""
GRPO Training with GPT-5.2 as Judge + DPO Pipeline
L5 Production Training for AIPC Agent
"""
import os, json, torch, re, time, requests
os.environ["WANDB_DISABLED"] = "true"

from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer, DPOTrainer, DPOConfig
from datasets import Dataset, load_dataset

APIM_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://<your-apim-or-aoai-endpoint>/openai")
APIM_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "<your-api-key>")
API_VERSION = "2025-04-01-preview"
JUDGE_MODEL = "gpt-5.2"
SFT_MODEL = "checkpoints/aipc_sft_v1"
GRPO_OUTPUT = "checkpoints/aipc_grpo_v1.1"

print("=" * 70)
print("L5 AIPC Pipeline: GRPO (GPT-5.2 Judge) + DPO Chain")
print("=" * 70)

def gpt52_judge_reward(completions, prompts=None, **kwargs):
    rewards = []
    for i, completion in enumerate(completions):
        prompt_text = prompts[i] if prompts else ""
        try:
            url = f"{APIM_ENDPOINT}/deployments/{JUDGE_MODEL}/chat/completions?api-version={API_VERSION}"
            headers = {"Content-Type": "application/json", "api-key": APIM_KEY}
            eval_text = f"Rate this customer support response quality (1-10). Only return the number.\nQuestion: {prompt_text[:300]}\nResponse: {completion[:500]}\nScore (1-10):"
            data = {"messages": [{"role": "user", "content": eval_text}], "max_completion_tokens": 5, "temperature": 0}
            resp = requests.post(url, headers=headers, json=data, timeout=15)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                match = re.search(r"(\d+)", content)
                if match:
                    score = min(10, max(1, int(match.group(1))))
                    rewards.append((score - 5) / 5)
                else:
                    rewards.append(0.0)
            elif resp.status_code == 429:
                time.sleep(2)
                rewards.append(0.0)
            else:
                rewards.append(0.0)
        except Exception as e:
            rewards.append(0.0)
    return rewards

print("[Test] GPT-5.2 judge...")
test_r = gpt52_judge_reward(completions=["AI PC has NPU for local inference"], prompts=["What is AI PC?"])
print(f"  Test reward: {test_r[0]}")

print(f"\n[GRPO] Loading {SFT_MODEL}...")
prompts = []
with open("data/aipc_sft_train.jsonl") as f:
    for line in f:
        item = json.loads(line)
        q = item.get("question") or item.get("prompt", "")
        if q: prompts.append({"prompt": q})
prompts = prompts[:200]
dataset = Dataset.from_list(prompts)
print(f"  Prompts: {len(prompts)}")

tokenizer = AutoTokenizer.from_pretrained(SFT_MODEL)
if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(SFT_MODEL, torch_dtype=torch.bfloat16, device_map="auto")

config = GRPOConfig(output_dir=GRPO_OUTPUT, num_train_epochs=1, per_device_train_batch_size=4, gradient_accumulation_steps=4, learning_rate=5e-7, max_completion_length=256, num_generations=4, temperature=0.8, logging_steps=5, save_strategy="no", bf16=True, remove_unused_columns=False, report_to="none")

trainer = GRPOTrainer(model=model, args=config, train_dataset=dataset, processing_class=tokenizer, reward_funcs=gpt52_judge_reward)

print("  Starting GRPO with GPT-5.2 judge...")
t0 = time.time()
trainer.train()
print(f"  GRPO done in {time.time()-t0:.0f}s")
trainer.save_model(GRPO_OUTPUT)
tokenizer.save_pretrained(GRPO_OUTPUT)
del model, trainer; torch.cuda.empty_cache()

for stage, model_in, data_file, model_out in [
    ("V1.2 Style", GRPO_OUTPUT, "data/aipc_style_dpo.jsonl", "checkpoints/aipc_dpo_v1.2"),
    ("V1.3 Feedback", "checkpoints/aipc_dpo_v1.2", "data/aipc_feedback_v1.3.jsonl", "checkpoints/aipc_dpo_v1.3"),
    ("V1.4 Code", "checkpoints/aipc_dpo_v1.3", "data/aipc_code_feedback_v1.4.jsonl", "checkpoints/aipc_dpo_v1.4"),
]:
    print(f"\n[DPO {stage}] {model_in} -> {model_out}")
    tok = AutoTokenizer.from_pretrained(model_in)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    ds = load_dataset("json", data_files=data_file, split="train")
    m = AutoModelForCausalLM.from_pretrained(model_in, torch_dtype=torch.bfloat16, device_map="auto")
    cfg = DPOConfig(output_dir=model_out, beta=0.1, learning_rate=5e-7, per_device_train_batch_size=2, gradient_accumulation_steps=2, num_train_epochs=3, logging_steps=1, save_strategy="no", bf16=True, remove_unused_columns=False, report_to="none", max_length=2048, max_prompt_length=1024)
    t = DPOTrainer(model=m, ref_model=None, args=cfg, train_dataset=ds, processing_class=tok)
    t.train()
    t.save_model(model_out); tok.save_pretrained(model_out)
    print(f"  {stage} done")
    del m, t; torch.cuda.empty_cache()

print("\n" + "=" * 70)
print("[Eval] Base vs V1.4 with GPT-5.2 scoring")
print("=" * 70)

test_qs = [
    "What is an AI PC and how does it differ from a regular laptop?",
    "How can I deploy a 7B language model on a local AI PC?",
    "My VPN connection keeps dropping. How do I troubleshoot?",
    "What are the benefits of NPU over GPU for AI inference?",
    "How to check if Intel Core Ultra NPU is being utilized?",
]

def gen(mp, q):
    tk = AutoTokenizer.from_pretrained(mp)
    md = AutoModelForCausalLM.from_pretrained(mp, torch_dtype=torch.bfloat16, device_map="auto")
    ids = tk.apply_chat_template([{"role":"user","content":q}], return_tensors="pt", add_generation_prompt=True).to(md.device)
    out = md.generate(ids, max_new_tokens=256, temperature=0.6, do_sample=True)
    r = tk.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
    del md; torch.cuda.empty_cache()
    return r

def score(q, r):
    try:
        url = f"{APIM_ENDPOINT}/deployments/{JUDGE_MODEL}/chat/completions?api-version={API_VERSION}"
        data = {"messages":[{"role":"user","content":f"Rate 1-10. Only number.\nQ:{q}\nA:{r[:500]}\nScore:"}],"max_completion_tokens":5,"temperature":0}
        resp = requests.post(url, headers={"Content-Type":"application/json","api-key":APIM_KEY}, json=data, timeout=15)
        if resp.status_code == 200:
            m = re.search(r"(\d+)", resp.json()["choices"][0]["message"]["content"])
            return int(m.group(1)) if m else 0
        return 0
    except: return 0

print(f"\n{'Question':<50} {'Base':>6} {'V1.4':>6}")
print("-" * 64)
bs, vs = [], []
for q in test_qs:
    br = gen("/root/Llama-3.2-3B-Instruct", q)
    vr = gen("checkpoints/aipc_dpo_v1.4", q)
    b = score(q, br); v = score(q, vr)
    bs.append(b); vs.append(v)
    print(f"{q[:48]:<50} {b:>5}/10 {v:>5}/10")
print("-" * 64)
ab = sum(bs)/len(bs); av = sum(vs)/len(vs)
print(f"{'AVERAGE':<50} {ab:>5.1f}/10 {av:>5.1f}/10")
imp = ((av-ab)/ab*100) if ab>0 else 0
print(f"Improvement: {imp:+.1f}%")
print("\nALL COMPLETE")
