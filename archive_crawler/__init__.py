"""archive_crawler: scrape scholarly paper metadata from a venue you define.

Fetches abstract, introduction, keywords, authors and publication year for
papers in a chosen "database" (venue) such as ACM CHI, using free scholarly
metadata APIs (OpenAlex by default, Crossref as an alternate).
"""

from __future__ import annotations

from .config import Database, get_database, load_databases
from .crawler import Crawler
from .models import Author, Paper
from .sources import CrossrefSource, OpenAlexSource, Source, get_source

__version__ = "0.1.0"

__all__ = [
    "Author",
    "Paper",
    "Crawler",
    "Database",
    "get_database",
    "load_databases",
    "Source",
    "OpenAlexSource",
    "CrossrefSource",
    "get_source",
    "__version__",
]
