"""Score instruction adherence per configuration from the recorded observations.

The visual review deliberately produces no aesthetic score: it is unblinded, so a
preference number from it would not be defensible. But "who did better" can still
be answered on a checkable basis, because ten of the eleven frozen prompts request
no text in the image at all. Rendering signage, slogans or brand names in those
scenarios is therefore a deviation from the instruction, not a matter of taste.

This module counts three deviation classes that any reader can re-check against
the published PNGs and the recorded observations:

  * missing image - the configuration returned no image for a planned sample;
  * unrequested text - the observation records text, signage or a slogan for a
    prompt whose text does not ask for any;
  * cropped subject - the observation records the subject clipped by the frame.

The result is an adherence rate over checkable items, not a quality ranking. A
model can adhere perfectly and still produce the less appealing picture, so the
side-by-side images remain the only basis for aesthetic judgement.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_paired_run import GROUPS

# Words that make in-image text a legitimate part of the request.
TEXT_REQUEST_WORDS = ("text", "word", "label", "sign", "signage", "title", "caption",
                      "letter", "typography", "poster", "logo", "brand", "writing",
                      "banner", "album", "slogan")
# "texture" contains "text"; require a word boundary that is not part of a longer word.
TEXT_REQUEST_PATTERN = re.compile(
    r"\b(" + "|".join(TEXT_REQUEST_WORDS) + r")(s|ing|ed)?\b", re.IGNORECASE)

DEVIATION_MARKERS = {
    "unrequested_text": {
        "zh": ("未请求", "额外文字", "额外英文", "增加英文", "添加英文", "标语", "徽标", "品牌"),
        "en": ("unrequested", "extra text", "extra english", "added text", "slogan",
               "brand", "logo", "wordmark"),
    },
    "cropped_subject": {
        "zh": ("裁切", "截断", "被裁"),
        "en": ("crop", "clipp", "truncat", "cut off"),
    },
}


def prompt_requests_text(prompt):
    return bool(TEXT_REQUEST_PATTERN.search(prompt))


def load_prompts(root):
    with (root / "prompts.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        field = reader.fieldnames[0]
        return [" ".join(row[field].split()) for row in reader
                if row[field] and row[field].strip()]


def score(root, archive):
    root, archive = Path(root), Path(archive)
    prompts = load_prompts(root)
    summary = json.loads((archive / "summary.json").read_text("utf-8"))
    quality = json.loads((archive / "quality-review.json").read_text("utf-8"))
    if quality.get("result_sha256") != summary["result_sha256"]:
        raise SystemExit("Visual review does not belong to this measured run")
    if len(prompts) != len(quality["per_prompt"]):
        raise SystemExit("Prompt count and reviewed scenario count differ")

    text_free = [index for index, prompt in enumerate(prompts, 1)
                 if not prompt_requests_text(prompt)]
    per_group = {}
    for group, metrics in zip(GROUPS, summary["groups"]):
        deviations = {"missing_image": metrics["failed_samples"],
                      "unrequested_text": 0, "cropped_subject": 0}
        detail = {"unrequested_text": [], "cropped_subject": []}
        for item in quality["per_prompt"]:
            index = item["prompt_index"]
            observations = item["observations"][group]
            blob = " ".join(observations[lang].lower() for lang in ("en", "zh"))
            for name, markers in DEVIATION_MARKERS.items():
                if name == "unrequested_text" and index not in text_free:
                    continue
                terms = markers["zh"] + markers["en"]
                if any(term.lower() in blob for term in terms):
                    deviations[name] += 1
                    detail[name].append(index)
        # Checkable items: one image-return check per planned sample, plus one
        # text check per text-free scenario and one crop check per scenario.
        checks = metrics["planned_samples"] + len(text_free) + len(quality["per_prompt"])
        total = sum(deviations.values())
        per_group[group] = {
            "planned_samples": metrics["planned_samples"],
            "checkable_items": checks,
            "deviations": deviations,
            "deviation_total": total,
            "adherence_rate": round((checks - total) / checks, 4),
            "scenarios": detail,
        }
    return {
        "run_id": summary["run_id"],
        "result_sha256": summary["result_sha256"],
        "scenarios_reviewed": len(quality["per_prompt"]),
        "text_free_scenarios": text_free,
        "method": ("Deviation counting against the frozen prompts. Ten of eleven prompts "
                   "request no in-image text, so rendered signage in those scenarios is a "
                   "deviation from the instruction. Counts are derived from the recorded "
                   "observation wording, which is an unblinded review."),
        "boundary": ("An adherence rate is not an aesthetic score and not a benchmark "
                     "result. It measures how often a configuration departed from what the "
                     "prompt asked for, over items a reader can re-check against the "
                     "published images. Higher adherence does not mean the more appealing "
                     "image, and a single run does not establish a model-level rate."),
        "per_group": per_group,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = score(root, arguments.archive)
    if arguments.check:
        ok = all(0.0 <= item["adherence_rate"] <= 1.0 for item in result["per_group"].values())
        print(json.dumps({"status": "PASS" if ok else "FAIL",
                          "groups": len(result["per_group"])}, ensure_ascii=False))
        return 0 if ok else 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
