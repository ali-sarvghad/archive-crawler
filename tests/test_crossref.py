"""Tests for the Crossref source."""

from __future__ import annotations

from archive_crawler.sources.crossref import CrossrefSource
from tests.conftest import FakeResponse, FakeSession

ITEM = {
    "DOI": "10.1145/9999",
    "title": ["A Study of Widgets"],
    "container-title": ["Proceedings of the CHI Conference on Human Factors"],
    "author": [
        {"given": "Grace", "family": "Hopper", "affiliation": [{"name": "Navy"}]},
    ],
    "issued": {"date-parts": [[2019, 5]]},
    "abstract": "<jats:p>Abstract We examine widgets.</jats:p>",
    "subject": ["Human-Computer Interaction"],
    "URL": "https://doi.org/10.1145/9999",
    "is-referenced-by-count": 7,
}


def make_source(item=ITEM):
    def handler(url, params):
        if params.get("cursor") == "*":
            return FakeResponse({"message": {"items": [item], "next-cursor": "END"}})
        return FakeResponse({"message": {"items": [], "next-cursor": None}})
    return CrossrefSource(session=FakeSession(handler), min_interval=0, max_retries=1)


def test_parse_fields_and_strip_jats():
    src = make_source()
    papers = list(src.search(venue="CHI", limit=5))
    assert len(papers) == 1
    p = papers[0]
    assert p.title == "A Study of Widgets"
    assert p.year == 2019
    assert p.abstract == "We examine widgets."  # JATS + leading "Abstract" removed
    assert p.authors[0].name == "Grace Hopper"
    assert p.authors[0].affiliation == "Navy"
    assert p.keywords == ["Human-Computer Interaction"]
    assert p.doi == "10.1145/9999"
    assert p.source == "crossref"


def test_venue_post_filter_excludes_nonmatches():
    other = dict(ITEM, **{"container-title": ["Some Other Journal"]})
    src = make_source(other)
    assert list(src.search(venue="CHI", limit=5)) == []
