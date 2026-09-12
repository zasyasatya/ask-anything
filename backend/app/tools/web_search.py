"""web_search tool — DuckDuckGo lite by default (no API key), Serper/Tavily optional."""
from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from .base import Tool, ToolContext, ToolResult

DDG_URL = "https://lite.duckduckgo.com/lite/"


async def _ddg_search(client: httpx.AsyncClient, query: str, max_results: int,
                      settings) -> list[dict[str, str]]:
    resp = await client.get(
        DDG_URL,
        params={"q": query},
        headers={"User-Agent": settings.user_agent},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http") or "duckduckgo" in href:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        snippet = ""
        parent_td = a.find_parent("td")
        if parent_td is not None:
            sib = parent_td.find_next_sibling("td")
            if sib is not None:
                snippet = sib.get_text(" ", strip=True)
        if not snippet:
            parent_tr = a.find_parent("tr")
            if parent_tr is not None:
                nxt_tr = parent_tr.find_next_sibling("tr")
                if nxt_tr is not None:
                    snippet = nxt_tr.get_text(" ", strip=True)
        results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


async def _serper_search(client: httpx.AsyncClient, query: str, max_results: int,
                         api_key: str) -> list[dict[str, str]]:
    resp = await client.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": max_results},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("link", ""),
         "snippet": r.get("snippet", "")}
        for r in resp.json().get("organic", [])[:max_results]
    ]


async def _tavily_search(client: httpx.AsyncClient, query: str, max_results: int,
                         api_key: str) -> list[dict[str, str]]:
    resp = await client.post(
        "https://api.tavily.com/search",
        json={"query": query, "max_results": max_results},
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "snippet": r.get("content", "")}
        for r in resp.json().get("results", [])[:max_results]
    ]


async def run_web_search(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    query = str(args.get("query", "")).strip()
    max_results = int(args.get("max_results", 5))
    backend = ctx.settings.search_backend
    if backend == "serper" and ctx.settings.serper_api_key:
        impl = _serper_search(ctx.http, query, max_results,
                              ctx.settings.serper_api_key)
    elif backend == "tavily" and ctx.settings.tavily_api_key:
        impl = _tavily_search(ctx.http, query, max_results,
                              ctx.settings.tavily_api_key)
    else:
        impl = _ddg_search(ctx.http, query, max_results, ctx.settings)

    try:
        results = await impl
    except httpx.HTTPError as exc:
        return ToolResult(
            summary=f"web_search gagal (network): {exc}",
            data={"error": str(exc), "results": []},
        )
    if not results:
        return ToolResult(
            summary=f"web_search: tidak ada hasil untuk '{query}'",
            data={"results": []},
        )
    return ToolResult(
        summary=f"web_search '{query}': {len(results)} hasil",
        data={"query": query, "results": results},
    )


WEB_SEARCH = Tool(
    name="web_search",
    description=(
        "Search the public web for current information (news, prices, "
        "documentation). Returns titles, URLs and snippets. Use whenever the "
        "answer needs up-to-date or external facts."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "default": 5,
                            "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
    },
    run=run_web_search,
)
