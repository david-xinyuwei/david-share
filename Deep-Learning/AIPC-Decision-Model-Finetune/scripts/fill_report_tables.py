"""Write generated tables into the report between <!-- TABLE:NAME --> and <!-- /TABLE:NAME --> markers.

Re-running replaces the previous content (idempotent); a bare <!-- TABLE:NAME --> marker gets its closing marker added.
  python fill_report_tables.py --report 文档/微调与端侧验证报告_20261027-130700.md \
      --blocks 验证结果/微调评测_X/summary/report_blocks.json --block ENGINE=验证结果/端侧引擎_20261027-124700/engine_brief.md
Prints which markers were filled and which marker in the report has no block. Standard library only.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--blocks", default="", help="JSON object {NAME: markdown}")
    ap.add_argument("--block", action="append", default=[], help="NAME=path to a markdown file")
    a = ap.parse_args()
    blocks = json.loads(Path(a.blocks).read_text(encoding="utf-8")) if a.blocks else {}
    for item in a.block:
        name, path = item.split("=", 1)
        blocks[name] = Path(path).read_text(encoding="utf-8").strip()
    report = Path(a.report)
    text = report.read_text(encoding="utf-8")
    for name, content in blocks.items():
        filled = f"<!-- TABLE:{name} -->\n{content.strip()}\n<!-- /TABLE:{name} -->"
        pattern = re.compile(rf"<!-- TABLE:{re.escape(name)} -->.*?<!-- /TABLE:{re.escape(name)} -->", re.S)
        if pattern.search(text):
            text = pattern.sub(lambda _: filled, text)
        elif f"<!-- TABLE:{name} -->" in text:
            text = text.replace(f"<!-- TABLE:{name} -->", filled, 1)
        else:
            print(f"no marker for {name}")
            continue
        print(f"filled {name}")
    missing = sorted(set(re.findall(r"<!-- TABLE:(\w+) -->", text)) - set(blocks))
    if missing:
        print("markers without a block:", ", ".join(missing))
    report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
