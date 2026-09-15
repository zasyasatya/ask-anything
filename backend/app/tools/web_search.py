"""web_search tool — DuckDuckGo by default (no API key), Serper/Tavily optional.

Browsing is the tool that produces *citable evidence*, so "no result" has to be
distinguishable from "the search endpoint refused to answer". A silent empty
list is how an agent ends up answering from memory while the UI shows a
Browser badge — the exact behaviour this project forbids.

Therefore:

  * the HTML endpoint is tried when the configured one yields nothing (DDG Lite
    and DDG HTML have different markup *and* different rate limits);
  * both markups are parsed (table rows of `/lite/`, `a.result__a` of `/html/`);
  * DDG redirect URLs (`/l/?uddg=…`) are unwrapped, so a citation points at the
    real page instead of a tracking link;
  * an anti-bot/anomaly page is reported as ``ok=False`` with the reason, and a
    genuine "no results" answer stays ``ok=True, hits=0``.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .args import as_int, as_str
from .base import Tool, ToolContext, ToolResult

#: Default; nilai aktif dibaca dari Settings.search_ddg_url (ASK_SEARCH_DDG_URL).
DDG_URL = "https://lite.duckduckgo.com/lite/"
DDG_HTML_URL = "https://html.duckduckgo.com/html/"

#: Endpoint yang dicoba berurutan saat endpoint utama tidak memberi hasil.
FALLBACK_URLS = (DDG_HTML_URL,)

_BLOCK_RE = re.compile(
    r"(anomaly|unusual traffic|automated queries|are you a robot|"
    r"captcha|blocked|rate.?limit|too many requests|detected unusual)",
    re.IGNORECASE,
)

_WS = re.compile(r"\s+")


def _unwrap(url: str) -> str:
    """DDG html mengirim tautan lewat `/l/?uddg=<url-encoded>`."""
    if not url:
        return ""
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    parsed = urlparse(u)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = (parse_qs(parsed.query).get("uddg") or [""])[0]
        if target:
            return unquote(target)
    return u


def _clean_items(rows: list[dict[str, str]], max_results: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        url = _unwrap(row.get("url", ""))
        if not url.startswith("http") or "duckduckgo.com" in url:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({
            "title": _WS.sub(" ", row.get("title", "")).strip() or url,
            "url": url,
            "snippet": _WS.sub(" ", row.get("snippet", "")).strip(),
        })
        if len(out) >= max_results:
            break
    return out


def parse_ddg_lite(html: str, max_results: int) -> list[dict[str, str]]:
    """Tabel `/lite/`: <a href> di satu sel, snippet di sel/baris berikutnya."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http") and not href.startswith("//"):
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
        rows.append({"title": title, "url": href, "snippet": snippet})
    return _clean_items(rows, max_results)


