#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "optimization-evolution.json"
EN_OUTPUT = ROOT / "docs" / "optimization-evolution.md"
CN_OUTPUT = ROOT / "docs" / "optimization-evolution-CN.md"


TEXT = {
    "en": {
        "title": "From Model Constraints to Accuracy Closure: MiMo-V2.5-Pro on MI300X",
        "switch": "[中文版](optimization-evolution-CN.md) | [Main benchmark report](../README.md)",
        "intro": (
            "This chapter explains the order in which the MI300X serving stack evolved and why later "
            "optimizations only become meaningful after earlier contracts are stable. It separates model "
            "architecture, operator kernels, memory, scheduling, parallelism, and correctness instead of "
            "presenting them as one undifferentiated speed recipe."
        ),
        "scope": "Scope and evidence boundary",
        "scope_body": (
            "This is a public, source-anchored evolution map. The stages were not all measured in one "
            "controlled run, so their sequence must not be read as an additive speedup waterfall. Public "
            "commits establish implementation changes; this repository's sanitized data establishes only "
            "the measurements explicitly linked from the main benchmark report."
        ),
        "short": "The evolution in one page",
        "short_headers": ("Stage", "Layer", "What changed", "What it unlocked"),
        "dag": "Exact dependency graph",
        "dag_body": (
            "The PNG above is chronological. The graph below is causal: a node may depend on more than the "
            "stage immediately before it."
        ),
        "order": "Why the order matters",
        "order_headers": ("Rule", "Reason"),
        "stages": "Stage-by-stage explanation",
        "question": "Question",
        "answer": "Answer",
        "problem": "Bottleneck exposed",
        "change": "Technical change",
        "dependency": "Why this stage comes here",
        "unlock": "What it unlocks",
        "boundary": "Claim boundary",
        "evidence_meaning": "What the evidence establishes",
        "evidence": "Public evidence",
        "claims": "Machine-readable claim bindings",
        "claim_headers": ("Claim ID", "Statement", "Support", "Source locator", "Sources"),
        "baseline": "This is the baseline contract; it has no earlier runtime dependency.",
        "depends": "Depends on {items}. Without those prerequisites, this stage cannot be isolated or interpreted.",
        "parallelism": "TP, DP, EP, and PD are different axes",
        "parallelism_intro": (
            "These labels answer different questions. Combining them into a single 'GPU count' hides model "
            "placement, replica count, expert communication, and phase separation."
        ),
        "parallelism_headers": ("Axis", "Role", "How it appears here", "Boundary"),
        "layers": "How the layers interact",
        "layers_headers": ("Layer", "Primary evidence", "Typical failure if skipped"),
        "layers_rows": (
            ("Operators and kernels", "Kernel marker, operator test, matched-shape benchmark", "The runtime silently uses a generic or stale implementation."),
            ("Memory and KV layout", "KV usage, page-size/layout identity, actual batch", "Configured concurrency rises while the active batch does not."),
            ("Scheduling and parallelism", "Scheduler traces, queue state, per-rank traffic", "Throughput is attributed to the wrong phase or topology."),
            ("Correctness and evaluation", "Sampling-path probe, trajectory, scorer output", "A fast healthy server produces a methodologically invalid score."),
        ),
        "discipline": "Evidence and claim discipline",
        "discipline_items": (
            "Architecture sources define supported behavior; they do not prove a measured uplift.",
            "A public commit proves that code or configuration changed; it does not prove an end-to-end effect.",
            "A microkernel result must not be promoted to a service-level result without a controlled run.",
            "Client concurrency, configured limits, and actual scheduler batch are separate quantities.",
            "Performance closure and accuracy closure are separate lineages; neither substitutes for the other.",
        ),
        "verify": "Verify the generated artifact",
        "verify_body": "The article, diagram, and dependency data are deterministic repository artifacts:",
        "expected": "Expected gate summary",
        "references": "Public references",
        "references_headers": ("ID", "Type", "Source"),
    },
    "cn": {
        "title": "从模型约束到 Accuracy Closure：MiMo-V2.5-Pro MI300X 优化演进",
        "switch": "[English](optimization-evolution.md) | [Benchmark 主报告](../README-CN.md)",
        "intro": (
            "本章解释 MI300X 推理栈为什么按这个顺序演进，以及为什么只有前一层契约稳定之后，后一层优化才有意义。"
            "内容把模型架构、Operator kernel、Memory、Scheduling、Parallelism 与 Correctness 分开讨论，不把它们混成一套无法审计的加速配方。"
        ),
        "scope": "范围与证据边界",
        "scope_body": (
            "这是一张面向公开读者、带来源锚点的演进图。所有阶段并非来自同一轮受控测试，因此不能把时间顺序读成可叠加的加速瀑布。"
            "公开 commit 只能证明实现发生变化；只有主 Benchmark 报告链接的脱敏数据，才能支撑其中明确标注的实测结论。"
        ),
        "short": "一页看懂演进主线",
        "short_headers": ("阶段", "技术层", "改了什么", "解锁了什么"),
        "dag": "精确依赖图",
        "dag_body": "上方 PNG 表示时间顺序；下方图表示因果依赖。一个节点可能同时依赖多条前置路径，而不只依赖紧邻阶段。",
        "order": "为什么必须按这个顺序",
        "order_headers": ("原则", "原因"),
        "stages": "逐阶段解释",
        "question": "问题",
        "answer": "说明",
        "problem": "暴露出的瓶颈",
        "change": "技术改动",
        "dependency": "为什么排在这里",
        "unlock": "解锁的能力",
        "boundary": "结论边界",
        "evidence_meaning": "这些证据能证明什么",
        "evidence": "公开证据",
        "claims": "机器可读 Claim 绑定",
        "claim_headers": ("Claim ID", "Statement", "支持类型", "来源定位", "来源"),
        "baseline": "这是基线契约，没有更早的 Runtime 依赖。",
        "depends": "依赖 {items}。如果这些前置条件不成立，就无法隔离或解释当前阶段。",
        "parallelism": "TP、DP、EP 与 PD 是四个不同维度",
        "parallelism_intro": (
            "这些标签回答的是不同问题。把它们统称为 GPU 数量，会掩盖模型切分、副本数量、Expert 通信以及 Prefill/Decode 阶段分离。"
        ),
        "parallelism_headers": ("维度", "作用", "在本项目中的位置", "边界"),
        "layers": "各技术层如何相互作用",
        "layers_headers": ("技术层", "主要证据", "跳过该层的典型后果"),
        "layers_rows": (
            ("Operator 与 Kernel", "Kernel marker、Operator test、相同 shape Benchmark", "Runtime 静默使用通用实现或旧 JIT 产物。"),
            ("Memory 与 KV layout", "KV usage、Page size/Layout identity、实际 batch", "配置并发不断提高，但活跃 batch 没有变化。"),
            ("Scheduling 与 Parallelism", "Scheduler trace、Queue state、Per-rank traffic", "吞吐被错误归因到其他阶段或 topology。"),
            ("Correctness 与 Evaluation", "Sampling-path probe、Trajectory、Scorer output", "服务很快且健康，但得分方法不成立。"),
        ),
        "discipline": "证据与结论纪律",
        "discipline_items": (
            "架构资料定义支持的行为，不能证明实测提升。",
            "公开 commit 证明代码或配置发生变化，不能直接证明端到端效果。",
            "Microkernel 结果只有经过受控服务测试，才能升级为端到端结论。",
            "Client concurrency、配置上限与 Scheduler 实际 batch 是三个不同概念。",
            "Performance closure 与 Accuracy closure 属于不同 lineage，不能相互替代。",
        ),
        "verify": "验证生成产物",
        "verify_body": "文章、图片与依赖数据都是可确定性重建的 Repo 产物：",
        "expected": "预期门禁摘要",
        "references": "公开参考资料",
        "references_headers": ("ID", "类型", "来源"),
    },
}


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    output.extend("| " + " | ".join(escape_cell(cell) for cell in row) + " |" for row in rows)
    return output


