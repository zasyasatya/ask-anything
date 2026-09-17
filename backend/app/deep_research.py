"""Deep Research engine — multi-query browsing that produces grouped nodes.

Unlike the regular agent loop (which streams text answers), deep research
opens a *canvas* of information nodes. Each node is a piece of evidence
(title, snippet, URL, year, source domain, category) that the frontend
renders as an interactive graph/grouped view.

The engine:
  1. Expands the user's topic into multiple search queries (variations,
     sub-topics, temporal angles).
  2. Runs web_search + fetch_url for each query.
  3. Extracts structured information from results.
  4. Groups nodes by source domain and year.
  5. Returns a structured payload the frontend canvas can render.

All browsing is done through the same tools as the agent loop, so provenance
is preserved and the mechanistic interpreter can trace every step.
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx

from .config import Settings
from .tools.web_search import run_web_search
from .tools.fetch_url import run_fetch_url
from .tools.base import ToolContext

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


# ─── Query expansion ────────────────────────────────────────────────────────

def _expand_queries(topic: str, max_queries: int = 6) -> list[str]:
    """Generate multiple search queries from a single topic.
    
    Strategy: base query + temporal variants + subtopic angles + question forms.
    """
    topic = topic.strip().rstrip("?!.")
    queries = [topic]
    
    # Temporal variants
    current_year = datetime.now().year
    queries.append(f"{topic} {current_year}")
    queries.append(f"{topic} latest research")
    
    # Question / explanation variants
    queries.append(f"what is {topic}")
    queries.append(f"{topic} overview analysis")
    
    # Comparative / deep-dive variants  
    queries.append(f"{topic} pros cons comparison")
    queries.append(f"{topic} history development")
    queries.append(f"{topic} key findings statistics")
    
    # Deduplicate and trim
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        ql = q.lower().strip()
        if ql not in seen:
            seen.add(ql)
            unique.append(q)
    
    return unique[:max_queries]


# ─── Node extraction ────────────────────────────────────────────────────────

def _extract_year(text: str, url: str = "") -> int | None:
    """Best-effort year extraction from snippet/title/url."""
    # Try explicit year patterns
    patterns = [
        r'\b(20[0-2]\d)\b',  # 2000-2029
        r'\b(19\d{2})\b',    # 1900-1999
    ]
    for p in patterns:
        m = re.search(p, text or "")
        if m:
            y = int(m.group(1))
            if 1900 <= y <= datetime.now().year + 1:
                return y
    # Try URL
    for p in patterns:
        m = re.search(p, url or "")
        if m:
            y = int(m.group(1))
            if 1900 <= y <= datetime.now().year + 1:
                return y
    return None


def _extract_domain(url: str) -> str:
    """Extract readable domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain
    except Exception:
        return "unknown"


def _categorize(title: str, snippet: str) -> str:
    """Categorize a node based on content keywords."""
    text = f"{title} {snippet}".lower()
    
    categories = {
        "Research & Academic": ["research", "study", "paper", "journal", "university", 
                                "peer-reviewed", "findings", "experiment", "hypothesis",
                                "penelitian", "jurnal", "akademik", "universitas"],
        "News & Media": ["news", "report", "announced", "breaking", "press", "media",
                         "berita", "laporan", "wartawan", "media"],
        "Official & Government": ["gov", "official", "regulation", "policy", "government",
                                  "resmi", "pemerintah", "regulasi", "kebijakan"],
        "Technology": ["software", "code", "api", "framework", "algorithm", "github",
                       "programming", "tech", "digital", "app", "platform",
                       "teknologi", "pemrograman", "aplikasi"],
        "Business & Industry": ["market", "company", "revenue", "business", "industry",
                                "startup", "enterprise", "investment",
                                "bisnis", "perusahaan", "investasi", "pasar"],
        "Tutorial & Guide": ["how to", "tutorial", "guide", "step", "learn", "course",
                             "documentation", "getting started",
                             "panduan", "tutorial", "cara", "langkah"],
        "Statistics & Data": ["statistics", "data", "survey", "percentage", "chart",
                              "graph", "analysis", "dataset",
                              "statistik", "data", "survei", "analisis"],
        "Opinion & Analysis": ["opinion", "analysis", "review", "editorial", "commentary",
                               "think", "perspective", "argument",
                               "opini", "analisis", "ulasan", "perspektif"],
    }
    
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return cat
    
    return "General"


