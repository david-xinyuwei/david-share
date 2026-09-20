"""Measure the text judge's own error floor before trusting it to score text rendering.

The judge is a vision model, so its error rate is part of every number the study produces. This
renders each target string with a real font on a plain background, asks the judge to read it back,
and scores the reading with the study's own rule (imported from score_text_rendering, so the two
cannot drift apart). Whatever the judge misses here is measurement error, not image-model error.

Boundary: a clean horizontal render establishes that the judge can read the characters. It does
not establish that it reads them inside a generated scene, so the study's scores may understate
the image models but will not overstate them.

Credentials come from the environment exactly as for the scorer:
  JUDGE_ENDPOINT, JUDGE_DEPLOYMENT, AZURE_OPENAI_API_KEY

`--check` rescores an archived calibration.json from its saved transcriptions and calls no model.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_text_rendering import (READ_INSTRUCTION, SCORING_RULE, judge_from_environment,  # noqa: E402
                                  score, transcribe)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def render(text_lines, font_path, path):
    """Black text centred on a 1024x1024 white canvas, shrunk until the longest line fits."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    margin, size = 60, 72
    while size > 12:
        font = ImageFont.truetype(font_path, size)
        widest = max(draw.textbbox((0, 0), line, font=font)[2] for line in text_lines)
        if widest <= 1024 - 2 * margin:
            break
        size -= 4
    line_height = int(size * 1.5)
    y = (1024 - line_height * len(text_lines)) // 2
    for line in text_lines:
        width = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((1024 - width) / 2, y), line, fill="black", font=font)
        y += line_height
    image.save(path)


def summarize(records):
    totals = {}
    for record in records:
        bucket = totals.setdefault(record["language"], [0, 0, 0, 0])
        bucket[0] += record["matched"]
        bucket[1] += record["chars"]
        bucket[2] += record["exact_segments"]
        bucket[3] += record["segments"]
    return {language: {"matched_chars": m, "total_chars": c, "char_accuracy": round(m / c, 4),
                       "exact_segments": e, "total_segments": s, "exact_rate": round(e / s, 4)}
            for language, (m, c, e, s) in sorted(totals.items())}


def read_prompts(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        return [row for row in reader if row and row[0].strip()]


def check(calibration_path):
    data = json.loads(calibration_path.read_text(encoding="utf-8"))
    mismatches = []
    rescored = []
    for record in data["records"]:
        fresh = score(record["target"].split("|"), record["transcription"])
        keys = ("matched", "chars", "exact_segments", "segments")
        if tuple(fresh[k] for k in keys) != tuple(record[k] for k in keys):
            mismatches.append(f"{record['pair_id']} {record['language']}")
        rescored.append({**record, **{k: fresh[k] for k in keys}})
    if summarize(rescored) != data["summary"]:
        mismatches.append("summary does not reproduce from the records")
    if data.get("scoring_rule") != SCORING_RULE:
        mismatches.append("stored scoring_rule is not the rule this script implements")
    print(json.dumps({"validation": "PASS" if not mismatches else "FAIL", "records": len(data["records"]),
                      "summary": data["summary"], "mismatches": mismatches}, ensure_ascii=False))
    return 0 if not mismatches else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate the text judge on cleanly rendered targets.")
    parser.add_argument("--prompts", type=Path, help="The study's prompt CSV (target strings in column 4).")
    parser.add_argument("--out", type=Path, help="Directory for the renders and calibration.json.")
    parser.add_argument("--font", default="C:/Windows/Fonts/msyh.ttc",
                        help="TrueType font covering both scripts; the default is Microsoft YaHei.")
    parser.add_argument("--check", type=Path, metavar="CALIBRATION_JSON",
                        help="Rescore an archived calibration from its saved transcriptions; no model calls.")
    arguments = parser.parse_args()
    if arguments.check:
        return check(arguments.check.resolve())
    if not (arguments.prompts and arguments.out):
        parser.error("--prompts and --out are required unless --check is given")

    endpoint, deployment, key = judge_from_environment()
    out = arguments.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for row in read_prompts(arguments.prompts):
        pair_id, language, target = row[1], row[2], row[3]
        image = out / f"{pair_id}-{language}.png"
        render(target.split("|"), arguments.font, image)
        transcription = transcribe(endpoint, deployment, key, image.read_bytes())
        result = score(target.split("|"), transcription)
        records.append({"pair_id": pair_id, "language": language, "target": target, "image": image.name,
                        "transcription": transcription,
                        **{k: result[k] for k in ("chars", "matched", "segments", "exact_segments")}})
        flag = "" if result["matched"] == result["chars"] else "   <-- judge error"
        print(f"{pair_id} {language}: {result['matched']}/{result['chars']} chars{flag}")
        if flag:
            print(f"     target : {target}\n     read   : {transcription!r}")
    summary = summarize(records)
    (out / "calibration.json").write_text(json.dumps(
        {"judge": deployment, "font": Path(arguments.font).name, "instruction": READ_INSTRUCTION,
         "scoring_rule": SCORING_RULE, "prompts": arguments.prompts.name, "summary": summary,
         "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nJudge accuracy on cleanly rendered text (the measurement floor):")
    for language, s in summary.items():
        print(f"  {language}: {s['matched_chars']}/{s['total_chars']} = {s['char_accuracy']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
