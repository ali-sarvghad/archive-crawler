"""Base class shared by all metadata sources (backends)."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional

try:  # requests is the only hard runtime dependency for the sources.
    import requests
except ImportError:  # pragma: no cover - surfaced clearly at runtime.
    requests = None  # type: ignore[assignment]

from ..models import Paper


class SourceError(RuntimeError):
    """Raised when a source cannot fulfil a request."""


class Source(ABC):
    """Abstract metadata source.

    A source knows how to talk to one scholarly database/API and yield
    :class:`~archive_crawler.models.Paper` records for a query, optionally
    scoped to a particular venue (e.g. ACM CHI).
    """

    #: Human-facing name of the backend, e.g. ``"openalex"``.
    name: str = "base"

    def __init__(
        self,
        *,
        mailto: Optional[str] = None,
        min_interval: float = 0.1,
        timeout: float = 30.0,
        max_retries: int = 4,
        session: Optional["requests.Session"] = None,
    ) -> None:
        if requests is None and session is None:  # pragma: no cover
            raise SourceError(
                "The 'requests' package is required. Install with: pip install requests"
            )
        self.mailto = mailto
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self._last_request_ts = 0.0

    # -- polite HTTP helper ------------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def _get_json(self, url: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """GET a URL and return parsed JSON, with polite throttling + retries."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise SourceError(f"retryable status {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - broad by design for retry.
                last_exc = exc
                backoff = min(2 ** attempt, 16)
                time.sleep(backoff)
        raise SourceError(f"GET {url} failed after {self.max_retries} attempts: {last_exc}")

    # -- interface ---------------------------------------------------------
    @abstractmethod
    def search(
        self,
        query: Optional[str] = None,
        *,
        venue: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Paper]:
        """Yield papers matching the query/venue/year constraints.

        Implementations should stream results (via API cursor pagination) and
        stop once ``limit`` records have been produced.
        """
        raise NotImplementedError
