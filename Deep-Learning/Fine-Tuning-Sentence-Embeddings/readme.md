# Fine-Tuning a Sentence Embeddings Model for Domain-Specific RAG

\Semantic retrieval is the backbone of modern Retrieval-Augmented Generation (RAG) and search systems. While generic embedding models such as `all-mpnet-base-v2` and `text-embedding-3` are effective for many open-domain tasks, they often fall short when deployed in narrow, domain-specific scenarios. This results in:

- **Noisy Top-k recalls:** Unrelated documents frequently appear amongst the top search results.
- **Wasted LLM tokens:** Large Language Models need to process poorly filtered context, increasing compute cost and often generating off-topic or imprecise answers.

This repository presents a fully reproducible pipeline for **fine-tuning sentence (bi-encoder) embeddings** on your domain data, using the example of AI job search. We demonstrate how domain adaptation (via contrastive learning) lifts recall and downstream answer accuracy, and provide scripts to quantitatively and qualitatively compare performance—both before and after fine-tuning.

------

## Why Fine-Tune Embeddings?

Modern search and RAG pipelines consist of three main modules:

1. **Embedding/Recall**
   Transforms queries and documents into dense vectors, capturing semantic similarity.
2. **Candidate Selection/ANN Search**
   Quickly retrieves Top-k candidates using approximate nearest neighbor search (e.g. FAISS, Redis, Milvus, pgvector).
3. **LLM (Re-Rank/Generate)**
   Reads retrieved passages and generates a final answer.

If your embedding model is not tailored to your domain's jargon and intent, step 1 often fails:

- Related but irrelevant documents are recalled (“semantic ≠ functional” similarity)
- Critical domain-specific matches (e.g., special skills, acronyms) are missed

**Solution:**
Fine-tune the embedding model using contrastive learning, so that positive query-document pairs are mapped close together, and negatives are pushed far apart according to your domain's logic.

------

## Features of this Repository

- **End-to-end scripts:** Full CLI workflow from data prep → model training → corpus build → retrieval evaluation → RAG chatbot comparison → quantitative CSV report.
- **Ready-to-run:** All scripts are self-contained; environment and dependencies are fully reproducible.
- **Working on real-world (recruitment/job search) data:** Easily adapted for other fields (customer support, legal, medical, e-commerce, etc.)
- **Both metrics and interpretability:** Gives you not only recall numbers (Hit@K, MRR), but also per-query inspection of which documents were retrieved, and side-by-side LLM outputs.
- **Scalable corpus evaluation:** Test search robustness not just on toy data, but on larger candidate pools (800–10,000+ docs, depending on your data).
- **Supports both GPU and CPU environments**

------

## Pipeline Overview

```
Data Preparation                   Training                         Evaluation
     ┌───────────────────────────┐   ┌─────────────────────────────┐   ┌──────────────────────────────┐
     │  Training Triplets:       │   │  Fine-tune with             │   │  Build large candidate       │
     │  (query, positive, neg)   │──▶│  MultipleNegativesRanking   │──▶│  corpus (corpus.jsonl)       │
     └───────────────────────────┘   └─────────────────────────────┘   └───────┬──────────────────────┘
                                                                                        │
                                                                                    Retrieval + RAG
                                                           ┌───────────────────────────┴────────────────────────┐
                                                           │   Offline metrics (Hit@K, MRR),                   │
                                                           │   Batch CSV/report for every query,               │
                                                           │   Per-query document / answer comparison          │
                                                           └───────────────────────────────────────────────────┘
```



------

## Quick Start

1. **Clone & create environment**

   ```
   conda create -n rag_demo python=3.11 -y
   conda activate rag_demo
   pip install -r requirements.txt
   ```

   

2. **Fine-tune the embedding model**

   ```
   python 1_train_embedding.py \
     --base_model sentence-transformers/all-distilroberta-v1 \
     --epochs 5 --bsz 8
   ```

   

3. **Build candidate corpus**

   ```
   python 0_build_corpus.py --size 800
   # (Or scale up, e.g. --size 3000 if you have more negatives)
   ```

   

4. **Compute and compare retrieval metrics**

   ```
   python 2_eval_retrieval.py
   # See performance jump: Hit@10, MRR@10, etc.
   ```

   

5. **Batch report for all queries**

   ```
   3-rag_batch_eval.py
   ```
   
   ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Sentence-Embeddings/images/1.png)

------

## Results: Why Fine-Tuning Pays Off

**On a 800-doc open-domain candidate pool:**

| Metric | Baseline | Finetuned | Δ      |
| ------ | -------- | --------- | ------ |
| Hit@1  | 0.275    | **0.598** | +32 pp |
| Hit@3  | 0.392    | **0.775** | +38 pp |
| Hit@10 | 0.529    | **0.892** | +36 pp |
| MRR@10 | 0.351    | **0.694** | +0.34  |

- **Before fine-tuning:** LLM answers often diluted, Top-3 candidates may all be off-topic; correct JDs are buried or missed.
- **After fine-tuning:** Correct JD nearly always top-ranked; answers are precise, relevant, and token-efficient.

The side-by-side CSV (rag_compare_report.csv) makes it trivial to spot for any reviewer where fine-tuning fixed previous failure points.

------

## File/Script Structure

```
.
├─ 0_build_corpus.py           # Supervised contrastive fine-tuning
├─ 1_train_embedding.py        # Fast corpus build (no repeat, flexible size)
├─ 2_eval_retrieval.py         # Quantitative recall metrics
├─ 3-rag_batch_eval.py         # Single-query RAG chatbot demo
├─ corpus.jsonl                # Document pool for retrieval
├─ runs/finetuned/final/       # Output directory for fine-tuned model
└─ rag_compare_report.csv      # Per-query side-by-side CSV results
```



------

## Customization

- **Your data:**
  Replace the training triplets with your business's (query, positive, negative) pairs—customer support, legal QA, code search, etc.
- **Model choice:**
  Swap in any Huggingface-compatible dual-encoder encoder; supports base/larger models (e.g. e5-base, bge-large).
- **Corpus size:**
  Adjust via `0_build_corpus.py --size N` for realistic-scale simulation.
- **Evaluation:**
  Extend batch evaluation to include real-world queries/logs, or integrate with downstream LLM APIs (OpenAI, Azure, etc.)

------

## Acknowledgements

- [sentence-transformers](https://www.sbert.net/)
- [HuggingFace Datasets](https://huggingface.co/datasets)
- [datastax/linkedin_job_listings](https://huggingface.co/datasets/datastax/linkedin_job_listings)
- Inspired by best practices in industry RAG, enterprise search, and open-source LLM research.

------

## Who is this for?

- MLEs, search/NLP engineers who need easily-repeatable fine-tuning & evidence
- Business/product stakeholders: Not only can you "see the numbers", but also audit per-query improvements query-by-query
- Anyone interested in RAG/semantic search with strong practical guarantees

------

**Happy fine-tuning!** 🚀
PRs, issues, and suggestions welcome.