def _build_summary(title: str, snippet: str, url: str) -> str:
    """Build a concise summary for a node."""
    if snippet and len(snippet) > 20:
        return snippet[:300] + ("..." if len(snippet) > 300 else "")
    return f"Informasi dari {_extract_domain(url)} tentang topik yang diteliti."


def _result_to_node(
    result: dict[str, str],
    query: str,
    node_id: int,
    fetched_content: str = "",
) -> dict[str, Any]:
    """Convert a search result into a canvas node."""
    title = result.get("title", "")
    url = result.get("url", "")
    snippet = result.get("snippet", "")
    domain = _extract_domain(url)
    year = _extract_year(f"{title} {snippet}", url)
    category = _categorize(title, snippet)
    
    # Build detailed summary
    summary = _build_summary(title, snippet, url)
    if fetched_content and len(fetched_content) > len(summary):
        # Use first paragraph of fetched content as richer summary
        paragraphs = [p.strip() for p in fetched_content.split("\n\n") if p.strip()]
        if paragraphs:
            summary = paragraphs[0][:500] + ("..." if len(paragraphs[0]) > 500 else "")
    
    return {
        "id": f"node-{node_id}",
        "title": title,
        "url": url,
        "snippet": snippet,
        "summary": summary,
        "domain": domain,
        "year": year,
        "category": category,
        "query": query,
        "fetched": bool(fetched_content),
        "content_preview": fetched_content[:800] if fetched_content else "",
    }


# ─── Main engine ────────────────────────────────────────────────────────────

async def run_deep_research(
    *,
    topic: str,
    settings: Settings,
    emit: EmitFn,
) -> dict[str, Any]:
    """Run deep research on a topic, returning grouped nodes for the canvas."""
    t0 = time.time()
    
    max_queries = settings.deep_research_max_queries
    max_results = settings.deep_research_max_results_per_query
    
    # Step 1: Expand queries
    queries = _expand_queries(topic, max_queries)
    await emit({
        "type": "research_phase",
        "phase": "expanding",
        "queries": queries,
        "t_ms": round((time.time() - t0) * 1000, 1),
    })
    
    nodes: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    node_id = 0
    tool_events: list[dict[str, Any]] = []
    
    async with httpx.AsyncClient() as http:
        ctx = ToolContext(settings=settings, http=http)
        
        # Step 2: Search for each query
        for qi, query in enumerate(queries):
            await emit({
                "type": "research_phase",
                "phase": "searching",
                "query": query,
                "query_index": qi,
                "total_queries": len(queries),
                "t_ms": round((time.time() - t0) * 1000, 1),
            })
            
            search_args = {"query": query, "max_results": max_results}
            search_t0 = time.time()
            
            try:
                search_result = await asyncio.wait_for(
                    run_web_search(search_args, ctx), timeout=20
                )
                search_duration = round((time.time() - search_t0) * 1000, 1)
            except Exception as exc:
                tool_events.append({
                    "name": "web_search",
                    "query": query,
                    "ok": False,
                    "error": str(exc),
                    "duration_ms": round((time.time() - search_t0) * 1000, 1),
                })
                await emit({
                    "type": "research_tool",
                    "name": "web_search",
                    "query": query,
                    "ok": False,
                    "error": str(exc),
                    "t_ms": round((time.time() - t0) * 1000, 1),
                })
                continue
            
            results = (search_result.data or {}).get("results", [])
            tool_events.append({
                "name": "web_search",
                "query": query,
                "ok": search_result.ok,
                "hits": len(results),
                "duration_ms": search_duration,
            })
            
            await emit({
                "type": "research_tool",
                "name": "web_search",
                "query": query,
                "ok": search_result.ok,
                "hits": len(results),
                "duration_ms": search_duration,
                "t_ms": round((time.time() - t0) * 1000, 1),
            })
            
            # Step 3: Process results + optional fetch
            for r in results:
                url = r.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                node_id += 1
                
                # Try to fetch top results for richer content
                fetched_content = ""
                if node_id <= max_queries * 2:  # Only fetch top N for speed
                    fetch_t0 = time.time()
                    try:
                        fetch_result = await asyncio.wait_for(
                            run_fetch_url({"url": url}, ctx), timeout=15
                        )
                        if fetch_result.ok and fetch_result.data:
                            fetched_content = str(
                                fetch_result.data.get("text", "") or
                                fetch_result.data.get("content", "")
                            )[:1200]
                        tool_events.append({
                            "name": "fetch_url",
                            "url": url,
                            "ok": fetch_result.ok,
                            "duration_ms": round((time.time() - fetch_t0) * 1000, 1),
                        })
                    except Exception:
                        pass  # Fetch failure is non-fatal
                
                node = _result_to_node(r, query, node_id, fetched_content)
                nodes.append(node)
                
                await emit({
                    "type": "research_node",
                    "node": node,
                    "t_ms": round((time.time() - t0) * 1000, 1),
                })
    
    # Step 4: Group nodes
    groups = _group_nodes(nodes)
    
    elapsed = round((time.time() - t0) * 1000, 1)
    
    result = {
        "topic": topic,
        "nodes": nodes,
        "groups": groups,
        "queries": queries,
        "tool_events": tool_events,
        "total_nodes": len(nodes),
        "total_sources": len(seen_urls),
        "elapsed_ms": elapsed,
        "summary": _generate_topic_summary(topic, nodes, groups),
    }
    
    await emit({
        "type": "research_done",
        **result,
        "t_ms": elapsed,
    })
    
    return result


