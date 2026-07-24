"""High-level crawler orchestrator.

Ties together a :class:`~archive_crawler.config.Database`, a
:class:`~archive_crawler.sources.base.Source` backend, optional full-text
introduction extraction, and de-duplication into a single stream of papers.
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from .config import Database
from .fulltext import extract_introduction
from .models import Paper
from .sources import get_source

logger = logging.getLogger("archive_crawler")


class Crawler:
    def __init__(
        self,
        database: Database,
        *,
        mailto: Optional[str] = None,
        fetch_fulltext: bool = False,
        dedup: bool = True,
    ) -> None:
        self.database = database
        self.fetch_fulltext = fetch_fulltext
        self.dedup = dedup
        self.source = get_source(database.source, mailto=mailto)

    def crawl(
        self,
        query: Optional[str] = None,
        *,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Paper]:
        """Yield papers for the configured database, honouring overrides."""
        db = self.database
        query = query or db.default_query
        year_from = year_from if year_from is not None else db.year_from
        year_to = year_to if year_to is not None else db.year_to

        logger.info(
            "Crawling %s via %s (venue=%r, years=%s-%s, limit=%s)",
            db.label, db.source, db.venue, year_from, year_to, limit,
        )

        seen: set[str] = set()
        emitted = 0
        for paper in self.source.search(
            query,
            venue=db.venue,
            year_from=year_from,
            year_to=year_to,
            limit=None if self.dedup else limit,
        ):
            if self.dedup:
                key = paper.dedup_key()
                if key in seen:
                    continue
                seen.add(key)

            if self.fetch_fulltext and paper.open_access_url and not paper.introduction:
                paper.introduction = extract_introduction(
                    paper.open_access_url, session=self.source.session
                )
                if paper.introduction:
                    logger.debug("Extracted introduction for %r", paper.title)

            yield paper
            emitted += 1
            if limit is not None and emitted >= limit:
                return
