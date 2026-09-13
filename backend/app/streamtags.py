"""Split a token stream into tagged blocks (`<think>...`, blok tool-call).

Local models do not give us structured tool calls the way an OpenAI-compatible
server does: they emit the call as *text* inside a tag. Because tokens arrive in
arbitrary chunks, a tag can be split across two chunks (`...<tool` + `_call>...`),
so the parser holds back anything that might still turn out to be the start of
a tag instead of leaking half a tag into the answer.
"""
from __future__ import annotations

TEXT = "text"

# Nama tag disusun dari potongan: penulisan literal penanda penutup tool-call
# di dalam sebuah file dibaca sebagai akhir tool-call oleh tooling yang
# menuliskan file itu, sehingga file-nya terpotong.
_L, _R = chr(60), chr(62)
_TOOL_TAG = "tool" + "_call"

#: blok yang dipakai inference lokal: reasoning + pemanggilan tool
THINK_TAGS = ("<think>", "</think>")
TOOL_CALL_TAGS = (f"{_L}{_TOOL_TAG}{_R}", f"{_L}/{_TOOL_TAG}{_R}")


class TagStreamParser:
    """Feed text, get back `[(kind, chunk), …]` with `kind` = `"text"` or a tag."""

    def __init__(self, blocks: dict[str, tuple[str, str]]) -> None:
        #: kind -> (opening tag, closing tag)
        self.blocks = blocks
        self.mode = TEXT
        self.hold = ""

    def feed(self, text: str) -> list[tuple[str, str]]:
        self.hold += text
        out: list[tuple[str, str]] = []
        while True:
            if self.mode == TEXT:
                # earliest opening tag wins
                best: tuple[int, str, str, str] | None = None
                for kind, (open_tag, close_tag) in self.blocks.items():
                    i = self.hold.find(open_tag)
                    if i >= 0 and (best is None or i < best[0]):
                        best = (i, kind, open_tag, close_tag)
                if best is not None:
                    i, kind, open_tag, _ = best
                    if i > 0:
                        out.append((TEXT, self.hold[:i]))
                    self.hold = self.hold[i + len(open_tag):]
                    self.mode = kind
                    continue
                cut = self._safe_cut(self.hold,
                                     [t[0] for t in self.blocks.values()])
                if cut > 0:
                    out.append((TEXT, self.hold[:cut]))
                    self.hold = self.hold[cut:]
                break

            close_tag = self.blocks[self.mode][1]
            i = self.hold.find(close_tag)
            if i >= 0:
                if i > 0:
                    out.append((self.mode, self.hold[:i]))
                self.hold = self.hold[i + len(close_tag):]
                self.mode = TEXT
                continue
            cut = self._safe_cut(self.hold, [close_tag])
            if cut > 0:
                out.append((self.mode, self.hold[:cut]))
                self.hold = self.hold[cut:]
            break
        return out

    def flush(self) -> list[tuple[str, str]]:
        """Emit whatever is left (an unterminated tag stays a block: a tool call
        cut off by `max_tokens` must not be rendered as answer text)."""
        if not self.hold:
            return []
        out = [(self.mode, self.hold)]
        self.hold = ""
        return out

    @staticmethod
    def _safe_cut(buffer: str, tags: list[str]) -> int:
        """Length of `buffer` that cannot be the start of any tag."""
        keep = 0
        for tag in tags:
            for length in range(1, len(tag)):
                if buffer.endswith(tag[:length]):
                    keep = max(keep, length)
        return len(buffer) - keep
