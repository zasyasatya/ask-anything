"""Normalise OpenAI-compatible base URLs.

Users paste whatever the API documentation happens to show them, so all of
these spellings mean *the same server*:

    https://ai.sumopod.com
    https://ai.sumopod.com/v1
    https://ai.sumopod.com/v1/
    https://ai.sumopod.com/v1/chat/completions   ← copied from a curl example
    https://ai.sumopod.com/v1/models
    ai.sumopod.com/v1                            (no scheme)

The OpenAI wire protocol works from a **base** URL and appends the endpoint
path itself, so without normalisation pasting the full endpoint produced
`…/v1/chat/completions/chat/completions` → HTTP 404. We canonicalise once,
here, and every consumer (providers, health check, UI) agrees on the result.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

# First http(s) URL inside the pasted text (tolerates markdown links, quotes,
# trailing punctuation from a copied curl command …).
_URL_RE = re.compile(r"https?://[^\s\)\]\"'<>]+", re.IGNORECASE)

# Endpoint paths that are *not* part of the base URL and must be stripped.
_ENDPOINT_SUFFIXES = (
    "/chat/completions",
    "/chat/completion",
    "/completions",
    "/embeddings",
    "/models",
    "/chat",
)

# A trailing "v1" / "v2" / "v1beta" style segment is the API version marker.
_VERSION_SEG_RE = re.compile(r"^v\d+(?:\.\d+)?[a-z0-9_-]*$", re.IGNORECASE)

DEFAULT_VERSION_PATH = "/v1"


def normalize_openai_base_url(url: str) -> str:
    """Return the canonical base URL (`scheme://host[:port][/prefix/v1]`).

    Returns "" for empty input so callers can tell "not configured" apart.
    """
    if not url or not url.strip():
        return ""

    match = _URL_RE.search(url)
    candidate = (match.group(0) if match else url.strip())
    candidate = candidate.strip().strip(".,;")
    if "://" not in candidate:
        candidate = "https://" + candidate.lstrip("/")

    parts = urlsplit(candidate)
    if not parts.netloc:
        return candidate.rstrip("/")

    path = parts.path.rstrip("/")
    changed = True
    while changed:
        changed = False
        lowered = path.lower()
        for suffix in _ENDPOINT_SUFFIXES:
            if lowered.endswith(suffix):
                path = path[: -len(suffix)].rstrip("/")
                changed = True
                break

    segments = [s for s in path.split("/") if s]
    if not segments:
        # Bare host → assume the OpenAI default version prefix.
        path = DEFAULT_VERSION_PATH
    else:
        if _VERSION_SEG_RE.match(segments[-1]):
            # Canonical version marker (`v1`, `v1beta`, …) — lowercase it; the
            # rest of a non-versioned prefix is left exactly as typed.
            segments[-1] = segments[-1].lower()
        path = "/" + "/".join(segments)

    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def endpoint_url(base_url: str, path: str = "chat/completions") -> str:
    """Join a (possibly messy) base URL with an endpoint path."""
    return f"{normalize_openai_base_url(base_url).rstrip('/')}/{path.lstrip('/')}"


def chat_completions_url(base_url: str) -> str:
    return endpoint_url(base_url, "chat/completions")


def models_url(base_url: str) -> str:
    return endpoint_url(base_url, "models")
