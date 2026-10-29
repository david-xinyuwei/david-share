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


def localize_block(text):
    from markdown_it import MarkdownIt

    translations = json.loads(Path(__file__).with_name("table_labels_en.json").read_text(encoding="utf-8"))
    pattern = re.compile("|".join(re.escape(key) for key in sorted(translations, key=len, reverse=True)))
    parser = MarkdownIt("commonmark", {"html": True})
    lines = []
    for line in text.splitlines():
        parts = line.split("|") if line.startswith("|") else [line]
        translated = []
        for part in parts:
            value = part.strip()
            if value in translations:
                result = translations[value]
            else:
                output = []
                links = []
                for token in parser.parseInline(value)[0].children or []:
                    if token.type == "link_open":
                        links.append(token.attrGet("href"))
                        output.append("[")
                    elif token.type == "link_close":
                        output.append("](" + links.pop() + ")")
                    elif token.type == "code_inline":
                        output.append("`" + token.content + "`")
                    elif token.type == "text":
                        output.append(translations[token.content] if token.content in translations else
                                      token.content if links and "/" in token.content else
                                      pattern.sub(lambda match: translations[match.group()], token.content))
                    elif token.type in ("strong_open", "strong_close"):
                        output.append("**")
                    elif token.type in ("em_open", "em_close"):
                        output.append("*")
                    elif token.type == "softbreak":
                        output.append("\n")
                    else:
                        output.append(token.content)
                result = "".join(output)
            translated.append(result)
        lines.append("| ".join(translated) if line.startswith("|") else translated[0])
    return "\n".join(lines)


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
