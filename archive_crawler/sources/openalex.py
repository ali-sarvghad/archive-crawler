"""OpenAlex metadata source.

OpenAlex (https://openalex.org) is a free, open catalog of scholarly works.
It is the default backend because it returns every field the crawler targets:
abstract (as an inverted index we reconstruct), keywords/concepts, authors,
publication year, venue, and an open-access URL when one exists. No API key is
required; supplying a ``mailto`` opts into the faster "polite pool".
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional

from ..models import Author, Paper
from .base import Source, SourceError

API_BASE = "https://api.openalex.org"


class OpenAlexSource(Source):
    name = "openalex"

    # -- public API --------------------------------------------------------
    def resolve_venue(self, venue: str) -> tuple[Optional[str], str]:
        """Resolve a free-text venue name to an OpenAlex source id.

        Returns ``(source_id, display_name)``. If ``venue`` already looks like
        an OpenAlex source id (e.g. ``S4306420956`` or a full URL), it is used
        verbatim. Otherwise the sources endpoint is searched and the highest
        works-count match is chosen.
        """
        vid = venue.rsplit("/", 1)[-1]
        if re.fullmatch(r"S\d+", vid):
            return vid, venue

        data = self._get_json(
            f"{API_BASE}/sources",
            params=self._with_mailto({"search": venue, "per-page": 25}),
        )
        results = data.get("results") or []
        if not results:
            raise SourceError(f"No OpenAlex venue matched {venue!r}")
        # Prefer the most-published matching source.
        best = max(results, key=lambda s: s.get("works_count", 0))
        return best["id"].rsplit("/", 1)[-1], best.get("display_name", venue)

    def search(
        self,
        query: Optional[str] = None,
        *,
        venue: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Paper]:
        filters: list[str] = []

        if venue:
            source_id, _ = self.resolve_venue(venue)
            filters.append(f"primary_location.source.id:{source_id}")
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")

        params: dict[str, Any] = {
            "per-page": 200,
            "cursor": "*",
        }
        if filters:
            params["filter"] = ",".join(filters)
        if query:
            params["search"] = query

        yielded = 0
        while True:
            page = self._get_json(
                f"{API_BASE}/works", params=self._with_mailto(dict(params))
            )
            results = page.get("results") or []
            if not results:
                break
            for work in results:
                yield self._parse_work(work)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            next_cursor = (page.get("meta") or {}).get("next_cursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor

    # -- helpers -----------------------------------------------------------
    def _with_mailto(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.mailto:
            params.setdefault("mailto", self.mailto)
        return params

    def _parse_work(self, work: dict[str, Any]) -> Paper:
        authors = []
        for a in work.get("authorships") or []:
            author = a.get("author") or {}
            institutions = a.get("institutions") or []
            affiliation = institutions[0]["display_name"] if institutions else None
            authors.append(
                Author(
                    name=author.get("display_name") or "Unknown",
                    affiliation=affiliation,
                    orcid=author.get("orcid"),
                )
            )

        keywords = [
            kw.get("display_name")
            for kw in (work.get("keywords") or [])
            if kw.get("display_name")
        ]
        # Fall back to concepts if the newer keywords field is absent.
        if not keywords:
            keywords = [
                c.get("display_name")
                for c in (work.get("concepts") or [])
                if c.get("display_name") and (c.get("score") or 0) >= 0.3
            ]

        primary = work.get("primary_location") or {}
        source_meta = primary.get("source") or {}
        best_oa = work.get("best_oa_location") or {}
        oa_url = (
            (work.get("open_access") or {}).get("oa_url")
            or best_oa.get("pdf_url")
            or best_oa.get("landing_page_url")
        )

        return Paper(
            title=work.get("display_name") or work.get("title") or "Untitled",
            authors=authors,
            year=work.get("publication_year"),
            abstract=self._reconstruct_abstract(work.get("abstract_inverted_index")),
            keywords=keywords,
            doi=self._clean_doi(work.get("doi")),
            venue=source_meta.get("display_name"),
            url=primary.get("landing_page_url") or work.get("id"),
            open_access_url=oa_url,
            citation_count=work.get("cited_by_count"),
            source=self.name,
            source_id=work.get("id"),
        )

    @staticmethod
    def _clean_doi(doi: Optional[str]) -> Optional[str]:
        if not doi:
            return None
        return doi.replace("https://doi.org/", "").strip() or None

    @staticmethod
    def _reconstruct_abstract(inverted: Optional[dict[str, list[int]]]) -> Optional[str]:
        """Rebuild plain-text abstract from OpenAlex's inverted index."""
        if not inverted:
            return None
        positions: list[tuple[int, str]] = []
        for word, idxs in inverted.items():
            for i in idxs:
                positions.append((i, word))
        if not positions:
            return None
        positions.sort(key=lambda p: p[0])
        return " ".join(word for _, word in positions)
