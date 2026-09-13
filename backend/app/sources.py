"""Source registry + citation enforcement for browser evidence.

The agent must never present browsing output as if it were its own knowledge:
every URL a browser tool touched is registered as a numbered source, handed
back to the model as a numbered list (so it can write ``[1]`` inline), and then
verified in the final answer by :func:`finalize_answer`.

Provenance matters as much as the citation itself, so a record carries the
``origin`` of the evidence:

  ``"browser"``  — a real URL retrieved by ``web_search`` / ``fetch_url``.
  ``"diagram"``  — *not* used here; diagram output is generated, never cited.

When a browser call yields nothing, the answer is explicitly labelled as
having no web evidence rather than silently going uncited.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

#: `[1]`, `[2,3]`, `[1][2]` — the inline citation markers we understand.
_CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*[,;-]\s*\d{1,3})*)\]")


@dataclass
class SourceRecord:
    """One citable URL discovered by a browser tool."""

    index: int
    url: str
    title: str = ""
    #: Which tool produced it ("web_search" | "fetch_url").
    tool: str = ""
    #: Provenance class, always "browser" here (see module docstring).
    origin: str = "browser"
    snippet: str = ""
    #: True once fetch_url read the full page (search hits start as False).
    read: bool = False
    #: Inline `[n]` markers found in the final answer.
    cited: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceRegistry:
    """Ordered, URL-deduplicated list of sources for one agent run."""

    items: list[SourceRecord] = field(default_factory=list)
    _by_url: dict[str, SourceRecord] = field(default_factory=dict)

    # -- collection ------------------------------------------------------
    def add(self, url: str, *, title: str = "", tool: str = "",
            snippet: str = "", read: bool = False) -> SourceRecord:
        """Register a URL, or upgrade the existing record for it.

        A search hit that is later fetched keeps its original number (so
        citations stay stable) but gains ``read=True`` and a better title.
        """
        url = (url or "").strip()
        existing = self._by_url.get(url)
        if existing is not None:
            if read:
                existing.read = True
            if title and (not existing.title or existing.tool == "web_search"):
                existing.title = title
            if snippet and not existing.snippet:
                existing.snippet = snippet
            return existing
        rec = SourceRecord(
            index=len(self.items) + 1, url=url, title=title or url,
            tool=tool, snippet=snippet[:400], read=read,
        )
        self.items.append(rec)
        self._by_url[url] = rec
        return rec

    def register_tool_result(self, tool_name: str, args: dict[str, Any],
                             data: dict[str, Any]) -> int:
        """Absorb one browser-tool payload. Returns how many sources were added.

        Non-browser tools are ignored on purpose: a diagram is generated
        content, and citing it as a "source" would be fabricated evidence.
        """
        if not isinstance(data, dict) or data.get("error"):
            return 0
        before = len(self.items)
        if tool_name == "web_search":
            for r in data.get("results") or []:
                if isinstance(r, dict) and r.get("url"):
                    self.add(
                        str(r["url"]),
                        title=str(r.get("title") or ""),
                        tool="web_search",
                        snippet=str(r.get("snippet") or ""),
                    )
        elif tool_name == "fetch_url":
            url = str(args.get("url") or data.get("url") or "").strip()
            if url:
                self.add(url, title=str(data.get("title") or ""),
                         tool="fetch_url", read=True)
        return len(self.items) - before

    # -- presentation ----------------------------------------------------
    def as_marked_list(self) -> str:
        """Numbered block fed back to the model so it can cite `[n]`."""
        lines: list[str] = []
        for s in self.items:
            state = "read" if s.read else "snippet"
            snippet = f" — {s.snippet[:220]}" if s.snippet else ""
            lines.append(
                f"[{s.index}] {s.title} — {s.url} ({s.tool}, {state}){snippet}"
            )
        return "\n".join(lines)

    def prompt_block(self) -> str:
        """System message text: the evidence the answer must be based on."""
        if not self.items:
            return (
                "BROWSING RESULT: no usable web evidence was retrieved. Do NOT "
                "invent sources or cite numbers. Say plainly that the browser "                "returned nothing, and answer only from what is verifiable."
            )
        return (
            "SOURCES collected by the browser tools (numbered). Base any "
            "external fact on them and cite inline with the marker [n] right "
            "after the sentence it supports. Never cite a number that is not "
            "listed here, and never present model knowledge as a cited fact.\n\n"
            + self.as_marked_list()
        )

    # -- verification ----------------------------------------------------
    def find_citations(self, answer: str) -> tuple[list[int], list[int]]:
        """Return (cited indexes, invalid indexes) found in `answer`."""
        cited: set[int] = set()
        invalid: set[int] = set()
        for m in _CITE_RE.finditer(answer or ""):
            for num in re.split(r"[,;-]", m.group(1)):
                num = num.strip()
                if not num.isdigit():
                    continue
                i = int(num)
                if 1 <= i <= len(self.items):
                    cited.add(i)
                else:
                    invalid.add(i)
        return sorted(cited), sorted(invalid)

    def report(self, answer: str) -> dict[str, Any]:
        """Verification summary stored on the message and shown in the UI.

        status:
          ``"cited"``     — sources exist and the answer cites them.
          ``"appended"``  — model forgot; a Sources block was injected.
          ``"no-evidence"`` — browser produced nothing → nothing to cite.
          ``"na"``        — run used no browser tool at all (no web claim).
        """
        if not self.items:
            return {
                "total": 0, "cited": [], "uncited": [], "invalid": [],
                "status": "no-evidence",
                "detail": "Browser belum mengembalikan hasil apa pun — jawaban "
                          "ini tidak punya bukti web.",
            }
        cited, invalid = self.find_citations(answer or "")
        for i in cited:
            self.items[i - 1].cited = True
        uncited = [s.index for s in self.items if not s.cited]
        status = "cited" if cited else "appended"
        return {
            "total": len(self.items),
            "cited": cited,
            "uncited": uncited,
            "invalid": invalid,
            "status": status,
            "detail": (
                f"{len(cited)}/{len(self.items)} sumber dikutip inline."
                if cited else
                "Model tidak menyisipkan marker [n]; daftar Sumber ditambahkan "
                "agar jawaban tetap dapat diverifikasi."
            ),
        }

    def sources_markdown(self, cited_only: bool = False) -> str:
        items = [s for s in self.items if not cited_only or s.cited]
        if not items:
            return ""
        lines = ["", "", "## Sumber", ""]
        for s in items:
            mark = "✓ dikutip" if s.cited else "tidak dikutip"
            title = s.title if s.title and s.title != s.url else s.url
            lines.append(f"{s.index}. [{title}]({s.url}) — {s.tool}, {mark}")
        return "\n".join(lines)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.items]


def finalize_answer(answer: str, registry: SourceRegistry) -> tuple[str, dict[str, Any]]:
    """Guarantee the answer ends with a verifiable source list.

    Returns ``(answer, citation_report)``. The model's inline markers are kept
    as written; if it cited nothing, the numbered Sources block alone still
    makes the claim checkable. Out-of-range markers are reported, not hidden.
    """
    text = (answer or "").strip()
    if not registry.items:
        return text, registry.report(text)
    report = registry.report(text)
    if report["status"] == "appended":
        text = f"{text}\n{registry.sources_markdown()}".strip()
        report = registry.report(text)
        report["status"] = "appended"
    else:
        # Every listed source should also be reachable in one place, even when
        # the model cited only some of them.
        uncited = report["uncited"]
        if uncited:
            text = f"{text}\n{registry.sources_markdown()}".strip()
            report = registry.report(text)
            report["status"] = "cited"
            report["uncited"] = uncited
    return text, report
