"""Foundry IQ retrieval client (stub).

Production: calls Azure AI Search via the Foundry IQ surface to retrieve
relevant chunks from the knowledge base (competitor URLs, bootstrap playbooks).

Current state: returns mock context from local knowledge/ directory. Swap in
the real Azure AI Search SDK when the index is provisioned.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse


KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def retrieve(query: str, top_k: int = 3, source_filter: Optional[str] = None) -> List[dict]:
    """Retrieve relevant chunks for a query.

    Returns a list of dicts: [{content, source, score}, ...]
    """
    # In live mode, this would call:
    #   from azure.search.documents import SearchClient
    #   results = search_client.search(query, top=top_k, ...)
    #
    # For now, scan local knowledge/ files and do a naive keyword match.
    results = []
    if not KNOWLEDGE_DIR.exists():
        return results

    query_lower = query.lower()
    keywords = set(query_lower.split())

    for fpath in sorted(KNOWLEDGE_DIR.glob("**/*.md")) + sorted(KNOWLEDGE_DIR.glob("**/*.txt")):
        if source_filter and source_filter.lower() not in fpath.name.lower():
            continue
        try:
            text = fpath.read_text(errors="ignore")
        except Exception:
            continue
        # Naive relevance: count keyword overlaps in the first 2000 chars.
        snippet = text[:2000]
        snippet_lower = snippet.lower()
        hits = sum(1 for kw in keywords if kw in snippet_lower)
        if hits > 0:
            results.append({
                "content": snippet[:800],
                "source": str(fpath.relative_to(KNOWLEDGE_DIR)),
                "score": hits / max(len(keywords), 1),
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def ingest_url(url: str, max_bytes: int = 400_000, timeout: float = 6.0) -> Optional[str]:
    """Fetch a public company URL and return readable plain text.

    Used to seed the OrgDesigner from any company's homepage. Dependency-free
    (stdlib only) so the repo stays forkable. Returns None on any failure so
    callers fall back to a brief seeded from the URL itself.

    Security: this fetches a user-supplied URL server-side, so it guards against
    SSRF - only http/https, public hosts only (no localhost, private ranges,
    link-local, or the cloud metadata endpoint).
    """
    if not _is_public_http_url(url):
        return None

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DungeonOrgDesigner/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        # nosec B310 - scheme + host validated by _is_public_http_url above.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in ctype and "text" not in ctype:
                return None
            raw = resp.read(max_bytes)
    except (urllib.error.URLError, socket.timeout, ValueError, OSError):
        return None

    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        return None

    return _html_to_text(text) or None


def brief_from_url(url: str) -> str:
    """Turn a company URL into a short brief seed for the OrgDesigner.

    Falls back to a generic brief built from the domain when the page can't be
    fetched (offline, blocked, or non-HTML), so the demo never hard-fails.
    """
    text = ingest_url(url)
    host = urlparse(url).netloc or url
    if text:
        snippet = text[:1200].strip()
        return f"Company homepage ({host}):\n{snippet}"
    return (
        f"A company operating at {host}. The homepage could not be read, so design "
        f"a sensible default org for a small digital-first business at this domain."
    )


# ---------------------------------------------------------------------------
# Internal helpers (SSRF guard + HTML stripping)
# ---------------------------------------------------------------------------

_BLOCK_HOST_SUFFIXES = (".internal", ".local", ".localhost")


def _is_public_http_url(url: str) -> bool:
    """Allow only http/https URLs that resolve to public IP addresses."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    host_lower = host.lower()
    if host_lower == "localhost" or host_lower.endswith(_BLOCK_HOST_SUFFIXES):
        return False

    # Resolve every address the host maps to; reject if ANY is non-public.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return False
    if not infos:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    return True


def _html_to_text(html_doc: str) -> str:
    """Strip scripts/styles/tags and collapse whitespace - no extra deps."""
    # Drop non-content blocks entirely.
    cleaned = re.sub(r"(?is)<(script|style|noscript|template|svg)\b.*?</\1>", " ", html_doc)
    # Prefer the <title> + meta description as a strong signal up front.
    title_match = re.search(r"(?is)<title\b[^>]*>(.*?)</title>", cleaned)
    desc_match = re.search(
        r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        cleaned,
    )
    lead = " ".join(
        html.unescape(m.group(1)).strip()
        for m in (title_match, desc_match)
        if m and m.group(1).strip()
    )
    body = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    body = html.unescape(body)
    body = re.sub(r"\s+", " ", body).strip()
    combined = f"{lead}. {body}" if lead else body
    return combined[:8000]

