"""Metadata source backends."""

from __future__ import annotations

from typing import Type

from .base import Source, SourceError
from .crossref import CrossrefSource
from .openalex import OpenAlexSource

#: Registry mapping backend name -> Source class.
SOURCES: dict[str, Type[Source]] = {
    OpenAlexSource.name: OpenAlexSource,
    CrossrefSource.name: CrossrefSource,
}


def get_source(name: str, **kwargs) -> Source:
    """Instantiate a source by name (e.g. ``"openalex"``)."""
    try:
        cls = SOURCES[name]
    except KeyError:
        available = ", ".join(sorted(SOURCES))
        raise SourceError(f"Unknown source {name!r}. Available: {available}") from None
    return cls(**kwargs)


__all__ = ["Source", "SourceError", "OpenAlexSource", "CrossrefSource", "SOURCES", "get_source"]
