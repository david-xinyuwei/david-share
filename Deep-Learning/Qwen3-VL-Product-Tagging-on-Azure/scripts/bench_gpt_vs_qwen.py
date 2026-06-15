"""Fair benchmark: Azure OpenAI GPT-5.x vs Qwen3-VL on the same image set.

Runs the same product-tagging prompt + image set against:
- Azure OpenAI Responses API models (e.g., gpt-5.4, gpt-5-mini)
- Qwen3-VL (uses pre-computed predictions JSONL for comparison)

All endpoints, keys, model names, and paths are configurable via CLI args / env vars.
No internal infrastructure is hardcoded.

Outputs:
- predictions/<model>.jsonl  per-image latency + tokens + raw text + parsed JSON
- summary.json               aggregated metrics (JSON validity, category accuracy,
                             detail-tag F1, co-garment F1, P50/P95 latency, tokens)

Example:
  python bench_gpt_vs_qwen.py \
      --images-dir ./images \
      --val-json   ./fashionpedia_v2_val.json \
      --endpoint   https://<your-aoai>.openai.azure.com/openai \
      --api-key    "$AZURE_OPENAI_KEY" \
      --models     gpt-5.4 gpt-5-mini \
      --max-images 50 \
      --out-dir    ./bench_out \
      --qwen-predictions ./qwen_t1_predictions.jsonl

Required AOAI deployments: one per `--models` value, accessed via the Responses API
(api-version 2025-04-01-preview or later). Reasoning models (mini/nano) automatically
get `reasoning.effort=minimal` so that output_text is not consumed by reasoning tokens.
"""

import argparse
import base64
import json
import os
import re
import time
from pathlib import Path
from statistics import median

import requests

DEFAULT_API_VERSION = "2025-04-01-preview"

SYSTEM_PROMPT = (
    'You are a product content tagger. Look at the product image and return a STRICT JSON '
    'object with these keys ONLY: "category" (one of: shirt, top, sweater, cardigan, jacket, '
    'vest, pants, shorts, skirt, coat, dress, jumpsuit, cape, glasses, hat, headband, tie, '
    'glove, watch, belt, leg_warmer, tights, sock, shoe, bag, scarf, umbrella), '
    '"detail_tags" (subset of: hood, collar, lapel, epaulette, sleeve, pocket, neckline, '
    'buckle, zipper, applique, bead, bow, flower, fringe, ribbon, rivet, ruffle, sequin, '
    'tassel), "co_garments" (other garments visible, may be empty), "confidence" (0..1). '
    'Use lowercase tag values. Output ONLY the JSON, no prose.'
)
USER_PROMPT = "Identify the main fashion product in the image and return the tag JSON now."


def build_request(model: str, image_b64: str) -> dict:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": USER_PROMPT},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                ],
            },
        ],
        "max_output_tokens": 2048,
    }
    # mini / nano are reasoning models. Without reasoning.effort=minimal, all output
    # tokens are consumed by hidden reasoning_content and output_text is empty.
    # Reference: Azure OpenAI Responses API docs.
    if "mini" in model or "nano" in model:
        body["reasoning"] = {"effort": "minimal"}
    return body


def call_model(endpoint: str, model: str, image_path: Path, api_key: str,
               api_version: str, timeout: int = 120) -> dict:
    url = f"{endpoint.rstrip('/')}/responses?api-version={api_version}"
    img_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    body = build_request(model, img_b64)
    t0 = time.time()
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json", "api-key": api_key},
        json=body,
        timeout=timeout,
    )
    elapsed_ms = int((time.time() - t0) * 1000)
    try:
        j = resp.json()
    except Exception as exc:
        return {"model": model, "status": resp.status_code, "error": str(exc),
                "elapsed_ms": elapsed_ms}
    output_text = ""
    for item in j.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    output_text = c.get("text", "")
    usage = j.get("usage", {})
    return {
        "model": model,
        "status": resp.status_code,
        "elapsed_ms": elapsed_ms,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "output_text": output_text,
    }


def parse_prediction(text: str):
    if not text:
        return None
    match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def f1_set(pred, gold):
    pred_set = {x.lower() for x in (pred or [])}
    gold_set = {x.lower() for x in (gold or [])}
    if not pred_set and not gold_set:
        return 1.0
    if not pred_set or not gold_set:
        return 0.0
    inter = pred_set & gold_set
    if not inter:
        return 0.0
    prec = len(inter) / len(pred_set)
    rec = len(inter) / len(gold_set)
    return 2 * prec * rec / (prec + rec)