def source_link(source: dict, docs_relative: bool = True) -> str:
    if "url" in source:
        return f"[{source['title']}]({source['url']})"
    prefix = "../" if docs_relative else ""
    return f"[`{source['path']}`]({prefix}{source['path']})"


def dependency_mermaid(stages: list[dict]) -> str:
    by_id = {stage["id"]: stage for stage in stages}
    lines = ["```mermaid", "flowchart LR"]
    for stage in stages:
        label = f"{stage['sequence']} · {stage['title_en']}"
        lines.append(f"  S{stage['sequence']}[\"{label}\"]")
    for stage in stages:
        for dependency in stage["depends_on"]:
            lines.append(f"  S{by_id[dependency]['sequence']} --> S{stage['sequence']}")
    lines.extend(
        [
            "  classDef model fill:#fff1f2,stroke:#be363e,color:#20262e",
            "  classDef runtime fill:#eef6fb,stroke:#1f6897,color:#20262e",
            "  classDef correct fill:#fff1f5,stroke:#af3f5c,color:#20262e",
            "  class S0 model",
            "  class S1,S2,S3,S4,S5,S6 runtime",
            "  class S7,S8 correct",
            "```",
        ]
    )
    return "\n".join(lines)


def render(language: str, data: dict) -> str:
    t = TEXT[language]
    suffix = "en" if language == "en" else "cn"
    by_id = {stage["id"]: stage for stage in data["stages"]}
    lines = [
        f"# {t['title']}",
        "",
        t["switch"],
        "",
        t["intro"],
        "",
        '<div align="center"><img src="../images/optimization-evolution.png" width="960" alt="MiMo-V2.5-Pro MI300X optimization evolution"></div>',
        "",
        f"## {t['scope']}",
        "",
        t["scope_body"],
        "",
        f"> {data['scope'][suffix]}",
        "",
        f"## {t['short']}",
        "",
    ]

    lines.extend(
        table(
            t["short_headers"],
            [
                (
                    str(stage["sequence"]),
                    stage["lane"],
                    stage[f"change_{suffix}"],
                    stage[f"unlock_{suffix}"],
                )
                for stage in data["stages"]
            ],
        )
    )
    lines.extend(["", f"## {t['dag']}", "", t["dag_body"], "", dependency_mermaid(data["stages"]), ""])

    lines.extend([f"## {t['order']}", ""])
    lines.extend(
        table(
            t["order_headers"],
            [(rule[f"title_{suffix}"], rule[f"reason_{suffix}"]) for rule in data["order_rules"]],
        )
    )
    lines.extend(["", f"## {t['stages']}", ""])

    for stage in data["stages"]:
        dependencies = stage["depends_on"]
        dependency_text = t["baseline"]
        if dependencies:
            items = ", ".join(
                f"**{by_id[item]['sequence']} · {by_id[item][f'title_{suffix}']}**" for item in dependencies
            )
            dependency_text = t["depends"].format(items=items)
        evidence = ", ".join(source_link(data["sources"][ref]) for ref in stage["source_refs"])
        lines.extend(
            [
                f'<!-- stage:{stage["id"]} -->',
                f"### {stage['sequence']}. {stage[f'title_{suffix}']}",
                "",
            ]
        )
        lines.extend(
            table(
                (t["question"], t["answer"]),
                [
                    (t["problem"], stage[f"problem_{suffix}"]),
                    (t["change"], stage[f"change_{suffix}"]),
                    (t["dependency"], dependency_text),
                    (t["unlock"], stage[f"unlock_{suffix}"]),
                    (t["boundary"], stage[f"boundary_{suffix}"]),
                    (t["evidence_meaning"], stage[f"evidence_{suffix}"]),
                    (t["evidence"], evidence),
                ],
            )
        )
        lines.extend(["", f"**{t['claims']}:**", ""])
        lines.extend(
            table(
                t["claim_headers"],
                [
                    (
                        claim_ref,
                        data["claims"][claim_ref][f"statement_{suffix}"],
                        data["claims"][claim_ref]["support_type"],
                        data["claims"][claim_ref]["locator"],
                        ", ".join(
                            source_link(data["sources"][source_ref])
                            for source_ref in data["claims"][claim_ref]["source_refs"]
                        ),
                    )
                    for claim_ref in stage["claim_refs"]
                ],
            )
        )
        lines.append("")

    lines.extend([f"## {t['parallelism']}", "", t["parallelism_intro"], ""])
    lines.extend(
        table(
            t["parallelism_headers"],
            [
                (
                    f"**{axis['axis']} — {axis[f'name_{suffix}']}**",
                    axis[f"role_{suffix}"],
                    axis[f"project_{suffix}"],
                    axis[f"boundary_{suffix}"],
                )
                for axis in data["parallelism_axes"]
            ],
        )
    )

    lines.extend(["", f"## {t['layers']}", ""])
    lines.extend(table(t["layers_headers"], list(t["layers_rows"])))
    lines.extend(["", f"## {t['discipline']}", ""])
    lines.extend(f"- {item}" for item in t["discipline_items"])
    lines.extend(
        [
            "",
            f"## {t['verify']}",
            "",
            t["verify_body"],
            "",
            "```bash",
            "python3 -m pip install -r requirements.txt",
            "python3 scripts/validate_optimization_evolution.py",
            "python3 scripts/render_optimization_docs.py --check",
            "python3 scripts/generate_optimization_evolution.py --check",
            "python3 scripts/validate_repo.py",
            "```",
            "",
            f"**{t['expected']}:**",
            "",
            "```text",
            "OPTIMIZATION_EVOLUTION_DATA=PASS",
            "OPTIMIZATION_DOCS_CURRENT=PASS",
            "DIAGRAM_CURRENT=PASS",
            "REPO_VALIDATION=PASS",
            "```",
            "",
            f"## {t['references']}",
            "",
        ]
    )
    lines.extend(
        table(
            t["references_headers"],
            [
                (source_id, source["type"], source_link(source))
                for source_id, source in data["sources"].items()
            ],
        )
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    if not __debug__ or sys.flags.optimize:
        raise RuntimeError("Documentation checks require normal Python mode; -O/-OO is not supported.")
    parser = argparse.ArgumentParser(description="Render bilingual MI300X optimization evolution docs")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    outputs = {EN_OUTPUT: render("en", data), CN_OUTPUT: render("cn", data)}
    if args.check:
        for path, expected in outputs.items():
            assert path.exists(), f"missing generated document: {path}"
            assert path.read_text(encoding="utf-8") == expected, f"stale generated document: {path}"
        print("OPTIMIZATION_DOCS_CURRENT=PASS")
        return 0

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"generated={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())