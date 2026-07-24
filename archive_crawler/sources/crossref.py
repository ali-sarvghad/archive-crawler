"""Crossref metadata source (alternate backend).

Crossref (https://www.crossref.org) is the DOI registration agency for most
academic publishers. It has excellent author/year/venue coverage. Abstracts are
present only when the publisher deposits them (often as JATS XML, which we strip
to plain text) and there are no reconstructed keywords beyond ``subject`` tags.
Use OpenAlex when you need abstracts + keywords for every record; use Crossref
when you want authoritative bibliographic data or DOI-anchored results.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional

from ..models import Author, Paper
from .base import Source

API_BASE = "https://api.crossref.org"

_TAG_RE = re.compile(r"<[^>]+>")


class CrossrefSource(Source):
    name = "crossref"

    def search(
        self,
        query: Optional[str] = None,
        *,
        venue: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Paper]:
        params: dict[str, Any] = {"rows": 100, "cursor": "*"}

        filters: list[str] = []
        if year_from:
            filters.append(f"from-pub-date:{year_from}-01-01")
        if year_to:
            filters.append(f"until-pub-date:{year_to}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if query:
            params["query.bibliographic"] = query
        if venue:
            params["query.container-title"] = venue
        if self.mailto:
            params["mailto"] = self.mailto

        yielded = 0
        while True:
            page = self._get_json(f"{API_BASE}/works", params=dict(params))
            message = page.get("message") or {}
            items = message.get("items") or []
            if not items:
                break
            for item in items:
                paper = self._parse_item(item)
                # Crossref cannot filter by exact venue, so post-filter here.
                if venue and not self._venue_matches(paper.venue, venue):
                    continue
                yield paper
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            next_cursor = message.get("next-cursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _venue_matches(venue: Optional[str], wanted: str) -> bool:
        if not venue:
            return False
        return wanted.lower() in venue.lower()

    def _parse_item(self, item: dict[str, Any]) -> Paper:
        authors = []
        for a in item.get("author") or []:
            name = " ".join(p for p in (a.get("given"), a.get("family")) if p)
            affs = a.get("affiliation") or []
            authors.append(
                Author(
                    name=name or a.get("name") or "Unknown",
                    affiliation=affs[0]["name"] if affs else None,
                    orcid=a.get("ORCID"),
                )
            )

        titles = item.get("title") or []
        containers = item.get("container-title") or []

        return Paper(
            title=titles[0] if titles else "Untitled",
            authors=authors,
            year=self._extract_year(item),
            abstract=self._strip_jats(item.get("abstract")),
            keywords=item.get("subject") or [],
            doi=item.get("DOI"),
            venue=containers[0] if containers else None,
            url=item.get("URL"),
            citation_count=item.get("is-referenced-by-count"),
            source=self.name,
            source_id=item.get("DOI"),
        )

    @staticmethod
    def _extract_year(item: dict[str, Any]) -> Optional[int]:
        for key in ("published", "published-print", "published-online", "issued"):
            parts = ((item.get(key) or {}).get("date-parts") or [[None]])[0]
            if parts and parts[0]:
                return int(parts[0])
        return None

    @staticmethod
    def _strip_jats(abstract: Optional[str]) -> Optional[str]:
        if not abstract:
            return None
        text = _TAG_RE.sub("", abstract)
        text = re.sub(r"\s+", " ", text).strip()
        # Publishers often prefix the literal word "Abstract".
        return re.sub(r"^Abstract\s*", "", text) or None
