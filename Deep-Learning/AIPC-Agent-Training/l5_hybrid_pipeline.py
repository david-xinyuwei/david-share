"""
L5 GRPO with Hybrid Reward (Rule-based + GPT-5.2 Judge) + DPO + Eval
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
print("L5 Hybrid Reward: Rule-based (0~0.5) + GPT Judge (-0.3~+0.5)")
print("=" * 70)

# ============================================================
# Hybrid Reward: rule-based baseline + GPT quality adjustment
# ============================================================
KEYWORDS = ["support", "ticket", "help", "issue", "resolve", "troubleshoot",
            "password", "reset", "network", "VPN", "account", "install",
            "error", "update", "configuration", "service", "permission"]

def rule_reward(completion):
    """Rule-based: 0 ~ 0.5 (always positive baseline)"""
    s = 0.0
    c = completion.lower()
    kw = sum(1 for k in KEYWORDS if k.lower() in c)
    s += min(0.15, kw * 0.02)
    l = len(completion)
    if 100 <= l <= 600: s += 0.1
    elif 50 <= l < 100 or 600 < l <= 1000: s += 0.05
    if any(m in completion for m in ["1.", "2.", "3.", "-", "Step", "First"]): s += 0.1
    if "\n" in completion and len(completion.split("\n")) >= 3: s += 0.05
    if not any(h in completion for h in ["I don't know", "I cannot", "as an AI"]): s += 0.1
    return min(0.5, s)

def gpt_judge(prompt, completion):
    """GPT-5.2 judge: returns -0.3 ~ +0.5 adjustment"""
    try:
        url = f"{APIM_ENDPOINT}/deployments/{JUDGE_MODEL}/chat/completions?api-version={API_VERSION}"
        headers = {"Content-Type": "application/json", "api-key": APIM_KEY}
        eval_text = f"Rate this support response 1-10. Only return the number.\nQ: {prompt[:200]}\nA: {completion[:400]}\nScore:"
        data = {"messages": [{"role": "user", "content": eval_text}], "max_completion_tokens": 5, "temperature": 0}
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            match = re.search(r"(\d+)", content)
            if match:
                score = min(10, max(1, int(match.group(1))))
                # Map 1-10 to -0.3~+0.5: score 3 = 0, score 7 = +0.3, score 10 = +0.5
                return (score - 3) / 14  # 1->-0.14, 3->0, 5->+0.14, 7->+0.29, 10->+0.5
        return 0.0
    except:
        return 0.0

def hybrid_reward(completions, prompts=None, **kwargs):
    """Combined: rule(0~0.5) + gpt(-0.3~0.5) = total -0.3 ~ 1.0"""
    rewards = []
    for i, c in enumerate(completions):
        p = prompts[i] if prompts else ""
        r = rule_reward(c)
        g = gpt_judge(p, c)
        total = r + g
        rewards.append(total)
    return rewards

# Test
print("[Test] Hybrid reward...")
good = "To resolve your VPN connection issue:\n1. Check your network settings\n2. Restart the VPN client\n3. Verify your credentials\n4. Contact IT support if the issue persists."
bad = "I don't know."
t_good = hybrid_reward(completions=[good], prompts=["VPN keeps dropping"])
t_bad = hybrid_reward(completions=[bad], prompts=["VPN keeps dropping"])
print(f"  Good response: {t_good[0]:.3f} (expect > 0.3)")
print(f"  Bad response:  {t_bad[0]:.3f} (expect < 0.1)")

# ============================================================
# GRPO with Hybrid Reward
# ============================================================
print(f"\n[GRPO] Loading {SFT_MODEL}, 200 prompts, 2 epochs...")
prompts = []
with open("data/aipc_sft_train.jsonl") as f:
    for line in f:
        item = json.loads(line)
        q = item.get("question") or item.get("prompt", "")
        if q: prompts.append({"prompt": q})
prompts = prompts[:200]
dataset = Dataset.from_list(prompts)

tokenizer = AutoTokenizer.from_pretrained(SFT_MODEL)
if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(SFT_MODEL, torch_dtype=torch.bfloat16, device_map="auto")

config = GRPOConfig(
    output_dir=GRPO_OUTPUT, num_train_epochs=2,
    per_device_train_batch_size=4, gradient_accumulation_steps=4,
    learning_rate=1e-6, max_completion_length=256, num_generations=4,
    temperature=0.8, logging_steps=5, save_strategy="no",
    bf16=True, remove_unused_columns=False, report_to="none",
)

trainer = GRPOTrainer(model=model, args=config, train_dataset=dataset,
                      processing_class=tokenizer, reward_funcs=hybrid_reward)

print("  Starting GRPO (hybrid reward, 2 epochs)...")
t0 = time.time()
trainer.train()
print(f"  GRPO done in {time.time()-t0:.0f}s")
trainer.save_model(GRPO_OUTPUT)
tokenizer.save_pretrained(GRPO_OUTPUT)
del model, trainer; torch.cuda.empty_cache()

# ============================================================
# DPO Chain
# ============================================================
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
    cfg = DPOConfig(output_dir=model_out, beta=0.1, learning_rate=5e-7,
        per_device_train_batch_size=2, gradient_accumulation_steps=2,
        num_train_epochs=3, logging_steps=1, save_strategy="no",
        bf16=True, remove_unused_columns=False, report_to="none",
        max_length=2048, max_prompt_length=1024)
    t = DPOTrainer(model=m, ref_model=None, args=cfg, train_dataset=ds, processing_class=tok)
    t.train(); t.save_model(model_out); tok.save_pretrained(model_out)
    print(f"  {stage} done")
    del m, t; torch.cuda.empty_cache()

# ============================================================
# Evaluation: Base vs V1.4 (GPT-5.2 scoring)
# ============================================================
print("\n" + "=" * 70)
print("[Eval] Base vs V1.4 - GPT-5.2 scoring")
print("=" * 70)

test_qs = [
    "What is an AI PC and how does it differ from a regular laptop?",
    "How can I deploy a 7B language model on a local AI PC?",
    "My VPN connection keeps dropping. How do I troubleshoot?",
    "What are the benefits of NPU over GPU for AI inference?",
    "How to check if Intel Core Ultra NPU is being utilized?",
    "I cannot install the latest Windows update. What should I do?",
    "How to reset a user password in Active Directory?",
    "What causes high CPU usage and how to diagnose it?",
]

def gen(mp, q):
    tk = AutoTokenizer.from_pretrained(mp)
    md = AutoModelForCausalLM.from_pretrained(mp, torch_dtype=torch.bfloat16, device_map="auto")
    ids = tk.apply_chat_template([{"role":"user","content":q}], return_tensors="pt", add_generation_prompt=True).to(md.device)
    out = md.generate(ids, max_new_tokens=300, temperature=0.6, do_sample=True)
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

print(f"\n{'Question':<55} {'Base':>5} {'V1.4':>5}")
print("-" * 68)
bs, vs = [], []
for q in test_qs:
    br = gen("/root/Llama-3.2-3B-Instruct", q)
    vr = gen("checkpoints/aipc_dpo_v1.4", q)
    b = score(q, br); v = score(q, vr)
    bs.append(b); vs.append(v)
    print(f"{q[:53]:<55} {b:>4}/10 {v:>4}/10")
    time.sleep(0.5)
print("-" * 68)
ab = sum(bs)/len(bs); av = sum(vs)/len(vs)
print(f"{'AVERAGE':<55} {ab:>4.1f}/10 {av:>4.1f}/10")
imp = ((av-ab)/ab*100) if ab>0 else 0
print(f"\nImprovement: {imp:+.1f}%")
print("\n=== L5 PIPELINE COMPLETE ===")