def _group_nodes(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Group nodes by source domain and year."""
    by_source: dict[str, list[dict[str, Any]]] = {}
    by_year: dict[str, list[dict[str, Any]]] = {}
    by_category: dict[str, list[dict[str, Any]]] = {}
    
    for node in nodes:
        # By source domain
        domain = node.get("domain", "unknown")
        by_source.setdefault(domain, []).append(node)
        
        # By year
        year = node.get("year")
        year_key = str(year) if year else "Unknown"
        by_year.setdefault(year_key, []).append(node)
        
        # By category
        cat = node.get("category", "General")
        by_category.setdefault(cat, []).append(node)
    
    return {
        "by_source": {k: {
            "domain": k,
            "count": len(v),
            "nodes": [n["id"] for n in v],
        } for k, v in sorted(by_source.items(), key=lambda x: -len(x[1]))},
        "by_year": {k: {
            "year": k,
            "count": len(v),
            "nodes": [n["id"] for n in v],
        } for k, v in sorted(by_year.items(), key=lambda x: x[0], reverse=True)},
        "by_category": {k: {
            "category": k,
            "count": len(v),
            "nodes": [n["id"] for n in v],
        } for k, v in sorted(by_category.items(), key=lambda x: -len(x[1]))},
    }


def _generate_topic_summary(
    topic: str,
    nodes: list[dict[str, Any]],
    groups: dict[str, Any],
) -> str:
    """Generate a brief summary of the research findings."""
    total = len(nodes)
    sources = len(groups.get("by_source", {}))
    categories = list(groups.get("by_category", {}).keys())
    years = [k for k in groups.get("by_year", {}).keys() if k != "Unknown"]
    
    parts = [f"Ditemukan {total} informasi dari {sources} sumber berbeda."]
    
    if categories:
        top_cats = categories[:3]
        parts.append(f"Topik tercakup: {', '.join(top_cats)}.")
    
    if years:
        years_sorted = sorted([int(y) for y in years if y.isdigit()])
        if years_sorted:
            parts.append(
                f"Rentang tahun: {years_sorted[0]}–{years_sorted[-1]}."
            )
    
    return " ".join(parts)
