"""
Build the console's replay pack from the recorded study runs.

The pack lets the console demonstrate every chart with no credentials, no
network and no spend - useful for a rehearsal, a laptop on a plane, or the
moment the conference-room wifi dies five minutes before the session.

Replay summaries are produced by the same bench_core.summarize_arm() the live
path uses, from the same raw .metrics.jsonl the written reports were built
from. Nothing is recomputed by hand, so a replayed chart and a live chart mean
the same thing.

Usage:
    python scripts/build_replay_pack.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bench_core  # noqa: E402  - needs the path insert above

PARENT = ROOT.parent
OUT = ROOT / "replay" / "replay_pack.json"

# Each entry: folder, glob for the raw metrics, title and the one-line reason a
# customer would care about this run.
SOURCES = [
    {
        "id": "scenario-matrix",
        "folder": "scenario-model-benchmark",
        "glob": "outputs/*.metrics.jsonl",
        "title": "Assistant scenarios across the candidate models",
        "description": "Single-turn, concurrency 1, Sweden Central VM to Sweden Central deployments, no tools.",
    },
    {
        "id": "router-validation",
        "folder": "model-router-validation",
        "glob": "outputs/*.metrics.jsonl",
        "title": "Model Router against its own direct baselines",
        "description": "Three router modes versus direct Sol and Luna on identical prompts, Chat Completions for every arm.",
    },
    {
        "id": "throughput-recalibration",
        "folder": "throughput-recalibration",
        "glob": "outputs/raw_fulltext/direct_*.jsonl",
        "title": "Throughput re-measurement",
        "description": "The follow-up run that recalibrated decode throughput after the first pass.",
    },
    {
        "id": "production-readiness",
        "folder": "production-readiness",
        "glob": "outputs/raw_fulltext/sustained_*.numeric.jsonl",
        "title": "Sustained concurrency",
        "description": "Steady-state behaviour under sustained load rather than one request at a time.",
    },
]


# Fields added after the recorded runs were pinned. They are computed live on
# every running console; the embedded copy omits them so the pinned evidence
# pack stays byte-identical.
POST_PIN_ARM_FIELDS = ("price_cache_write",)
POST_PIN_SUMMARY_FIELDS = ("cache_write_tokens_total",)
# Deployments added after the pin (see bench_core.FOLLOW_UP_RUNS). The pinned
# pack embeds the catalog as it was; the follow-up pack carries these arms.
POST_PIN_DEPLOYMENTS = ("gpt-6-luna",)

# Runs recorded after the pack was pinned. They go into their own pack so the
# pinned one never changes; server.load_replay() merges both.
OUT_FOLLOW_UPS = ROOT / "replay" / "replay_followups.json"
FOLLOW_UP_SOURCES = [
    {
        "id": "gpt6-luna-same-session",
        "folder": "scenario-model-benchmark",
        "glob": "outputs/gpt6-luna-20260926/direct_*.metrics.jsonl",
        "title": "GPT-6 Luna and every earlier arm, re-measured in one session (2026-09-26)",
        "description": "17 arms incl. GPT-6 Luna at every effort, same VM, prompts and resource as the scenario matrix, "
                       "single-turn, concurrency 1, no tools.",
    },
]


def embedded_catalog(catalog: dict) -> dict:
    arms = [{k: v for k, v in arm.items() if k not in POST_PIN_ARM_FIELDS} for arm in catalog["arms"]
            if arm["deployment"] not in POST_PIN_DEPLOYMENTS]
    study_models = [m for m in catalog.get("study_models", []) if m not in POST_PIN_DEPLOYMENTS]
    return {**catalog, "arms": arms, "study_models": study_models}


def follow_up_catalog_arms(catalog: dict) -> list[dict]:
    return [arm for arm in catalog["arms"] if arm["deployment"] in POST_PIN_DEPLOYMENTS]


def embedded_summaries(summaries: list[dict]) -> list[dict]:
    return [{k: v for k, v in s.items() if k not in POST_PIN_SUMMARY_FIELDS} for s in summaries]


def load_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def build_run(source: dict, *, pinned: bool = True) -> dict | None:
    folder = PARENT / source["folder"]
    if not folder.is_dir():
        return None
    files = sorted(folder.glob(source["glob"]))
    if not files:
        return None

    records: list[dict] = []
    for path in files:
        records.extend(load_records(path))

    measured = [r for r in records if not r.get("warmup")]
    if not measured:
        return None

    by_arm: dict[str, list[dict]] = {}
    for record in measured:
        by_arm.setdefault(record.get("arm") or record.get("deployment") or "unknown", []).append(record)

    summaries = [bench_core.summarize_arm(arm, rows) for arm, rows in sorted(by_arm.items())]
    priced = [s["cost_per_1k_requests"] for s in summaries if s.get("cost_per_1k_requests")]
    baseline = max(priced) if priced else None
    for summary in summaries:
        summary["value_ratio"] = bench_core.value_score(summary, baseline)

    return {
        "id": source["id"],
        "title": source["title"],
        "description": source["description"],
        "folder": source["folder"],
        "files": [f.name for f in files],
        "records": len(measured),
        # the follow-up pack is not pinned, so it keeps every current summary field
        "summaries": embedded_summaries(summaries) if pinned else summaries,
    }


def check_or_write(path: Path, rendered: str, check: bool, label: str) -> int:
    if check:
        if not path.is_file():
            print(f"MISSING: {path.relative_to(ROOT)} has not been built.")
            return 1
        if path.read_text(encoding="utf-8") != rendered:
            print(f"STALE: {path.relative_to(ROOT)} differs from the recorded runs. Re-run without --check.")
            return 1
        print(f"VERIFIED: {label}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(ROOT)}: {label}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="Verify the committed pack matches the recorded runs; write nothing.")
    args = parser.parse_args()

    runs = [run for run in (build_run(s) for s in SOURCES) if run]
    if not runs:
        print("No recorded study runs found next to the console; nothing to build.")
        return 1

    catalog = bench_core.catalog(include_unverified=True)
    pack = {
        "_comment": "Recorded runs re-aggregated by bench_core.summarize_arm. "
                    "Replayed measurements, not a live test.",
        # Kept in the non-LFS pack so a clone without git-lfs can still open
        # replay mode. Live mode continues to read the sibling study assets.
        # The pack is pinned evidence, so catalog fields introduced after the
        # recorded runs are left out of the embedded copy; a live catalog
        # always carries them.
        "catalog": embedded_catalog(catalog),
        "runs": runs,
    }
    status = check_or_write(OUT, json.dumps(pack, ensure_ascii=False, indent=2) + "\n", args.check,
                            f"{len(runs)} recorded run(s), {sum(len(r['summaries']) for r in runs)} arm summaries.")

    follow_runs = [run for run in (build_run(s, pinned=False) for s in FOLLOW_UP_SOURCES) if run]
    follow_pack = {
        "_comment": "Runs recorded after replay_pack.json was pinned, re-aggregated by bench_core.summarize_arm. "
                    "Replayed measurements, not a live test. server.load_replay() merges this into the pinned pack.",
        "catalog_arms": follow_up_catalog_arms(catalog),
        "study_models": [m for m in catalog.get("study_models", []) if m in POST_PIN_DEPLOYMENTS],
        "runs": follow_runs,
    }
    status |= check_or_write(OUT_FOLLOW_UPS, json.dumps(follow_pack, ensure_ascii=False, indent=2) + "\n",
                             args.check, f"{len(follow_runs)} follow-up run(s), "
                                         f"{sum(len(r['summaries']) for r in follow_runs)} arm summaries.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
