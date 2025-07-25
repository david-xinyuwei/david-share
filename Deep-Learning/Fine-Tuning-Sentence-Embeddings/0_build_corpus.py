# 0_build_corpus.py  (fast version)
# ------------------------------------------------------------
# 生成评测 / RAG 的候选库 corpus.jsonl
#   • 把 test 正样本 102 条放入语料
#   • 负样本一次性去重后再随机采样
# ------------------------------------------------------------
import random, json, argparse
from tqdm import tqdm                     # 用于进度条
from datasets import load_dataset

parser = argparse.ArgumentParser()
parser.add_argument("--size", type=int, default=3000,
                    help="目标语料库大小(含正样本)，默认 3000")
parser.add_argument("--outfile", default="corpus.jsonl",
                    help="输出文件名")
args = parser.parse_args()

# ---------- 1. 读取数据 ----------
ds = load_dataset("shawhin/ai-job-embedding-finetuning")

test_pos = list(ds["test"]["job_description_pos"])          # 102 条
neg_pool = (
    list(ds["train"]["job_description_neg"]) +
    list(ds["validation"]["job_description_neg"])
)

# ---------- 2. 对负样本去重 ----------
unique_neg = list(set(neg_pool) - set(test_pos))            # 去除与正样本重复
random.seed(42)
random.shuffle(unique_neg)

need_neg = max(0, args.size - len(test_pos))                # 需要多少负样本
if need_neg > len(unique_neg):
    raise ValueError(
        f"可用独特负样本只有 {len(unique_neg)} 条，不足以凑到 {args.size} 条。"
        " 请选择更小 --size 或扩充负样本池。"
    )

selected_neg = unique_neg[:need_neg]

# ---------- 3. 组合并随机打散 ----------
corpus = test_pos + selected_neg
random.shuffle(corpus)

# ---------- 4. 写出文件 ----------
with open(args.outfile, "w", encoding="utf-8") as f:
    for doc in tqdm(corpus, desc="writing"):
        json.dump({"text": doc}, f, ensure_ascii=False)
        f.write("\n")

print(f"\n✅ Corpus written to {args.outfile} · size = {len(corpus)}")
