"""Validate the drafter-adaptation experiment: exported files, recomputed summary, README blocks.

Offline only. Reads the exported result files, recomputes ``data/summary.json``
through ``analyze_results.summarize`` and requires equality, checks the README's
generated table blocks against that summary, and verifies every published file
against ``evidence/files.json``.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from analyze_results import digest_file, dump_json, read_json, require, summarize


ROOT = Path(__file__).resolve().parent
MANIFEST = "evidence/files.json"
RULES = "evidence/rule-results.json"
IGNORED_PARTS = {"__pycache__", ".venv", ".pytest_cache"}
READMES = {"README.md": False, "README_CN.md": True}
BLOCK = "ADAPTATION_TABLE"
# Shapes that must never appear in published evidence: IPv4 addresses, UUIDs
# (cloud subscription/tenant identifiers) and absolute home, mount or drive paths.
PRIVATE_SHAPES = (
    re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    re.compile(r"/home/|/mnt/|/root/|[A-Za-z]:\\\\"),
)


def topic_dir(root):
    return root.parent.parent


def markdown_table(headers, rows):
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in [headers, ["---"] * len(headers), *rows])


def interval(entry):
    lower, upper = entry["bootstrap_95_percent_interval"]
    sign = "+" if lower >= 0 else ""
    return f"{sign}{lower:.3f}, {'+' if upper >= 0 else ''}{upper:.3f}"


def adaptation_table(summary, chinese):
    r3, r4 = summary["round3"], summary["round4"]
    zh_sel = r4["agreement_paired"]["chinese_ours_minus_released_selector"]
    en = [r4["agreement_paired"][f"english_v3_seed{seed}_minus_released"] for seed in (0, 1, 2)]
    r4_vllm, r3_vllm = r4["vllm"], r3["vllm"]

    def pct(value):
        return f"{value:.3f}"

    if chinese:
        headers = ["测量", "边界 A：漂移小（英文，LoRA r16 仅注意力）", "边界 B：漂移大（中文，LoRA r128 全模块）"]
        rows = [
            ["目标微调后，官方草稿首位命中（同一份目标文本）",
             f"{en[0]['first_offset_hit_rate']['reference']:.3f}（200 条提示中 193 条可评）",
             f"{zh_sel['first_offset_hit_rate']['reference']:.3f}（基座目标上为 {r4['agreement']['base_zh_released']['first_offset_hit_rate']:.3f}；200 条提示）"],
            ["再训草稿首位命中，及与官方草稿的成对差异（95% 区间）",
             "；".join(f"种子 {seed}：{item['first_offset_hit_rate']['candidate']:.3f}（{interval(item['first_offset_hit_rate'])}）" for seed, item in zip((0, 1, 2), en)),
             f"{zh_sel['first_offset_hit_rate']['candidate']:.3f}（{interval(zh_sel['first_offset_hit_rate'])}）"],
            ["联合前缀接受长度：官方 → 再训（95% 区间）",
             "；".join(f"种子 {seed}：{item['joint_prefix_acceptance_length']['reference']:.2f} → {item['joint_prefix_acceptance_length']['candidate']:.2f}（{interval(item['joint_prefix_acceptance_length'])}）" for seed, item in zip((0, 1, 2), en)),
             f"{zh_sel['joint_prefix_acceptance_length']['reference']:.2f} → {zh_sel['joint_prefix_acceptance_length']['candidate']:.2f}（{interval(zh_sel['joint_prefix_acceptance_length'])}）；基座目标上官方草稿为 {r4['agreement']['base_zh_released']['joint_prefix_acceptance_length']:.2f}"],
            ["vLLM 0.28.0 吞吐（tok/s），并发 1：不开推测 / 官方草稿 / 再训草稿",
             f"{r3_vllm['baseline']['levels']['1']['tokens_per_second']:.1f} / {r3_vllm['dflash_released']['levels']['1']['tokens_per_second']:.1f} / {r3_vllm['dflash_v3']['levels']['1']['tokens_per_second']:.1f}",
             f"{r4_vllm['baseline']['levels']['1']['tokens_per_second']:.1f} / {r4_vllm['dflash_released']['levels']['1']['tokens_per_second']:.1f} / {r4_vllm['dflash_ours']['levels']['1']['tokens_per_second']:.1f}"],
            ["vLLM 0.28.0 吞吐（tok/s），并发 4：不开推测 / 官方草稿 / 再训草稿",
             f"{r3_vllm['baseline']['levels']['4']['tokens_per_second']:.1f} / {r3_vllm['dflash_released']['levels']['4']['tokens_per_second']:.1f} / {r3_vllm['dflash_v3']['levels']['4']['tokens_per_second']:.1f}",
             f"{r4_vllm['baseline']['levels']['4']['tokens_per_second']:.1f} / {r4_vllm['dflash_released']['levels']['4']['tokens_per_second']:.1f} / {r4_vllm['dflash_ours']['levels']['4']['tokens_per_second']:.1f}"],
            ["判读", "官方草稿未受损，再训无可测收益", "官方草稿命中率下降，再训收回一部分，服务吞吐随之提高"],
        ]
        note = ("成对差异按提示做 2,000 次 bootstrap，区间不含 0 才计为方向明确。vLLM 每条路线只执行一次，40 条中文提示或 40 条英文提示，"
                "`max_tokens=256`，无显著性声明。答案质量未评分。")
    else:
        headers = ["Measurement", "Regime A: small drift (English, LoRA r16 attention-only)", "Regime B: large drift (Chinese, LoRA r128 all modules)"]
        rows = [
            ["Released drafter first-offset hit rate on the fine-tuned target (same target text)",
             f"{en[0]['first_offset_hit_rate']['reference']:.3f} (193 of 200 prompts evaluable)",
             f"{zh_sel['first_offset_hit_rate']['reference']:.3f} (was {r4['agreement']['base_zh_released']['first_offset_hit_rate']:.3f} on the base target; 200 prompts)"],
            ["Adapted drafter first-offset hit rate, paired difference vs released (95% interval)",
             "; ".join(f"seed {seed}: {item['first_offset_hit_rate']['candidate']:.3f} ({interval(item['first_offset_hit_rate'])})" for seed, item in zip((0, 1, 2), en)),
             f"{zh_sel['first_offset_hit_rate']['candidate']:.3f} ({interval(zh_sel['first_offset_hit_rate'])})"],
            ["Joint-prefix acceptance length: released → adapted (95% interval)",
             "; ".join(f"seed {seed}: {item['joint_prefix_acceptance_length']['reference']:.2f} → {item['joint_prefix_acceptance_length']['candidate']:.2f} ({interval(item['joint_prefix_acceptance_length'])})" for seed, item in zip((0, 1, 2), en)),
             f"{zh_sel['joint_prefix_acceptance_length']['reference']:.2f} → {zh_sel['joint_prefix_acceptance_length']['candidate']:.2f} ({interval(zh_sel['joint_prefix_acceptance_length'])}); released drafter on the base target: {r4['agreement']['base_zh_released']['joint_prefix_acceptance_length']:.2f}"],
            ["vLLM 0.28.0 throughput (tok/s), concurrency 1: no speculation / released / adapted",
             f"{r3_vllm['baseline']['levels']['1']['tokens_per_second']:.1f} / {r3_vllm['dflash_released']['levels']['1']['tokens_per_second']:.1f} / {r3_vllm['dflash_v3']['levels']['1']['tokens_per_second']:.1f}",
             f"{r4_vllm['baseline']['levels']['1']['tokens_per_second']:.1f} / {r4_vllm['dflash_released']['levels']['1']['tokens_per_second']:.1f} / {r4_vllm['dflash_ours']['levels']['1']['tokens_per_second']:.1f}"],
            ["vLLM 0.28.0 throughput (tok/s), concurrency 4: no speculation / released / adapted",
             f"{r3_vllm['baseline']['levels']['4']['tokens_per_second']:.1f} / {r3_vllm['dflash_released']['levels']['4']['tokens_per_second']:.1f} / {r3_vllm['dflash_v3']['levels']['4']['tokens_per_second']:.1f}",
             f"{r4_vllm['baseline']['levels']['4']['tokens_per_second']:.1f} / {r4_vllm['dflash_released']['levels']['4']['tokens_per_second']:.1f} / {r4_vllm['dflash_ours']['levels']['4']['tokens_per_second']:.1f}"],
            ["Reading", "Released drafter not degraded; adaptation shows no measurable gain", "Released drafter loses hit rate; adaptation recovers part of it and serving throughput rises"],
        ]
        note = ("Paired differences use a 2,000-resample prompt-level bootstrap; a direction is claimed only when the interval excludes 0. "
                "Each vLLM route ran once on 40 Chinese or 40 English prompts with `max_tokens=256`; no significance claim. Answer quality was not graded.")
    return markdown_table(headers, rows) + "\n\n" + note


def generated_block(text, key, body, *, refresh):
    start, end = f"<!-- BEGIN {key} -->", f"<!-- END {key} -->"
    require(text.count(start) == 1 and text.count(end) == 1, "MISSING_OR_DUPLICATE_REPORT_BLOCK:" + key)
    before, rest = text.split(start)
    old, after = rest.split(end)
    expected = "\n" + body + "\n"
    if not refresh:
        require(old == expected, "REPORT_DATA_DRIFT:" + key)
    return before + start + expected + end + after


def published_files(root):
    return sorted(path for path in root.rglob("*") if path.is_file()
                  and not set(path.relative_to(root).parts) & IGNORED_PARTS
                  and path.suffix not in {".pyc", ".pyo"}
                  and path.relative_to(root).as_posix() not in {MANIFEST, RULES})


def file_manifest(root):
    records = {}
    for path in published_files(root):
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "PUBLISHED_SYMLINK")
        records[path.relative_to(root).as_posix()] = {"bytes": path.stat().st_size, "sha256": digest_file(path)}
    return {"files": records, "scope": "Published experiment files; generated rule results and this manifest excluded."}


def verify_manifest(root):
    saved = read_json(root / MANIFEST)
    for name in saved["files"]:
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name and ":" not in name, "MANIFEST_PATH_ESCAPE")
    require(saved == file_manifest(root), "PUBLISHED_FILE_HASH_OR_SET_MISMATCH")


def verify_provenance(root):
    provenance = read_json(root / "evidence/provenance.json")
    for round_name in ("round3", "round4"):
        record = provenance[round_name]
        for public, entry in record["results"].items():
            require((root / "results" / round_name / public).is_file(), "PROVENANCE_RESULT_MISSING:" + public)
        for public, entry in record["source"].items():
            if entry.get("published", True):
                require((root / "source" / round_name / public).is_file(), "PROVENANCE_SOURCE_MISSING:" + public)
        for public, entry in record["artifacts"].items():
            require(entry["published"] is False and len(entry["sha256"]) == 64, "ARTIFACT_PROVENANCE_INCOMPLETE:" + public)
    for text_path in root.rglob("*.json"):
        if set(text_path.relative_to(root).parts) & IGNORED_PARTS:
            continue
        text = text_path.read_text(encoding="utf-8")
        for shape in PRIVATE_SHAPES:
            require(shape.search(text) is None, "PRIVATE_MARKER_IN_PUBLIC_FILE:" + text_path.name)


def validate(root=ROOT, *, refresh=False):
    root = root.resolve()
    summary = summarize(root)
    if refresh:
        dump_json(root / "data/summary.json", summary)
    require(read_json(root / "data/summary.json") == summary, "SAVED_SUMMARY_MISMATCH")
    verify_provenance(root)
    for filename, chinese in READMES.items():
        path = topic_dir(root) / filename
        text = path.read_text(encoding="utf-8")
        text = generated_block(text, BLOCK, adaptation_table(summary, chinese), refresh=refresh)
        if refresh:
            path.write_text(text, encoding="utf-8")
        require(f"python experiments/{root.name}/validate_report.py" in text, "REPLAY_ENTRY_MISSING:" + filename)
    if refresh:
        dump_json(root / MANIFEST, file_manifest(root))
    verify_manifest(root)
    records = [{"id": name, "status": "PASS", "evidence": evidence} for name, evidence in (
        ("summary-recomputed-from-per-request-records", ["results/", "data/summary.json"]),
        ("paired-bootstrap-only-on-identical-target-text", ["results/round4/agreement/", "results/round3/agreement/"]),
        ("provenance-hashes-and-private-marker-scan", ["evidence/provenance.json"]),
        ("generated-bilingual-adaptation-table", ["../../README.md", "../../README_CN.md"]),
        ("published-file-integrity", [MANIFEST]),
    )]
    result = {"scope": "Offline verification of exported evidence; not fresh GPU execution, regrading or a quality certification.",
              "checks": records, "manifest_sha256": digest_file(root / MANIFEST)}
    if refresh:
        dump_json(root / RULES, result)
    require(read_json(root / RULES) == result, "VALIDATION_RECORD_DRIFT")
    for record in records:
        print("RULE", record["id"], record["status"])
    print("ADAPTATION_GATE=PASS")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Regenerate summary, README block and manifest after reviewing an edit")
    args = parser.parse_args()
    validate(refresh=args.refresh)


if __name__ == "__main__":
    main()
