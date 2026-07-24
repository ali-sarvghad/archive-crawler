"""Best-effort extraction of the Introduction section from open-access text.

Full-text introductions are only obtainable when a paper is open access, so
this module operates purely on the ``open_access_url`` that OpenAlex provides.
It downloads the PDF or HTML, extracts plain text, and heuristically slices out
the "Introduction" section. When anything fails (paywall, scanned image PDF,
unusual layout) it returns ``None`` and the caller leaves ``introduction`` unset
rather than guessing.

PDF parsing uses ``pypdf`` if installed; without it, only HTML sources yield an
introduction.
"""

from __future__ import annotations

import io
import re
from typing import Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


def _load_pdf_reader():
    """Lazily import pypdf so the optional dependency never affects startup.

    Returns the ``PdfReader`` class, or ``None`` if pypdf is missing or its
    native backend is broken (which can surface as a low-level PanicException,
    a BaseException rather than an Exception).
    """
    try:
        from pypdf import PdfReader
    except BaseException:  # noqa: BLE001 - degrade gracefully, never crash.
        return None
    return PdfReader

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

# Heading that starts the introduction (optionally numbered: "1 Introduction").
_INTRO_START_RE = re.compile(
    r"(?im)^\s*(?:\d+[.\s]*)?(introduction|1\s+introduction)\s*$"
)
# Any of the headings that typically follow the introduction.
_NEXT_SECTION_RE = re.compile(
    r"(?im)^\s*(?:\d+[.\s]*)?"
    r"(related work|background|motivation|methods?|methodology|approach|"
    r"materials and methods|preliminaries|the system|design|"
    r"2\s+\w+)\s*$"
)


def extract_introduction(
    url: str,
    *,
    session: Optional["requests.Session"] = None,
    timeout: float = 30.0,
    max_chars: int = 12000,
) -> Optional[str]:
    """Download ``url`` and return its Introduction section, or ``None``."""
    if requests is None:
        return None
    sess = session or requests.Session()
    try:
        resp = sess.get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception:  # noqa: BLE001 - best effort by design.
        return None

    content_type = resp.headers.get("Content-Type", "").lower()
    is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")

    if is_pdf:
        text = _pdf_to_text(resp.content)
    else:
        text = _html_to_text(resp.text)

    if not text:
        return None
    return _slice_introduction(text, max_chars=max_chars)


# -- extraction helpers ----------------------------------------------------
def _pdf_to_text(data: bytes) -> Optional[str]:
    PdfReader = _load_pdf_reader()
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(io.BytesIO(data))
        # The introduction is near the front; first few pages are enough.
        pages = reader.pages[:6]
        return "\n".join(page.extract_text() or "" for page in pages)
    except Exception:  # noqa: BLE001
        return None


def _html_to_text(html: str) -> str:
    html = _SCRIPT_STYLE_RE.sub(" ", html)
    # Preserve block boundaries so headings land on their own line.
    html = re.sub(r"(?i)</(p|div|h[1-6]|section|br)>", "\n", html)
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _slice_introduction(text: str, *, max_chars: int) -> Optional[str]:
    start_match = _INTRO_START_RE.search(text)
    if not start_match:
        return None
    start = start_match.end()

    end_match = _NEXT_SECTION_RE.search(text, start)
    end = end_match.start() if end_match else start + max_chars

    intro = text[start:end].strip()
    intro = re.sub(r"\s+", " ", intro)
    if len(intro) < 50:  # too short to be a real introduction
        return None
    return intro[:max_chars]
