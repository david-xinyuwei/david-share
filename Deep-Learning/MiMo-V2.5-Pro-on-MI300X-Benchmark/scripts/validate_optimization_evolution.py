#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "optimization-evolution.json"
DOCS = (
    ROOT / "docs" / "optimization-evolution.md",
    ROOT / "docs" / "optimization-evolution-CN.md",
)
DIAGRAM = ROOT / "images" / "optimization-evolution.png"
REQUIRED_STAGE_FIELDS = {
    "id",
    "sequence",
    "lane",
    "status",
    "depends_on",
    "title_en",
    "title_cn",
    "problem_en",
    "problem_cn",
    "change_en",
    "change_cn",
    "unlock_en",
    "unlock_cn",
    "boundary_en",
    "boundary_cn",
    "evidence_en",
    "evidence_cn",
    "claim_refs",
    "source_refs",
}
ALLOWED_STATUSES = {
    "architecture_baseline",
    "adopted_runtime",
    "adopted_and_measured",
    "public_supplier_change",
    "adopted_and_explored",
    "public_supplier_fix",
    "public_supplier_method_update",
}
REQUIRED_CLAIM_FIELDS = {
    "statement_en",
    "statement_cn",
    "support_type",
    "source_refs",
    "locator",
}
ALLOWED_SUPPORT_TYPES = {"direct_documentation", "public_commit", "repository_evidence"}
REQUIRED_PARALLELISM_FIELDS = {
    "axis",
    "name_en",
    "name_cn",
    "role_en",
    "role_cn",
    "project_en",
    "project_cn",
    "boundary_en",
    "boundary_cn",
    "source_refs",
}


