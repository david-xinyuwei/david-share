"""Pre-generate the example result for each scenario so the demo can show something instantly.

Usage (inside the app venv, with .env loaded):
    python pregen.py                 # all scenarios missing from cache (Chinese examples → cache/<id>.json)
    python pregen.py --force         # regenerate everything
    python pregen.py coldplate mchx  # specific scenarios
    python pregen.py --lang en       # English examples (prompt_en + English output rules → cache/<id>.en.json)
    python pregen.py --effort low    # pin the GPT-6 reasoning effort (default: server AOAI_REASONING_EFFORT)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import sys
from pathlib import Path

import app as studio
from scenarios import SCENARIOS

BASE = Path(__file__).resolve().parent


def sample_image_data_url(rel: str) -> str | None:
    path = BASE / rel.lstrip("/")
    if not path.exists():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


async def pregen_one(s: dict, attempts: int = 2, lang: str = "zh", effort: str | None = None) -> bool:
    image = sample_image_data_url(s["sample_image"]) if s.get("requires_image") and s.get("sample_image") else None
    if s.get("requires_image") and not image:
        print(f"[{s['id']}] skipped: sample image missing")
        return False
    prompt = s.get("prompt_en") or s["prompt"] if lang == "en" else s["prompt"]
    body = studio.GenerateBody(scenario_id=s["id"], save_as_cache=True, lang=lang, reasoning_effort=effort,
                               messages=[studio.Message(role="user", content=prompt, image=image)])
    for attempt in range(1, attempts + 1):
        print(f"[{s['id']}] generating {lang} (attempt {attempt}) ...", flush=True)
        final = None
        chars = 0
        async for ev in studio.run_generation(body):
            if ev.startswith("event: delta"):
                chars += len(ev)
            elif ev.startswith("event: done"):
                final = json.loads(ev.split("\n", 1)[1][len("data: "):])
            elif ev.startswith("event: error"):
                print(f"[{s['id']}] error: {ev.strip()}")
        if final and final.get("ok"):
            print(f"[{s['id']}] OK  {final['latency_s']}s  metrics={len(final['metrics'])}  html={len(final['html'])} chars")
            return True
        print(f"[{s['id']}] no valid HTML (attempt {attempt})")
    return False


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--lang", choices=("zh", "en"), default="zh", help="language of the saved example (default zh)")
    ap.add_argument("--effort", choices=studio.REASONING_EFFORTS, default=None, help="GPT-6 reasoning effort (default: server setting)")
    args = ap.parse_args()
    todo = [s for s in SCENARIOS if (not args.ids or s["id"] in args.ids)]
    if not args.force:
        todo = [s for s in todo if not studio.cache_path(s["id"], args.lang).exists()]
    if not todo:
        print("nothing to do")
        return 0
    failed = []
    for s in todo:
        if not await pregen_one(s, lang=args.lang, effort=args.effort):
            failed.append(s["id"])
    print("done. failed:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
