#!/usr/bin/env python3
"""
E2 v2: Fashionpedia → Qwen-VL SFT (NO category hint in prompt, semantic class names).

Key fixes vs v1:
  1. Removed `Category hint: <id>` from the user prompt — model must infer from image.
  2. Use semantic Fashionpedia class names (shirt, dress, jacket, ...) instead of integer ids.
  3. main_category = the largest-area "garment" class (shirt/dress/jacket/...).
  4. style_tags = other garment classes present in the image (multi-label).
  5. detail_tags = accessory/detail classes present (sleeve/pocket/zipper/...).
"""
import argparse
import json
import os
import random
from collections import Counter
from pathlib import Path

from datasets import load_dataset
from PIL import Image

# Fashionpedia 46 classes (verified 2026-05-12 via dataset.features)
FASHIONPEDIA_CLASSES = [
    'shirt, blouse', 'top, t-shirt, sweatshirt', 'sweater', 'cardigan',
    'jacket', 'vest', 'pants', 'shorts', 'skirt', 'coat', 'dress', 'jumpsuit',
    'cape', 'glasses', 'hat', 'headband, head covering, hair accessory', 'tie',
    'glove', 'watch', 'belt', 'leg warmer', 'tights, stockings', 'sock', 'shoe',
    'bag, wallet', 'scarf', 'umbrella',
    'hood', 'collar', 'lapel', 'epaulette', 'sleeve', 'pocket', 'neckline',
    'buckle', 'zipper', 'applique', 'bead', 'bow', 'flower', 'fringe',
    'ribbon', 'rivet', 'ruffle', 'sequin', 'tassel'
]

# Garment categories (top-level products) vs detail/accessory categories
GARMENT_IDS = set(range(0, 27))    # shirt..umbrella  → main category candidates
DETAIL_IDS = set(range(27, 46))    # hood..tassel    → detail tags

def short_name(idx: int) -> str:
    """Return canonical short single-token name for tag output."""
    raw = FASHIONPEDIA_CLASSES[idx]
    return raw.split(',')[0].strip().replace(' ', '_').lower()

SYSTEM_INSTRUCTION = (
    "You are a product content tagger. Look at the product image and return a STRICT JSON "
    "object with these keys ONLY: "
    '"category" (one of: shirt, top, sweater, cardigan, jacket, vest, pants, shorts, '
    "skirt, coat, dress, jumpsuit, cape, glasses, hat, headband, tie, glove, watch, belt, "
    "leg_warmer, tights, sock, shoe, bag, scarf, umbrella), "
    '"detail_tags" (subset of: hood, collar, lapel, epaulette, sleeve, pocket, neckline, '
    "buckle, zipper, applique, bead, bow, flower, fringe, ribbon, rivet, ruffle, sequin, "
    'tassel), "co_garments" (other garments visible, may be empty), '
    '"confidence" (0..1). Use lowercase tag values. Output ONLY the JSON, no prose.'
)

USER_PROMPT = (
    "<image>\n"
    "Identify the main fashion product in the image and return the tag JSON now."
)


def build_answer(main_cat_id: int, all_cat_ids: list[int]) -> str:
    main = short_name(main_cat_id)
    co = sorted({short_name(c) for c in all_cat_ids
                 if c in GARMENT_IDS and c != main_cat_id})
    details = sorted({short_name(c) for c in all_cat_ids if c in DETAIL_IDS})
    return json.dumps({
        "category": main,
        "detail_tags": details,
        "co_garments": co,
        "confidence": 0.9,
    }, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-size", type=int, default=200)
    ap.add_argument("--val-size", type=int, default=50)
    ap.add_argument("--image-root", default="./data/fashionpedia_v2/images")
    ap.add_argument("--out-dir", default="./data/fashionpedia_v2")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    Path(args.image_root).mkdir(parents=True, exist_ok=True)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    print("Loading Fashionpedia (streaming)...")
    ds_train = load_dataset("detection-datasets/fashionpedia", split="train", streaming=True)
    ds_val = load_dataset("detection-datasets/fashionpedia", split="val", streaming=True)

    def convert(stream, n, prefix):
        out_records = []
        kept = 0
        skipped_no_garment = 0
        for ex in stream:
            if kept >= n:
                break
            img = ex.get("image")
            objects = ex.get("objects", {})
            cats = objects.get("category", [])
            areas = objects.get("area", [])
            if img is None or not cats or not areas:
                continue
            # Filter to garment categories only for "main"
            garment_idx = [i for i, c in enumerate(cats) if c in GARMENT_IDS]
            if not garment_idx:
                skipped_no_garment += 1
                continue
            # main = largest-area garment
            main_i = max(garment_idx, key=lambda k: areas[k])
            main_cat_id = int(cats[main_i])
            all_cat_ids = [int(c) for c in cats]

            img_name = f"{prefix}_{kept:05d}.jpg"
            img_path = Path(args.image_root) / img_name
            try:
                if isinstance(img, Image.Image):
                    img.convert("RGB").save(img_path, format="JPEG", quality=85)
                else:
                    continue
            except Exception as e:
                print(f"  skip: {e}")
                continue

            ans = build_answer(main_cat_id, all_cat_ids)
            rec = {
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": USER_PROMPT},
                    {"role": "assistant", "content": ans},
                ],
                "images": [str(img_path)],
            }
            out_records.append(rec)
            kept += 1
            if kept % 20 == 0:
                print(f"  {prefix}: {kept}/{n}")
        print(f"  skipped (no garment): {skipped_no_garment}")
        return out_records

    train = convert(ds_train, args.train_size, "train")
    val = convert(ds_val, args.val_size, "val")

    train_p = Path(args.out_dir) / "fashionpedia_v2_train.json"
    val_p = Path(args.out_dir) / "fashionpedia_v2_val.json"
    train_p.write_text(json.dumps(train, ensure_ascii=False, indent=2))
    val_p.write_text(json.dumps(val, ensure_ascii=False, indent=2))

    print(f"\n✅ Train: {len(train)} → {train_p}")
    print(f"✅ Val:   {len(val)} → {val_p}")

    # Stats
    cats = Counter()
    detail_lens = []
    co_lens = []
    for r in train:
        try:
            obj = json.loads(r["messages"][-1]["content"])
            cats[obj["category"]] += 1
            detail_lens.append(len(obj["detail_tags"]))
            co_lens.append(len(obj["co_garments"]))
        except Exception:
            pass
    print("\nTop-10 main categories (train):")
    for c, n in cats.most_common(10):
        print(f"  {c}: {n}")
    print(f"\navg detail_tags per sample: {sum(detail_lens)/max(1,len(detail_lens)):.2f}")
    print(f"avg co_garments per sample: {sum(co_lens)/max(1,len(co_lens)):.2f}")


if __name__ == "__main__":
    main()
