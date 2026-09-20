"""Score text rendering in completed runs, and build contact sheets for human review.

Two denominators, both fixed by the prompt set and printed with every number:
  - character accuracy: the best-matching window of equal length anywhere in the transcription,
    scored character by character
  - exact segments: the target appears verbatim as a substring, no partial credit

Both ignore whitespace. The judge emits one line per visual text element, so where it breaks a
line reflects layout, not spelling; a phrase the model wrapped onto two lines was still rendered.

The judge is a vision model, not a human. calibrate_text_judge.py measures its floor on cleanly
rendered text; a gap below that floor is attributable to the image model. Contact sheets exist so
every number can be checked by eye.

Credentials, like the runner's, come from the process environment and never from source:
  JUDGE_ENDPOINT      https://<resource>.openai.azure.com
  JUDGE_DEPLOYMENT    a vision-capable chat deployment
  AZURE_OPENAI_API_KEY

`--check` rescores from the transcriptions saved in an existing text-scoring.json and calls no
model at all; it is how the published numbers are verified offline.
"""
import argparse
import base64
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
READ_INSTRUCTION = (
    "Transcribe every piece of text visible in this image, exactly as written. "
    "Preserve the original language and characters. Output one line per distinct text element. "
    "Output only the transcription, with no commentary. If there is no text, output NONE."
)
SCORING_RULE = ("Whitespace-insensitive substring match over the whole transcription. "
                "The judge emits one line per visual text element, so line breaks reflect "
                "layout, not spelling.")


def judge_from_environment():
    endpoint = os.environ.get("JUDGE_ENDPOINT", "").rstrip("/")
    deployment = os.environ.get("JUDGE_DEPLOYMENT", "")
    key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not (endpoint.startswith("https://") and deployment and key):
        raise SystemExit("Set JUDGE_ENDPOINT, JUDGE_DEPLOYMENT and AZURE_OPENAI_API_KEY before scoring.")
    return endpoint, deployment, key


def transcribe(endpoint, deployment, key, image_bytes):
    payload = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": READ_INSTRUCTION},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," +
                                            base64.b64encode(image_bytes).decode("ascii")}}]}]}
    for attempt in range(3):
        try:
            response = requests.post(
                f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2025-04-01-preview",
                headers={"Content-Type": "application/json", "api-key": key}, json=payload, timeout=180)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            if response.status_code != 429 or attempt == 2:
                raise RuntimeError(f"judge HTTP {response.status_code}: {response.text[:200]}")
        except requests.RequestException:
            if attempt == 2:
                raise
    raise RuntimeError("judge unreachable")


def normalize(text):
    return "".join(text.split())


def score(segments, transcription):
    """Per-segment accuracy against the whole transcription, ignoring layout."""
    flat = normalize(transcription)
    total = correct = exact = 0
    detail = []
    for segment in segments:
        target = normalize(segment)
        is_exact = target in flat
        if is_exact:
            matched, window = len(target), segment
        else:
            best_ratio, window = 0.0, ""
            for start in range(max(len(flat) - len(target), 0) + 1):
                candidate = flat[start:start + len(target)]
                ratio = SequenceMatcher(None, target, candidate).ratio()
                if ratio > best_ratio:
                    best_ratio, window = ratio, candidate
            matched = round(best_ratio * len(target))
        total += len(target)
        correct += matched
        exact += 1 if is_exact else 0
        detail.append({"target": segment, "best_match": window, "chars": len(target),
                       "matched": matched, "exact": is_exact})
    return {"chars": total, "matched": correct, "segments": len(segments),
            "exact_segments": exact, "detail": detail}


def summarize(scored):
    by_group = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    for row in scored:
        bucket = by_group[row["group"]][row["language"]]
        bucket[0] += row["matched"]
        bucket[1] += row["chars"]
        bucket[2] += row["exact_segments"]
        bucket[3] += row["segments"]
    summary = {}
    for group in sorted(by_group):
        summary[group] = {}
        for language in ("en", "zh"):
            matched, chars, exact, segments = by_group[group][language]
            if chars:
                summary[group][language] = {
                    "matched_chars": matched, "total_chars": chars, "char_accuracy": round(matched / chars, 4),
                    "exact_segments": exact, "total_segments": segments, "exact_rate": round(exact / segments, 4)}
    return summary


def print_summary(summary):
    print("\n" + "=" * 92)
    print(f"{'group':<30} {'lang':<5} {'char accuracy':>20} {'exact segments':>22}")
    print("=" * 92)
    for group, languages in summary.items():
        for language, s in languages.items():
            print(f"{group:<30} {language:<5} {s['matched_chars']:>6}/{s['total_chars']:<6} = "
                  f"{s['char_accuracy']:>6.1%} {s['exact_segments']:>10}/{s['total_segments']:<6} = "
                  f"{s['exact_rate']:>6.1%}")
        print("-" * 92)


