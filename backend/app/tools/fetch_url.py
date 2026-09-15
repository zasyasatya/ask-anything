"""fetch_url tool — download a page and extract readable text."""
from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .args import as_int, as_str
from .base import Tool, ToolContext, ToolResult

_WS = re.compile(r"\s+")
_DEFAULT_CHARS = 12000


async def run_fetch_url(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    url = as_str(args.get("url") or args.get("link") or args.get("href"),
                 "") or as_str(args.get("_raw"))
    if not url.startswith(("http://", "https://")):
        # `www.example.com/page` (tanpa skema) adalah kesalahan model yang lazim.
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", url, re.IGNORECASE):
            url = "https://" + url
        else:
            return ToolResult(summary=f"fetch_url: URL tidak valid: {url or '(kosong)'}",
                              data={"error": "invalid url",
                                    "hint": "Kirim URL absolut http(s), mis. "
                                            "{\"url\": \"https://contoh.test/x\"}"},
                              ok=False, hits=0)
    if ctx.http is None:                       # pragma: no cover - wiring bug
        return ToolResult(summary="fetch_url gagal: HTTP client tidak tersedia",
                          data={"error": "no http client"}, ok=False, hits=0)
    max_chars = max(500, min(60000, as_int(args.get("max_chars"), _DEFAULT_CHARS)))
    try:
        resp = await ctx.http.get(
            url,
            headers={"User-Agent": ctx.settings.user_agent,
                     "Accept": "text/html,application/xhtml+xml"},
            timeout=ctx.settings.fetch_timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return ToolResult(summary=f"fetch_url gagal: {exc}",
                          data={"error": str(exc), "url": url}, ok=False, hits=0)

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav",
                     "footer", "header"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    # Halaman tanpa <title> tetap punya judul berguna di h1 pertama.
    if not title:
        h1 = soup.find(["h1", "h2"])
        if h1 is not None:
            title = h1.get_text(" ", strip=True)
    text = _WS.sub(" ", soup.get_text(" ")).strip()[:max_chars]
    return ToolResult(
        summary=f"fetch_url {url}: {len(text)} karakter"
                + ("" if title else " (tanpa judul)"),
        data={"url": str(resp.url), "title": title, "text": text,
              "status": resp.status_code},
        hits=1 if text else 0,
    )


FETCH_URL = Tool(
    name="fetch_url",
    description=(
        "Fetch a web page and return its readable text content. Use after "
        "web_search to read a specific source in depth."
    ),
    source="browser",
    evidence=True,
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
