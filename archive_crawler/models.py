"""Data models for crawled papers."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Author:
    """A single author of a paper."""

    name: str
    affiliation: Optional[str] = None
    orcid: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class Paper:
    """A scholarly paper with the metadata fields we care about.

    The five fields explicitly requested by the user are: ``abstract``,
    ``introduction``, ``keywords``, ``authors`` and ``year``. Everything else
    is supporting metadata that makes the records useful and de-duplicable.
    """

    title: str
    authors: list[Author] = field(default_factory=list)
    year: Optional[int] = None
    abstract: Optional[str] = None
    introduction: Optional[str] = None
    keywords: list[str] = field(default_factory=list)

    # Supporting / provenance metadata.
    doi: Optional[str] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    open_access_url: Optional[str] = None
    citation_count: Optional[int] = None
    source: Optional[str] = None  # which backend produced this record
    source_id: Optional[str] = None  # backend-native identifier

    def dedup_key(self) -> str:
        """A stable key used to de-duplicate records across sources."""
        if self.doi:
            return f"doi:{self.doi.lower().strip()}"
        return f"title:{self.title.lower().strip()}::{self.year}"

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["authors"] = [a.to_dict() for a in self.authors]
        return data

    # Convenience for CSV/flat export.
    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": "; ".join(a.name for a in self.authors),
            "year": self.year,
            "keywords": "; ".join(self.keywords),
            "abstract": self.abstract or "",
            "introduction": self.introduction or "",
            "doi": self.doi or "",
            "venue": self.venue or "",
            "url": self.url or "",
            "open_access_url": self.open_access_url or "",
            "citation_count": self.citation_count if self.citation_count is not None else "",
            "source": self.source or "",
        }