def contact_sheet(rows, runs_by_name, out_path, title, font_path):
    """One sheet per group: every image with its target, what the judge read, and the score."""
    from PIL import Image, ImageDraw, ImageFont
    columns, thumb, pad, caption = 5, 300, 12, 74
    grid_rows = (len(rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (thumb + pad) + pad,
                              grid_rows * (thumb + caption + pad) + pad + 40), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(font_path, 13)
        heading = ImageFont.truetype(font_path, 20)
    except OSError:
        font = heading = ImageFont.load_default()
    draw.text((pad, 10), title, fill="black", font=heading)
    for index, row in enumerate(rows):
        x = pad + (index % columns) * (thumb + pad)
        y = 40 + pad + (index // columns) * (thumb + caption + pad)
        with Image.open(runs_by_name[row["run"]] / row["image"]) as image:
            sheet.paste(image.convert("RGB").resize((thumb, thumb)), (x, y))
        verdict = f"{row['matched']}/{row['chars']} chars, {row['exact_segments']}/{row['segments']} exact"
        draw.text((x, y + thumb + 3), f"{row['pair_id']} {row['language']}  {verdict}", fill="black", font=font)
        draw.text((x, y + thumb + 21), f"want: {row['target'].replace('|', ' / ')}", fill="#333333", font=font)
        draw.text((x, y + thumb + 39), f"read: {row['transcription'].replace(chr(10), ' / ')[:46]}",
                  fill="#777777", font=font)
    sheet.save(out_path)


def check(scoring_path):
    """Rescore every saved transcription and confirm the stored numbers reproduce. No model calls."""
    data = json.loads(scoring_path.read_text(encoding="utf-8"))
    mismatches = []
    rescored = []
    for sample in data["samples"]:
        fresh = score(sample["target"].split("|"), sample["transcription"])
        if (fresh["matched"], fresh["chars"], fresh["exact_segments"], fresh["segments"]) != \
                (sample["matched"], sample["chars"], sample["exact_segments"], sample["segments"]):
            mismatches.append(f"{sample['group']} {sample['pair_id']} {sample['language']} r{sample['round']}")
        rescored.append({**sample, **{k: fresh[k] for k in ("matched", "chars", "exact_segments", "segments")}})
    if summarize(rescored) != data["summary"]:
        mismatches.append("summary table does not reproduce from the samples")
    if data.get("scoring_rule") != SCORING_RULE:
        mismatches.append("stored scoring_rule is not the rule this script implements")
    print(json.dumps({"validation": "PASS" if not mismatches else "FAIL",
                      "samples": len(data["samples"]), "mismatches": mismatches[:20]}, ensure_ascii=False))
    return 0 if not mismatches else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Score text rendering across one or more runs.")
    parser.add_argument("--run", type=Path, action="append",
                        help="A run directory; repeat to merge per-deployment shards.")
    parser.add_argument("--out", type=Path, help="Directory for the merged scores and contact sheets.")
    parser.add_argument("--prompts", type=Path, help="The prompt CSV the runs were frozen with.")
    parser.add_argument("--check", type=Path, metavar="TEXT_SCORING_JSON",
                        help="Rescore an existing text-scoring.json from its saved transcriptions; no model calls.")
    parser.add_argument("--font", default="C:/Windows/Fonts/msyh.ttc",
                        help="TrueType font covering both scripts, for contact-sheet captions.")
    arguments = parser.parse_args()
    if arguments.check:
        return check(arguments.check.resolve())
    if not (arguments.run and arguments.out and arguments.prompts):
        parser.error("--run, --out and --prompts are required unless --check is given")

    runs = [path.resolve() for path in arguments.run]
    out = arguments.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with arguments.prompts.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        prompts = [row for row in reader if row and row[0].strip()]

    # Every shard must have run the identical prompt file, or a prompt index means different
    # scenes in different shards and the merged table compares unlike things.
    digests, rows = set(), []
    for run in runs:
        digests.add(hashlib.sha256((run / "source" / arguments.prompts.name).read_bytes()).hexdigest())
        results = json.loads((run / "5way_v2_results.json").read_text(encoding="utf-8"))
        ok = [row for row in results["raw_data"] if row["ok"]]
        print(f"{run.name}: {len(ok)}/{len(results['raw_data'])} successful")
        rows.extend((run, row) for row in ok)
    if len(digests) != 1:
        raise SystemExit(f"Shards did not run the same prompt file: {sorted(digests)}")
    if hashlib.sha256(arguments.prompts.read_bytes()).hexdigest() not in digests:
        raise SystemExit("Scoring prompt file differs from the frozen prompt file the shards ran")
    print(f"\nscoring {len(rows)} successful samples across {len(runs)} shards\n")

    endpoint, deployment, key = judge_from_environment()
    scored = []
    for index, (run, row) in enumerate(rows, 1):
        _, pair_id, language, target, _, scene = prompts[row["prompt_idx"] - 1][:6]
        transcription = transcribe(endpoint, deployment, key, (run / row["image"]).read_bytes())
        result = score(target.split("|"), transcription)
        scored.append({**{k: row[k] for k in ("group", "round", "prompt_idx", "image", "image_sha256")},
                       "run": run.name, "pair_id": pair_id, "language": language, "target": target,
                       "scene": scene, "transcription": transcription, **result})
        print(f"  [{index}/{len(rows)}] {row['group']:<28} {pair_id} {language} "
              f"{result['matched']}/{result['chars']} chars {result['exact_segments']}/{result['segments']} exact")

    summary = summarize(scored)
    print_summary(summary)
    review = out / "review"
    review.mkdir(exist_ok=True)
    runs_by_name = {run.name: run for run in runs}
    for group in summary:
        group_rows = sorted((r for r in scored if r["group"] == group), key=lambda r: (r["round"], r["prompt_idx"]))
        contact_sheet(group_rows, runs_by_name, review / f"text-{group}.png",
                      f"{group} - text rendering (want / read / score)", arguments.font)
    (out / "text-scoring.json").write_text(json.dumps(
        {"judge": deployment, "instruction": READ_INSTRUCTION, "scoring_rule": SCORING_RULE,
         "runs": [run.name for run in runs], "prompt_sha256": digests.pop(),
         "scored_samples": len(scored), "summary": summary, "samples": scored},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ncontact sheets: {review}\nscores: {out / 'text-scoring.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
