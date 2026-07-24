"""Output writers for crawled papers (JSONL, JSON, CSV)."""

from __future__ import annotations

import csv
import json
from typing import Iterable, TextIO

from .models import Paper

FLAT_FIELDS = [
    "title",
    "authors",
    "year",
    "keywords",
    "abstract",
    "introduction",
    "doi",
    "venue",
    "url",
    "open_access_url",
    "citation_count",
    "source",
]


def write_jsonl(papers: Iterable[Paper], fh: TextIO) -> int:
    """Write one JSON object per line. Streams; good for large crawls."""
    count = 0
    for paper in papers:
        fh.write(json.dumps(paper.to_dict(), ensure_ascii=False) + "\n")
        count += 1
    return count


def write_json(papers: Iterable[Paper], fh: TextIO) -> int:
    """Write a single JSON array (buffers all records in memory)."""
    records = [p.to_dict() for p in papers]
    json.dump(records, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
    return len(records)


def write_csv(papers: Iterable[Paper], fh: TextIO) -> int:
    """Write a flat CSV (nested authors/keywords joined with '; ')."""
    writer = csv.DictWriter(fh, fieldnames=FLAT_FIELDS)
    writer.writeheader()
    count = 0
    for paper in papers:
        writer.writerow(paper.to_flat_dict())
        count += 1
    return count


WRITERS = {"jsonl": write_jsonl, "json": write_json, "csv": write_csv}
