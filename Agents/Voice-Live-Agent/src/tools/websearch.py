"""联网搜索，走 WebIQ。"""

from __future__ import annotations

import re

from .. import webiq_client
from . import tool

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html or "")).strip()


@tool(
    name="web_search",
    description="联网搜索并返回真实网页结果。用户说搜一下、查一查、帮我找某个信息时调用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "description": "返回结果数，默认 5，最多 10"},
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int = 5) -> dict:
    max_results = max(1, min(int(max_results), 10))
    response = webiq_client.search_with_retry(
        webiq_client.client().web.search, query=query, max_results=max_results
    )

    results = []
    for rank, item in enumerate(getattr(response, "webResults", []) or [], start=1):
        results.append(
            {
                "rank": rank,
                "title": getattr(item, "title", "") or "",
                "url": getattr(item, "url", "") or "",
                "snippet": _strip_html(getattr(item, "content", ""))[:500],
            }
        )

    return {"query": query, "count": len(results), "results": results, "source": "WebIQ"}
