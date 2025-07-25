# 2_eval_retrieval_compare.py
# ------------------------------------------------------------
# 统计 Baseline vs Finetuned 在 Top-10 上的 Hit 和 MRR
# ------------------------------------------------------------
import json, numpy as np, torch, faiss
from sentence_transformers import SentenceTransformer, util
from datasets import load_dataset

QUERY_SET = "test"                        # 用原测试集 102 条 query
K         = 10
BASE_MODEL_NAME  = "sentence-transformers/all-distilroberta-v1"
FINETUNED_DIR    = "runs/finetuned/final"

# ---------- 1. 读取查询 & 正确答案 ----------
ds  = load_dataset("shawhin/ai-job-embedding-finetuning", split=QUERY_SET)
queries = list(ds["query"])
gold    = list(ds["job_description_pos"])             # ground-truth

# ---------- 2. 读取候选文档（3k 条） ----------
corpus_texts = [json.loads(l)["text"] for l in open("corpus.jsonl")]

def evaluate(model_name, tag):
    print(f"\n----- {tag} -----")
    model = SentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")

    # 2.1 预编码 corpus
    corpus_emb = model.encode(
        corpus_texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=128
    )
    index = faiss.IndexFlatIP(corpus_emb.shape[1])
    index.add(corpus_emb)

    hit, rr = 0, 0
    for q, true_doc in zip(queries, gold):
        q_vec = model.encode(q, normalize_embeddings=True)
        _, I  = index.search(q_vec.reshape(1, -1), K)
        retrieved = [corpus_texts[i] for i in I[0]]

        if true_doc in retrieved:
            hit += 1
            rr  += 1 / (retrieved.index(true_doc) + 1)

    hit_k = hit / len(queries)
    mrr_k = rr  / len(queries)
    print(f"Hit@{K} = {hit_k:.3f}    MRR@{K} = {mrr_k:.3f}")
    return hit_k, mrr_k

evaluate(BASE_MODEL_NAME, "Baseline  (未微调)")
evaluate(FINETUNED_DIR,   "Finetuned (已微调)")