def load_data(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sources(sources: dict[str, dict]) -> None:
    assert sources, "sources must not be empty"
    for source_id, source in sources.items():
        assert source_id.strip() == source_id and source_id, f"invalid source id: {source_id!r}"
        assert source.get("type"), f"source type missing: {source_id}"
        assert source.get("title"), f"source title missing: {source_id}"
        has_url = "url" in source
        has_path = "path" in source
        assert has_url ^ has_path, f"source must contain exactly one of url/path: {source_id}"
        if has_url:
            parsed = urlparse(source["url"])
            assert parsed.scheme == "https" and parsed.netloc, f"invalid public URL: {source_id}"
        else:
            path = ROOT / source["path"]
            assert path.exists(), f"missing repository evidence path: {source_id}: {path}"


def validate_claims(claims: dict[str, dict], sources: dict[str, dict]) -> None:
    assert claims, "claims must not be empty"
    for claim_id, claim in claims.items():
        assert re.fullmatch(r"C-[A-Z0-9-]+", claim_id), f"invalid claim id: {claim_id}"
        assert set(claim) == REQUIRED_CLAIM_FIELDS, f"invalid claim shape: {claim_id}"
        assert claim["support_type"] in ALLOWED_SUPPORT_TYPES, f"invalid support type: {claim_id}"
        assert claim["source_refs"], f"claim must cite at least one source: {claim_id}"
        assert all(source_ref in sources for source_ref in claim["source_refs"]), (
            f"unknown claim source: {claim_id}"
        )
        for field in REQUIRED_CLAIM_FIELDS - {"source_refs"}:
            assert isinstance(claim[field], str) and claim[field].strip(), (
                f"claim field must be non-empty: {claim_id}.{field}"
            )


def validate_stages(stages: list[dict], sources: dict[str, dict], claims: dict[str, dict]) -> None:
    assert stages, "stages must not be empty"
    ids = [stage["id"] for stage in stages]
    assert len(ids) == len(set(ids)), "stage ids must be unique"
    assert [stage["sequence"] for stage in stages] == list(range(len(stages))), (
        "stage sequence must be contiguous and ordered"
    )

    by_id = {stage["id"]: stage for stage in stages}
    for stage in stages:
        missing = REQUIRED_STAGE_FIELDS - stage.keys()
        assert not missing, f"stage {stage.get('id', '<unknown>')} missing fields: {sorted(missing)}"
        assert stage["status"] in ALLOWED_STATUSES, f"invalid status for {stage['id']}"
        assert stage["source_refs"], f"stage must cite at least one source: {stage['id']}"
        assert len(stage["depends_on"]) == len(set(stage["depends_on"])), (
            f"duplicate dependency: {stage['id']}"
        )
        for field in REQUIRED_STAGE_FIELDS - {"sequence", "depends_on", "source_refs", "claim_refs"}:
            assert isinstance(stage[field], str) and stage[field].strip(), (
                f"stage field must be non-empty text: {stage['id']}.{field}"
            )
        for source_ref in stage["source_refs"]:
            assert source_ref in sources, f"unknown source {source_ref} in {stage['id']}"
        assert stage["claim_refs"], f"stage must bind at least one claim: {stage['id']}"
        assert len(stage["claim_refs"]) == len(set(stage["claim_refs"])), (
            f"duplicate claim binding: {stage['id']}"
        )
        for claim_ref in stage["claim_refs"]:
            assert claim_ref in claims, f"unknown claim {claim_ref} in {stage['id']}"
        claim_sources = {
            source_ref
            for claim_ref in stage["claim_refs"]
            for source_ref in claims[claim_ref]["source_refs"]
        }
        assert claim_sources == set(stage["source_refs"]), (
            f"stage sources must equal the union of bound claim sources: {stage['id']}"
        )
        for dependency in stage["depends_on"]:
            assert dependency in by_id, f"unknown dependency {dependency} in {stage['id']}"
            assert by_id[dependency]["sequence"] < stage["sequence"], (
                f"dependency must precede dependent stage: {dependency} -> {stage['id']}"
            )

    reachable = {stages[0]["id"]}
    for stage in stages[1:]:
        assert any(dependency in reachable for dependency in stage["depends_on"]), (
            f"stage is disconnected from earlier evolution: {stage['id']}"
        )
        reachable.add(stage["id"])


def validate_order_rules(rules: list[dict]) -> None:
    assert len(rules) >= 4, "at least four ordering rules are required"
    ids = [rule["id"] for rule in rules]
    assert len(ids) == len(set(ids)), "order rule ids must be unique"
    for rule in rules:
        assert set(rule) == {"id", "title_en", "title_cn", "reason_en", "reason_cn"}, (
            f"unexpected order rule shape: {rule.get('id')}"
        )
        assert all(isinstance(value, str) and value.strip() for value in rule.values()), (
            f"order rule fields must be non-empty: {rule.get('id')}"
        )


def validate_parallelism_axes(axes: list[dict], sources: dict[str, dict]) -> None:
    assert [item["axis"] for item in axes] == ["TP", "DP", "EP", "PD"], (
        "parallelism axes must remain TP, DP, EP, PD in explanatory order"
    )
    for item in axes:
        assert set(item) == REQUIRED_PARALLELISM_FIELDS, f"invalid parallelism shape: {item['axis']}"
        for field in REQUIRED_PARALLELISM_FIELDS - {"source_refs"}:
            assert isinstance(item[field], str) and item[field].strip(), (
                f"parallelism field must be non-empty: {item['axis']}.{field}"
            )
        assert item["source_refs"], f"parallelism axis must cite sources: {item['axis']}"
        assert all(source_ref in sources for source_ref in item["source_refs"]), (
            f"unknown parallelism source: {item['axis']}"
        )


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    return re.findall(r"```([^\n]*)\n(.*?)```", text, re.DOTALL)


def validate_generated_artifacts(data: dict) -> None:
    for script in ("render_optimization_docs.py", "generate_optimization_evolution.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        expected_marker = "OPTIMIZATION_DOCS_CURRENT=PASS" if script.startswith("render_") else "DIAGRAM_CURRENT=PASS"
        assert expected_marker in result.stdout, f"missing generated-artifact marker: {script}"

    english, chinese = (path.read_text(encoding="utf-8") for path in DOCS)
    assert fenced_blocks(english) == fenced_blocks(chinese), "bilingual code blocks differ"
    assert english.count("\n#") == chinese.count("\n#"), "bilingual heading counts differ"
    assert "../images/optimization-evolution.png" in english
    assert "../images/optimization-evolution.png" in chinese

    marker_positions = []
    for stage in data["stages"]:
        marker = f"<!-- stage:{stage['id']} -->"
        assert english.count(marker) == chinese.count(marker) == 1, f"stage marker mismatch: {stage['id']}"
        marker_positions.append((english.index(marker), chinese.index(marker)))
        assert f"### {stage['sequence']}. {stage['title_en']}" in english
        assert f"### {stage['sequence']}. {stage['title_cn']}" in chinese
        assert stage["evidence_en"] in english
        assert stage["evidence_cn"] in chinese

    english_end = english.index("\n## TP, DP, EP, and PD are different axes")
    chinese_end = chinese.index("\n## TP、DP、EP 与 PD 是四个不同维度")
    for index, stage in enumerate(data["stages"]):
        next_english = marker_positions[index + 1][0] if index + 1 < len(marker_positions) else english_end
        next_chinese = marker_positions[index + 1][1] if index + 1 < len(marker_positions) else chinese_end
        english_section = english[marker_positions[index][0]:next_english]
        chinese_section = chinese[marker_positions[index][1]:next_chinese]
        for source_ref in stage["source_refs"]:
            source = data["sources"][source_ref]
            needle = source.get("url", source.get("path"))
            assert needle in english_section, f"stage source absent from English section: {stage['id']}:{source_ref}"
            assert needle in chinese_section, f"stage source absent from Chinese section: {stage['id']}:{source_ref}"
        for claim_ref in stage["claim_refs"]:
            claim = data["claims"][claim_ref]
            for document, statement in (
                (english_section, claim["statement_en"]),
                (chinese_section, claim["statement_cn"]),
            ):
                assert claim_ref in document, f"claim id absent from stage section: {stage['id']}:{claim_ref}"
                assert statement in document, f"claim statement absent from stage section: {stage['id']}:{claim_ref}"
                assert claim["locator"] in document, f"claim locator absent from stage section: {stage['id']}:{claim_ref}"

    for source in data["sources"].values():
        needle = source.get("url", source.get("path"))
        assert needle in english and needle in chinese, f"source absent from docs: {needle}"

    png = DIAGRAM.read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "invalid evolution PNG"
    assert struct.unpack(">II", png[16:24]) == (1920, 1080), "unexpected evolution PNG dimensions"

    for readme in (ROOT / "README.md", ROOT / "README-CN.md"):
        text = readme.read_text(encoding="utf-8")
        assert "docs/optimization-evolution.md" in text
        assert "docs/optimization-evolution-CN.md" in text


def main() -> int:
    if not __debug__ or sys.flags.optimize:
        raise RuntimeError("Validation requires normal Python mode; -O/-OO is not supported.")
    parser = argparse.ArgumentParser(description="Validate the MI300X optimization evolution DAG")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()

    data = load_data(args.data)
    assert data.get("schema_version") == 1, "unsupported schema_version"
    assert data.get("scope", {}).get("en") and data.get("scope", {}).get("cn"), (
        "bilingual scope is required"
    )
    validate_sources(data["sources"])
    validate_claims(data["claims"], data["sources"])
    validate_stages(data["stages"], data["sources"], data["claims"])
    validate_order_rules(data["order_rules"])
    validate_parallelism_axes(data["parallelism_axes"], data["sources"])
    validate_generated_artifacts(data)

    edge_count = sum(len(stage["depends_on"]) for stage in data["stages"])
    print(f"stages={len(data['stages'])}")
    print(f"edges={edge_count}")
    print(f"sources={len(data['sources'])}")
    print(f"claims={len(data['claims'])}")
    print(f"order_rules={len(data['order_rules'])}")
    print(f"parallelism_axes={len(data['parallelism_axes'])}")
    print("generated_artifacts=PASS")
    print("OPTIMIZATION_EVOLUTION_DATA=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())