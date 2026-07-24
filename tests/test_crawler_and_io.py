"""Tests for the crawler orchestration, config, writers, and fulltext slicing."""

from __future__ import annotations

import io
import json

from archive_crawler.config import Database, get_database, load_databases
from archive_crawler.crawler import Crawler
from archive_crawler.fulltext import _slice_introduction, _html_to_text
from archive_crawler.models import Author, Paper
from archive_crawler.sources.base import Source
from archive_crawler.writers import write_csv, write_json, write_jsonl


class StubSource(Source):
    name = "stub"

    def __init__(self, papers):
        self._papers = papers  # skip base __init__ (no session needed)

    def search(self, query=None, *, venue=None, year_from=None, year_to=None, limit=None):
        yield from self._papers


def _paper(title, doi=None, year=2020):
    return Paper(title=title, doi=doi, year=year, authors=[Author("A. Uthor")])


def test_crawler_dedups_by_doi(monkeypatch):
    from archive_crawler import crawler as crawler_mod

    papers = [_paper("P1", "10.1/x"), _paper("P1 dup", "10.1/X"), _paper("P2", "10.2/y")]
    db = Database(key="k", label="L", source="stub")
    monkeypatch.setattr(crawler_mod, "get_source", lambda name, **kw: StubSource(papers))

    out = list(Crawler(db).crawl())
    assert [p.title for p in out] == ["P1", "P2"]  # duplicate DOI dropped


def test_crawler_respects_limit(monkeypatch):
    from archive_crawler import crawler as crawler_mod

    papers = [_paper(f"P{i}", f"10.1/{i}") for i in range(5)]
    db = Database(key="k", label="L", source="stub")
    monkeypatch.setattr(crawler_mod, "get_source", lambda name, **kw: StubSource(papers))

    assert len(list(Crawler(db).crawl(limit=2))) == 2


def test_load_and_get_database():
    dbs = load_databases()
    assert "acm_chi" in dbs
    assert get_database("ACM CHI").key == "acm_chi"  # label lookup, case-insensitive
    assert get_database("acm_chi").source == "openalex"


def test_writers_roundtrip():
    papers = [Paper(title="T", year=2021, keywords=["k1", "k2"],
                    authors=[Author("Jane Doe")], abstract="abs")]

    buf = io.StringIO()
    assert write_jsonl(papers, buf) == 1
    rec = json.loads(buf.getvalue().strip())
    assert rec["title"] == "T" and rec["authors"][0]["name"] == "Jane Doe"

    buf = io.StringIO()
    write_json(papers, buf)
    assert json.loads(buf.getvalue())[0]["abstract"] == "abs"

    buf = io.StringIO()
    write_csv(papers, buf)
    body = buf.getvalue()
    assert "Jane Doe" in body and "k1; k2" in body


def test_slice_introduction_between_headings():
    text = (
        "Title and authors\n"
        "1 Introduction\n"
        "This paper studies interfaces in depth and at length for testing.\n"
        "2 Related Work\n"
        "Others did things.\n"
    )
    intro = _slice_introduction(text, max_chars=5000)
    assert intro is not None
    assert intro.startswith("This paper studies interfaces")
    assert "Others did things" not in intro


def test_slice_introduction_returns_none_without_heading():
    assert _slice_introduction("no sections here, just prose text", max_chars=100) is None


def test_html_to_text_strips_scripts_and_tags():
    html = "<h1>Introduction</h1><script>bad()</script><p>Hello <b>world</b></p>"
    text = _html_to_text(html)
    assert "bad()" not in text
    assert "Introduction" in text and "Hello" in text
