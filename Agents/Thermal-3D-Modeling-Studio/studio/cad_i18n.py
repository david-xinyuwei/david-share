"""English versions of the reference CadQuery scripts, for the English UI.

Only comments and string literals that contain Chinese are replaced (part names, NAME, METRICS labels / notes, comments);
code, numbers and geometry stay byte-identical. pregen_cad.py --lang en then runs the English scripts through the same
cad_runner and checks that every solid matches the Chinese build.

    python cad_i18n.py dump      # list every Chinese fragment (numbered) -> cad_examples_en/fragments.json
    python cad_i18n.py merge <values.json>   # {"<number>": "<English>"} -> cad_examples_en/i18n_en.json (zh -> en)
    python cad_i18n.py build     # cad_examples/<id>.py -> cad_examples_en/<id>.py; fails on any untranslated fragment
"""
from __future__ import annotations

import io
import json
import re
import sys
import tokenize
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "cad_examples"
DST = BASE / "cad_examples_en"
TABLE = DST / "i18n_en.json"
HAN = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")


def fragments(code: str) -> list[tuple[int, int, int, str]]:
    """(row, col_start, col_end, text) of every comment body / string-literal body that contains Chinese."""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(code).readline):
        if not HAN.search(tok.string):
            continue
        (r0, c0), (r1, c1) = tok.start, tok.end
        if r0 != r1:
            raise ValueError(f"multi-line token with Chinese at line {r0}")
        if tok.type == tokenize.COMMENT:
            body = tok.string[1:].strip()
            start = c0 + tok.string.index(body)
            out.append((r0, start, start + len(body), body))
        elif tok.type == tokenize.STRING:
            m = re.match(r"^([rRbBuU]*)(['\"])(.*)\2$", tok.string, re.S)
            if not m:
                raise ValueError(f"unsupported string literal at line {r0}: {tok.string[:40]}")
            out.append((r0, c0 + len(m[1]) + 1, c1 - 1, m[3]))
        elif tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
            if "{" in tok.string or "}" in tok.string:
                raise ValueError(f"f-string literal with braces at line {r0}")
            out.append((r0, c0, c1, tok.string))
        else:
            raise ValueError(f"Chinese outside comments/strings at line {r0}: {tok.string[:40]}")
    return out


def scripts() -> list[Path]:
    return sorted(SRC.glob("*.py"))


def dump() -> None:
    seen: dict[str, int] = {}
    for path in scripts():
        for *_, text in fragments(path.read_text(encoding="utf-8")):
            seen.setdefault(text, len(seen) + 1)
    DST.mkdir(exist_ok=True)
    (DST / "fragments.json").write_text(json.dumps({n: t for t, n in seen.items()}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(seen)} unique fragments -> {DST / 'fragments.json'}")


def merge(*values_paths: str) -> None:
    numbered = json.loads((DST / "fragments.json").read_text(encoding="utf-8"))
    values = {}
    for p in values_paths:
        values.update(json.loads(Path(p).read_text(encoding="utf-8")))
    missing = [n for n in numbered if not values.get(n, "").strip()]
    if missing:
        raise SystemExit(f"no English for fragments {missing[:20]}{' ...' if len(missing) > 20 else ''}")
    table = {numbered[n]: values[n] for n in sorted(numbered, key=int)}
    TABLE.write_text(json.dumps(table, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(table)} translations -> {TABLE}")


def quote_safe(text: str, line: str, start: int) -> str:
    q = line[start - 1] if start > 0 else ""
    return text.replace("\\", "\\\\").replace(q, "\\" + q) if q in "'\"" else text


def build() -> None:
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    DST.mkdir(exist_ok=True)
    for path in scripts():
        code = path.read_text(encoding="utf-8")
        lines = code.splitlines(keepends=True)
        frags = fragments(code)
        untranslated = sorted({t for *_, t in frags if t not in table})
        if untranslated:
            raise SystemExit(f"{path.name}: untranslated {untranslated[:5]}")
        for row, c0, c1, text in sorted(frags, key=lambda f: (f[0], -f[1])):
            line = lines[row - 1]
            lines[row - 1] = line[:c0] + quote_safe(table[text], line, c0) + line[c1:]
        out = "".join(lines)
        left = [i + 1 for i, l in enumerate(out.splitlines()) if HAN.search(l)]
        if left:
            raise SystemExit(f"{path.name}: Chinese left on lines {left[:10]}")
        compile(out, path.name, "exec")
        (DST / path.name).write_text(out, encoding="utf-8", newline="\n")
        print(f"{path.name}: {len(frags)} fragments translated")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "dump":
        dump()
    elif cmd == "merge":
        merge(*sys.argv[2:])
    elif cmd == "build":
        build()
    else:
        print(__doc__)
