"""fetch_url tool — download a page and extract readable text."""
from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .base import Tool, ToolContext, ToolResult

_WS = re.compile(r"\s+")


async def run_fetch_url(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    url = str(args.get("url", "")).strip()
    if not url.startswith(("http://", "https://")):
        return ToolResult(summary=f"fetch_url: URL tidak valid: {url}",
                          data={"error": "invalid url"})
    try:
        resp = await ctx.http.get(
            url,
            headers={"User-Agent": ctx.settings.user_agent},
            timeout=ctx.settings.fetch_timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return ToolResult(summary=f"fetch_url gagal: {exc}",
                          data={"error": str(exc)})

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav",
                     "footer", "header"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = _WS.sub(" ", soup.get_text(" ")).strip()
    text = text[: int(args.get("max_chars", 12000))]
    return ToolResult(
        summary=f"fetch_url {url}: {len(text)} karakter",
        data={"url": url, "title": title, "text": text},
    )


FETCH_URL = Tool(
    name="fetch_url",
    description=(
        "Fetch a web page and return its readable text content. Use after "
        "web_search to read a specific source in depth."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http(s) URL"},
            "max_chars": {"type": "integer", "default": 12000},
        },
        "required": ["url"],
    },
    run=run_fetch_url,
)
