"""对每个工具做一次真实调用，确认外部依赖可用。

用法：
    .venv\\Scripts\\python.exe -m scripts.smoke_tools            # 只跑无需凭据的工具
    .venv\\Scripts\\python.exe -m scripts.smoke_tools --all      # 含 Azure OpenAI / SMTP / 换壁纸
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src import tools

# 管道或非 UTF-8 控制台下 Windows 默认用 cp1252，中文输出会直接抛 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FREE_CASES: list[tuple[str, dict]] = [
    ("get_current_time", {"timezone": "北京"}),
    ("get_weather", {"location": "北京"}),
    ("get_stock_quote", {"symbol": "微软"}),
    ("get_news_headlines", {"limit": 3}),
    ("web_search", {"query": "Lenovo AI PC", "max_results": 3}),
    ("search_wallpaper_image", {"query": "snow mountain sunrise"}),
]

CREDENTIALED_CASES: list[tuple[str, dict]] = [
    ("create_news_briefing", {"topic": "人工智能", "limit": 5}),
    ("generate_wallpaper_image", {"prompt": "雪山日出，极简风格"}),
    ("set_desktop_wallpaper", {}),
]


async def run(cases: list[tuple[str, dict]]) -> int:
    failures = 0
    for name, args in cases:
        result = await tools.dispatch(name, args)
        ok = bool(result.get("ok"))
        failures += 0 if ok else 1
        preview = json.dumps(result, ensure_ascii=False, default=str)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {preview[:300]}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="同时验证需要凭据的工具")
    args = parser.parse_args()

    cases = FREE_CASES + (CREDENTIALED_CASES if args.all else [])
    failures = asyncio.run(run(cases))

    print(f"\n合计 {len(cases)} 项，失败 {failures} 项")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
