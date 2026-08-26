#!/usr/bin/env python3
"""Render the completed Translator workload as a public bilingual document."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hosted-agent" / "src" / "lra-evidence-agent"
sys.path.insert(0, str(SOURCE))

from translation_workload import SECTION_IDS, SOURCE_SECTIONS  # noqa: E402


def checkpoint_contract_sha256(translations: list[str]) -> str:
    result_hashes = sorted(
        hashlib.sha256(translation.encode("utf-8")).hexdigest()
        for translation in translations
    )
    payload = {
        "names": list(SECTION_IDS),
        "result_sha256": result_hashes,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "evidence" / "owned-hosted-agent-live-translation.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "evidence"
            / "owned-hosted-agent-live-translation-output.md"
        ),
    )
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    acceptance = report.get("acceptance", {})
    translations = acceptance.get("translated_texts", [])
    if (
        report.get("passed") is not True
        or acceptance.get("status") != "completed"
        or acceptance.get("workload") != "translator_batch"
        or acceptance.get("recovery_proven") is not True
        or set(acceptance.get("entry_modes", [])) != {"fresh", "recovered"}
        or acceptance.get("process_instance_count", 0) < 2
        or not isinstance(translations, list)
        or len(translations) != len(SOURCE_SECTIONS)
        or not all(
            isinstance(translation, str) and translation.strip()
            for translation in translations
        )
        or acceptance.get("checkpoint_contract_sha256")
        != checkpoint_contract_sha256(translations)
    ):
        raise SystemExit("translation recovery report is not complete")

    lines = [
        "# Completed long-running translation output",
        "",
        f"- Agent version: `{report['deployment']['version']}`",
        f"- Elapsed: `{report['elapsed_seconds']}` seconds",
        f"- Response SHA-256: `{report['response_id_sha256']}`",
        f"- Entry modes: `{acceptance['entry_modes']}`",
        f"- Process instances: `{acceptance['process_instance_count']}`",
        f"- Terminal status: `{acceptance['status']}`",
        "",
        "> This is verbatim Azure Translator output captured to prove recovery "
        "and result completeness. It is not a human-edited translation or a "
        "language-quality evaluation.",
        "",
        "| Section | English source | Chinese result |",
        "|---:|---|---|",
    ]
    for index, (source, translation) in enumerate(
        zip(SOURCE_SECTIONS, translations, strict=True),
        start=1,
    ):
        source_cell = source.replace("|", "\\|")
        translation_cell = translation.replace("|", "\\|")
        lines.append(
            f"| {index} | {source_cell} | {translation_cell} |"
        )
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote completed translation output to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
