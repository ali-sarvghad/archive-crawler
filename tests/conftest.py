"""Shared test fixtures: a fake requests.Session that replays canned JSON."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200, headers: Optional[dict] = None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
        if isinstance(payload, (bytes, str)):
            self.content = payload.encode() if isinstance(payload, str) else payload
            self.text = payload.decode() if isinstance(payload, bytes) else payload
        else:
            self.text = json.dumps(payload)
            self.content = self.text.encode()

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """A stand-in for requests.Session driven by a handler callable.

    ``handler(url, params) -> FakeResponse`` decides each response. Every call
    is recorded in ``self.calls`` for assertions.
    """

    def __init__(self, handler: Callable[[str, Optional[dict]], FakeResponse]):
        self._handler = handler
        self.calls: list[tuple[str, Optional[dict]]] = []

    def get(self, url: str, params: Optional[dict] = None, timeout: Optional[float] = None):
        self.calls.append((url, params))
        return self._handler(url, params)
