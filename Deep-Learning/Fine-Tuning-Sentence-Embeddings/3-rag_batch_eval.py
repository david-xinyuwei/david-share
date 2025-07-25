# full_rag_report.py
# ------------------------------------------------------------
# 批量比较 Baseline vs Finetuned 的 RAG 表现并生成单一 CSV
# ------------------------------------------------------------
import json, csv, faiss, textwrap, numpy as np, torch
from tqdm import tqdm
from datasets import load_dataset
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI

# ---------- 基本配置 ----------
CORPUS_FILE      = "corpus.jsonl"                  # 800 条候选库
BASE_MODEL_PATH  = "sentence-transformers/all-distilroberta-v1"
FINE_MODEL_PATH  = "runs/finetuned/final"
TOP_K            = 10
OUT_CSV          = "rag_compare_report.csv"
WRITE_LLM        = False                           # 若需对比回答设为 True

# ---------- Azure OpenAI（仅在 WRITE_LLM=True 时使用） ----------
client = AzureOpenAI(
    api_key        = "*ME",
    azure_endpoint = "https://ai-hubeastus956138673159.openai.azure.com",
    api_version    = "2024-12-01-preview",
)
DEPLOY = "gpt-4.1"

# ---------- 加载数据 ----------
corpus_texts = [json.loads(l)["text"] for l in open(CORPUS_FILE)]
ds_test      = load_dataset("shawhin/ai-job-embedding-finetuning", split="test")
queries      = list(ds_test["query"])
golds        = list(ds_test["job_description_pos"])
N            = len(queries)

def build_index(model: SentenceTransformer):
    emb = model.encode(corpus_texts, normalize_embeddings=True,
                       convert_to_numpy=True, batch_size=128, show_progress_bar=False)
    idx = faiss.IndexFlatIP(emb.shape[1])
    idx.add(emb)
    return idx

def evaluate(model_path):
    model = SentenceTransformer(model_path,
                                device="cuda" if torch.cuda.is_available() else "cpu")
    index = build_index(model)
    ranks, sims_all, top3_snips, answers = [], [], [], []

    for q in queries:
        q_vec = model.encode(q, normalize_embeddings=True)
        sims, I = index.search(q_vec.reshape(1, -1), TOP_K)
        retrieved = [corpus_texts[i] for i in I[0]]

        # 记录排名 / 相似度
        if golds[len(ranks)] in retrieved:
            r = retrieved.index(golds[len(ranks)]) + 1
            sim_val = sims[0][r-1]
        else:
            r = 0
            sim_val = ""
        ranks.append(r)
        sims_all.append(sim_val)

        # Top-3 摘要
        snips = [textwrap.shorten(d.replace("\n"," "), 100) for d in retrieved[:3]]
        top3_snips.append(snips)

        # （可选）生成回答
        if WRITE_LLM:
            prompt = (
                "You are an HR assistant.\n\nQUESTION:\n" + q +
                "\n\nREFERENCE JOB DESCRIPTIONS:\n" +
                "\n\n---\n\n".join(retrieved[:3]) +
                "\n\nAnswer the question using ONLY the reference descriptions."
            )
            ans = client.chat.completions.create(
                    model=DEPLOY,
                    messages=[{"role":"user","content":prompt}],
                    temperature=0.2
                  ).choices[0].message.content
            answers.append(textwrap.shorten(ans.replace("\n"," "), 200))
        else:
            answers.append("")

    # 统计指标
    hit1  = sum(1 for r in ranks if r == 1) / N
    hit3  = sum(1 for r in ranks if 0 < r <= 3) / N
    hit10 = sum(1 for r in ranks if 0 < r <= 10) / N
    mrr   = sum(1 / r for r in ranks if r) / N
    metrics = (hit1, hit3, hit10, mrr)

    return metrics, ranks, sims_all, top3_snips, answers

# ---------- 评估两套模型 ----------
metrics_base, rank_b, sim_b, snip_b, ans_b = evaluate(BASE_MODEL_PATH)
metrics_fine, rank_f, sim_f, snip_f, ans_f = evaluate(FINE_MODEL_PATH)

# ---------- 写入 CSV ----------
header = [
    "query",
    "baseline_rank", "baseline_cosine",
    "finetuned_rank", "finetuned_cosine",
    "baseline_snip1", "baseline_snip2", "baseline_snip3",
    "finetuned_snip1", "finetuned_snip2", "finetuned_snip3"
]
if WRITE_LLM:
    header += ["baseline_answer", "finetuned_answer"]

with open(OUT_CSV, "w", newline='', encoding="utf-8") as f:
    w = csv.writer(f)
    # 在文件最顶部写两行总体指标
    w.writerow(["Metric", "Baseline", "Finetuned"])
    for name, b, ft in zip(["Hit@1", "Hit@3", "Hit@10", "MRR@10"],
                           metrics_base, metrics_fine):
        w.writerow([name, f"{b:.3f}", f"{ft:.3f}"])
    w.writerow([])          # 空行分隔
    w.writerow(header)

    for q, rb, rf, sb, sf, snb, snf, ab, af in zip(
            queries, rank_b, rank_f, sim_b, sim_f, snip_b, snip_f, ans_b, ans_f):
        row = [
            q,
            rb, sb,
            rf, sf,
            *snb, *snf
        ]
        if WRITE_LLM:
            row += [ab, af]
        w.writerow(row)

print("✅ Report written to", OUT_CSV)
print("\nOverall Metrics")
print(f"  Hit@1  : {metrics_base[0]:.3f}  →  {metrics_fine[0]:.3f}")
print(f"  Hit@3  : {metrics_base[1]:.3f}  →  {metrics_fine[1]:.3f}")
print(f"  Hit@10 : {metrics_base[2]:.3f}  →  {metrics_fine[2]:.3f}")
print(f"  MRR@10 : {metrics_base[3]:.3f}  →  {metrics_fine[3]:.3f}")
