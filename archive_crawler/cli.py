"""Command-line interface for the archive crawler."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from .config import get_database, load_databases
from .crawler import Crawler
from .writers import WRITERS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="archive-crawler",
        description="Scrape scholarly paper metadata (abstract, intro, keywords, "
        "authors, year) from a venue you define, e.g. ACM CHI.",
    )
    p.add_argument(
        "-d", "--database",
        help="Database key or label from the config (e.g. 'acm_chi' or 'ACM CHI').",
    )
    p.add_argument(
        "-q", "--query",
        help="Optional free-text search within the venue (title/abstract).",
    )
    p.add_argument("--year-from", type=int, help="Earliest publication year (inclusive).")
    p.add_argument("--year-to", type=int, help="Latest publication year (inclusive).")
    p.add_argument("-n", "--limit", type=int, help="Maximum number of papers to fetch.")
    p.add_argument(
        "-o", "--output", default="-",
        help="Output file path, or '-' for stdout (default).",
    )
    p.add_argument(
        "-f", "--format", choices=sorted(WRITERS), default="jsonl",
        help="Output format (default: jsonl).",
    )
    p.add_argument(
        "--config", help="Path to a databases.yaml/.json file (defaults to bundled)."
    )
    p.add_argument(
        "--source",
        help="Override the backend for an ad-hoc crawl (e.g. 'openalex', 'crossref').",
    )
    p.add_argument(
        "--venue",
        help="Ad-hoc venue name when not using --database (used with --source).",
    )
    p.add_argument(
        "--mailto",
        help="Contact email for the API 'polite pool' (recommended; faster + kinder).",
    )
    p.add_argument(
        "--fulltext", action="store_true",
        help="Best-effort: extract the Introduction from open-access full text.",
    )
    p.add_argument(
        "--no-dedup", action="store_true", help="Do not de-duplicate by DOI/title."
    )
    p.add_argument(
        "--list-databases", action="store_true", help="List configured databases and exit."
    )
    p.add_argument("-v", "--verbose", action="count", default=0, help="-v info, -vv debug.")
    return p


def _resolve_database(args) -> "object":
    from .config import Database

    if args.database:
        return get_database(args.database, args.config)
    if args.venue:
        return Database(
            key="adhoc",
            label=args.venue,
            source=args.source or "openalex",
            venue=args.venue,
        )
    raise SystemExit(
        "error: specify --database, or --venue (optionally with --source). "
        "Use --list-databases to see configured targets."
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    level = logging.WARNING - min(args.verbose, 2) * 10
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")

    if args.list_databases:
        for key, db in sorted(load_databases(args.config).items()):
            print(f"{key:14s} {db.label:24s} source={db.source} venue={db.venue!r}")
        return 0

    database = _resolve_database(args)
    if args.source:
        database.source = args.source

    crawler = Crawler(
        database,
        mailto=args.mailto,
        fetch_fulltext=args.fulltext,
        dedup=not args.no_dedup,
    )

    papers = crawler.crawl(
        query=args.query,
        year_from=args.year_from,
        year_to=args.year_to,
        limit=args.limit,
    )

    writer = WRITERS[args.format]
    if args.output == "-":
        count = writer(papers, sys.stdout)
    else:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            count = writer(papers, fh)

    logging.getLogger("archive_crawler").info("Wrote %d papers", count)
    if args.output != "-":
        print(f"Wrote {count} papers to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
