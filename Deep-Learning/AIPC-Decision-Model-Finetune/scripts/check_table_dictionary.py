"""List Chinese documentation table cells without an exact table_labels_en.json entry.

Standard library plus markdown-it-py (requirements-docs.txt). Read-only helper for keeping the bilingual
table dictionary complete before running render_diagrams.py --sync-english.
    python scripts/check_table_dictionary.py [--document README_CN.md] [--table N ...]
"""
import argparse
import json
import re
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")


def main():
    from render_diagrams import DOCUMENT_PAIRS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=int, action="append", default=[], help="1-based table index to inspect (default all)")
    parser.add_argument("--document", type=Path, action="append", help="Chinese document relative to the project root (default all registered pairs)")
    arguments = parser.parse_args()
    translations = json.loads((ROOT / "scripts" / "table_labels_en.json").read_text(encoding="utf-8"))
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    missing = {}
    documents = arguments.document or [Path(chinese) for chinese, _, _, _ in DOCUMENT_PAIRS]
    for document in documents:
        text = (ROOT / document).read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        index = 0
        for token in md.parse(text):
            if token.type != "table_open":
                continue
            index += 1
            if arguments.table and index not in arguments.table:
                continue
            for line in "".join(lines[token.map[0]:token.map[1]]).splitlines():
                if not line.startswith("|"):
                    continue
                for part in line.split("|"):
                    value = part.strip()
                    if value and CJK.search(value) and value not in translations:
                        missing.setdefault((document.as_posix(), index), []).append(value)
    for (document, table), cells in missing.items():
        print(f"{document} TABLE {table}: {len(cells)} cells without exact entry")
        for cell in dict.fromkeys(cells):
            print("  " + cell)
    print(f"total_missing={sum(len(v) for v in missing.values())}")


if __name__ == "__main__":
    main()