def parse_ddg_html(html: str, max_results: int) -> list[dict[str, str]]:
    """Halaman `/html/`: `a.result__a` + `.result__snippet`."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for a in soup.select("a.result__a, a.result__url, h2.result__title a"):
        href = a.get("href") or ""
        title = a.get_text(" ", strip=True)
        if not href:
            continue
        snippet = ""
        block = a.find_parent(class_=re.compile("result")) or a.parent
        if block is not None:
            sn = block.select_one(".result__snippet")
            if sn is not None:
                snippet = sn.get_text(" ", strip=True)
        rows.append({"title": title, "url": href, "snippet": snippet})
    if not rows:                      # markup lain: pakai parser tabel
        return parse_ddg_lite(html, max_results)
    return _clean_items(rows, max_results)


def _endpoints(settings) -> list[str]:
    """Configured endpoint first, then the built-in fallback (unless custom)."""
    configured = (getattr(settings, "search_ddg_url", "") or "").strip()
    if not configured or configured == DDG_URL:
        return [DDG_URL, *FALLBACK_URLS]
    return [configured, *[u for u in FALLBACK_URLS if u != configured]]


def _looks_blocked(html: str, status: int) -> bool:
    if status in (403, 429):
        return True
    return bool(_BLOCK_RE.search((html or "")[:4000]))


async def _fetch(client: httpx.AsyncClient, url: str, query: str, settings) -> str:
    resp = await client.get(
        url,
        params={"q": query},
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "id,en;q=0.8",
        },
    )
    resp.raise_for_status()
    return resp.text


async def _ddg_search(client: httpx.AsyncClient, query: str, max_results: int,
                      settings) -> tuple[list[dict[str, str]], str, list[str], bool]:
    """Try each endpoint.

    Returns ``(results, endpoint_used, problems, answered)`` where ``answered``
    is True when at least one endpoint actually answered (even with zero
    results). That distinction is what keeps "pencarian jalan tapi tidak ada
    hasil" apart from "endpointnya diblokir/gagal" in the UI.
    """
    problems: list[str] = []
    last_error = ""
    answered = False
    for url in _endpoints(settings):
        try:
            html = await _fetch(client, url, query, settings)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            problems.append(f"{urlparse(url).netloc}: {last_error}")
            continue
        if _looks_blocked(html, 200):
            problems.append(
                f"{urlparse(url).netloc}: halaman anti-bot (bukan hasil pencarian)")
            continue
        answered = True
        parser = parse_ddg_lite if "/lite/" in url else parse_ddg_html
        results = parser(html, max_results)
        if results:
            return results, url, problems, True
        problems.append(f"{urlparse(url).netloc}: 0 hasil")
    if last_error and not problems:
        problems.append(last_error)
    return [], "", problems, answered


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
    query = as_str(args.get("query") or args.get("q") or args.get("search"),
                   "") or as_str(args.get("_raw"))
    max_results = max(1, min(10, as_int(args.get("max_results"), 5)))
    if not query:
        return ToolResult(
            summary="web_search gagal: argumen `query` kosong",
            data={"error": "query kosong", "results": [],
                  "hint": "Panggil ulang dengan {\"query\": \"...\"}"},
            ok=False, hits=0,
        )
    if ctx.http is None:                       # pragma: no cover - wiring bug
        return ToolResult(summary="web_search gagal: HTTP client tidak tersedia",
                          data={"error": "no http client", "results": []},
                          ok=False, hits=0)
    backend = ctx.settings.search_backend
    endpoint = ""
    problems: list[str] = []
    answered = False
    try:
        if backend == "serper" and ctx.settings.serper_api_key:
            results = await _serper_search(ctx.http, query, max_results,
                                           ctx.settings.serper_api_key)
            endpoint, answered = "serper", True
        elif backend == "tavily" and ctx.settings.tavily_api_key:
            results = await _tavily_search(ctx.http, query, max_results,
                                           ctx.settings.tavily_api_key)
            endpoint, answered = "tavily", True
        else:
            results, endpoint, problems, answered = await _ddg_search(
                ctx.http, query, max_results, ctx.settings)
    except httpx.HTTPError as exc:
        return ToolResult(
            summary=f"web_search gagal (network): {exc}",
            data={"query": query, "error": str(exc), "results": []},
            ok=False,
            hits=0,
        )

    if not results:
        # `answered=False` = semua endpoint gagal/diblokir (bukan "tidak ada
        # hasil"): bedanya penting, karena UI menandai yang pertama merah.
        blocked = not answered
        return ToolResult(
            summary=(f"web_search: tidak ada hasil untuk '{query}'"
                     if answered else
                     f"web_search gagal: {'; '.join(problems) or 'endpoint tidak menjawab'}")
                    + (f" — {'; '.join(problems)}" if problems and answered else ""),
            data={"query": query, "results": [], "problems": problems,
                  "endpoint": endpoint or None,
                  "error": ("; ".join(problems) or None) if blocked else None,
                  "blocked": blocked,
                  "hint": ("Endpoint pencarian tidak bisa dihubungi. Coba lagi, "
                           "atau set ASK_SEARCH_DDG_URL ke gateway pencarian "
                           "internal.") if blocked else None},
            ok=not blocked,
            hits=0,
        )
    return ToolResult(
        summary=f"web_search '{query}': {len(results)} hasil"
                + (f" ({endpoint})" if endpoint else ""),
        data={"query": query, "results": results, "endpoint": endpoint or None,
              "problems": problems},
        hits=len(results),
    )


WEB_SEARCH = Tool(
    name="web_search",
    description=(
        "Search the public web for current information (news, prices, "
        "documentation). Returns titles, URLs and snippets. Use whenever the "
        "answer needs up-to-date or external facts."
    ),
    source="browser",
    evidence=True,
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