def evaluate(predictions, gold_records):
    cat_correct = 0
    detail_f1s, co_f1s, latencies = [], [], []
    in_tok, out_tok = [], []
    valid_json = 0
    for pred_rec, gold in zip(predictions, gold_records):
        latencies.append(pred_rec["elapsed_ms"])
        if pred_rec.get("input_tokens") is not None:
            in_tok.append(pred_rec["input_tokens"])
        if pred_rec.get("output_tokens") is not None:
            out_tok.append(pred_rec["output_tokens"])
        parsed = parse_prediction(pred_rec.get("output_text", ""))
        if parsed is None:
            continue
        valid_json += 1
        if parsed.get("category", "").lower() == gold["category"].lower():
            cat_correct += 1
        detail_f1s.append(f1_set(parsed.get("detail_tags"), gold.get("detail_tags", [])))
        co_f1s.append(f1_set(parsed.get("co_garments"), gold.get("co_garments", [])))
    n = len(predictions)
    return {
        "n": n,
        "json_validity": valid_json / n if n else 0,
        "category_accuracy": cat_correct / n if n else 0,
        "detail_f1_mean": sum(detail_f1s) / len(detail_f1s) if detail_f1s else 0,
        "co_garments_f1_mean": sum(co_f1s) / len(co_f1s) if co_f1s else 0,
        "latency_p50_ms": median(latencies) if latencies else 0,
        "latency_p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
        "input_tokens_mean": sum(in_tok) / len(in_tok) if in_tok else 0,
        "output_tokens_mean": sum(out_tok) / len(out_tok) if out_tok else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Fair GPT vs Qwen3-VL VLM benchmark")
    parser.add_argument("--images-dir", required=True, help="Directory containing val_*.jpg")
    parser.add_argument("--val-json", required=True, help="Gold-label JSON (multimodal conversation format)")
    parser.add_argument("--endpoint", default=os.environ.get("AOAI_ENDPOINT"),
                        help="Azure OpenAI endpoint, e.g. https://<resource>.openai.azure.com/openai")
    parser.add_argument("--api-key", default=os.environ.get("AOAI_KEY"),
                        help="Azure OpenAI api-key (env AOAI_KEY)")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--models", nargs="+", default=["gpt-5.4"],
                        help="AOAI deployment names to benchmark (e.g. gpt-5.4 gpt-5-mini)")
    parser.add_argument("--max-images", type=int, default=50)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--qwen-predictions",
                        help="Optional: JSONL with Qwen predictions ({prediction, latency_ms, input_tokens, output_tokens}) for side-by-side comparison")
    parser.add_argument("--qwen-model-label", default="qwen3vl-8b-fp8-t1",
                        help="Label for the Qwen model row in the summary")
    args = parser.parse_args()

    if not args.endpoint or not args.api_key:
        raise SystemExit("--endpoint and --api-key are required (or set AOAI_ENDPOINT / AOAI_KEY)")

    images_dir = Path(args.images_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_dir = out_dir / "predictions"
    pred_dir.mkdir(exist_ok=True)

    val_records = json.loads(Path(args.val_json).read_text(encoding="utf-8"))[: args.max_images]
    gold_records, image_paths = [], []
    for idx, rec in enumerate(val_records):
        gold_records.append(json.loads(rec["messages"][-1]["content"]))
        image_paths.append(images_dir / f"val_{idx:05d}.jpg")
    print(f"Loaded {len(val_records)} val records")

    summary = {
        "conditions": {
            "n_images": len(val_records),
            "prompt_version": "v1_strict_json",
            "api_version": args.api_version,
        },
        "models": {},
    }

    for model in args.models:
        print(f"\n=== Running {model} on {len(image_paths)} images ===")
        preds = []
        for i, img in enumerate(image_paths):
            if not img.exists():
                print(f"  [{i:02d}] {img.name} MISSING, skipping")
                continue
            res = call_model(args.endpoint, model, img, args.api_key, args.api_version)
            res["sample_id"] = img.stem
            res["image"] = str(img)
            preds.append(res)
            print(f"  [{i:02d}] {img.name} {res['elapsed_ms']}ms status={res['status']} out_tok={res.get('output_tokens')}")
        (pred_dir / f"{model}.jsonl").write_text(
            "\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n",
            encoding="utf-8",
        )
        metrics = evaluate(preds, gold_records[: len(preds)])
        metrics["model"] = model
        summary["models"][model] = metrics

    if args.qwen_predictions:
        qwen_raw = [json.loads(l) for l in Path(args.qwen_predictions).read_text().splitlines() if l.strip()]
        qwen_preds = []
        for i, q in enumerate(qwen_raw[: args.max_images]):
            qwen_preds.append({
                "elapsed_ms": q.get("latency_ms", 0),
                "input_tokens": q.get("input_tokens"),
                "output_tokens": q.get("output_tokens"),
                "output_text": q.get("prediction", ""),
                "sample_id": f"val_{i:05d}",
            })
        (pred_dir / f"{args.qwen_model_label}.jsonl").write_text(
            "\n".join(json.dumps(p, ensure_ascii=False) for p in qwen_preds) + "\n",
            encoding="utf-8",
        )
        m = evaluate(qwen_preds, gold_records[: len(qwen_preds)])
        m["model"] = args.qwen_model_label
        summary["models"][args.qwen_model_label] = m

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== Summary written to {summary_path} ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
