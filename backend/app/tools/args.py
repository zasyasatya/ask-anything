"""Tolerant coercion of tool arguments.

Real models — especially local ones and small ones behind a gateway — rarely
emit a perfect JSON object for a tool call. The failure modes seen in practice:

  * arguments arrive as a *string*: ``{"nodes": "[{\\"id\\": \\"a\\"}]"}``
  * the JSON is wrapped in a ```json fence or in prose
  * single quotes instead of double quotes, trailing commas, ``True``/``None``
  * a nested field is a JSON string instead of an array/object
  * the call was cut off by ``max_tokens`` (truncated JSON)

None of those should make a tool "not work": they are repaired here, once, so
every tool (and both providers) benefits. When repair is impossible the raw
text is preserved under ``_raw`` and the caller reports it honestly instead of
silently running with empty arguments.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)
#: `{...}` / `[...]` — shortest span that still parses is chosen by the caller.
_SPAN_RE = re.compile(r"[\{\[].*[\}\]]", re.S)


def _strip_prefixes(text: str) -> str:
    text = (text or "").strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    # `arguments = {...}` / `tool_call: {...}` style prefixes
    text = re.sub(r"^[A-Za-z_][\w ]{0,30}\s*[:=]\s*(?=[\{\[])", "", text)
    return text.strip()


def _balanced_spans(text: str) -> list[str]:
    """Every ``{...}``/``[...]`` substring, outermost-first, balanced."""
    spans: list[str] = []
    stack: list[str] = []
    start = -1
    in_str: str | None = None
    escaped = False
    pairs = {"{": "}", "[": "]"}
    for i, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            continue
        if ch in pairs:
            if not stack:
                start = i
            stack.append(pairs[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack and start >= 0:
                spans.append(text[start:i + 1])
                start = -1
    return spans


def _fix_loose(text: str) -> str:
    """Best-effort fixes for JSON that a human/model would call "almost JSON"."""
    out = text.strip()
    out = out.replace("\u201c", '"').replace("\u201d", '"')
    out = out.replace("\u2018", "'").replace("\u2019", "'")
    # trailing commas before a closing bracket
    out = re.sub(r",\s*([\}\]])", r"\1", out)
    # python literals
    out = re.sub(r"\bTrue\b", "true", out)
    out = re.sub(r"\bFalse\b", "false", out)
    out = re.sub(r"\bNone\b", "null", out)
    # single-quoted keys/values → double quotes (only when no double quote is
    # already used as the string delimiter around them)
    if '"' not in out and "'" in out:
        out = out.replace("'", '"')
    return out


def parse_loose(text: str) -> Any | None:
    """Parse JSON-ish text. Returns None when nothing sensible can be read."""
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    raw = _strip_prefixes(str(text))
    if not raw:
        return None
    candidates = [raw]
    candidates.extend(_balanced_spans(raw))
    m = _SPAN_RE.search(raw)
    if m:
        candidates.append(m.group(0))
    for candidate in candidates:
        for variation in (candidate, _fix_loose(candidate)):
            try:
                return json.loads(variation)
            except ValueError:
                pass
            # Python dict literals (`{'a': 1}`) — a very common local-model shape
            try:
                value = ast.literal_eval(variation)
            except (ValueError, SyntaxError, MemoryError, TypeError):
                continue
            if isinstance(value, (dict, list)):
                return value
    return None


def repair_arguments(raw: Any) -> dict[str, Any]:
    """Turn whatever the model produced into a dict of tool arguments.

    Unparseable input keeps the original text under ``_raw`` so the trace shows
    exactly what arrived (and the tool can say "argument tidak terbaca").
    """
    if isinstance(raw, dict):
        return {k: _deep(v) for k, v in raw.items()}
    if raw is None:
        return {}
    parsed = parse_loose(raw)
    if isinstance(parsed, dict):
        return {k: _deep(v) for k, v in parsed.items()}
    if isinstance(parsed, list):
        # A bare array of tool calls is handled by the provider; inside one tool
        # call we keep it as a positional `items` list.
        return {"items": [_deep(v) for v in parsed]}
    text = str(raw).strip()
    return {"_raw": text} if text else {}


def _deep(value: Any) -> Any:
    """Recursively un-stringify JSON embedded in a JSON string field."""
    if isinstance(value, dict):
        return {k: _deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep(v) for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in ("{", "["):
            parsed = parse_loose(stripped)
            if isinstance(parsed, (dict, list)):
                return _deep(parsed)
    return value


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (str, int, float)):
        return str(value).strip() or default
    return default


def as_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        m = re.search(r"-?\d+", text)
        return int(m.group(0)) if m else default
    except (TypeError, ValueError):
        return default


def as_list(value: Any) -> list[Any]:
    """Coerce a field that should be a list (JSON string, single item, mapping)."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        parsed = parse_loose(value)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        text = value.strip()
        if not text:
            return []
        # `"a, b, c"` or one-line `"A -> B"` list
        parts = [p.strip() for p in re.split(r"[;\n]", text) if p.strip()]
        return parts if len(parts) > 1 else [text]
    return [value]


def as_mapping(value: Any) -> dict[str, Any]:
    """Coerce a node list that arrived as ``{"A": "Label A", …}``."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = parse_loose(value)
        if isinstance(parsed, dict):
            return parsed
    return {}


def first_key(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    """First present, non-empty value among `keys` (aliases models invent)."""
    for key in keys:
        if key in mapping:
            value = mapping[key]
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            return value
    return default
