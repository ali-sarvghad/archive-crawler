"""Tests for the OpenAlex source using a fake HTTP session."""

from __future__ import annotations

from archive_crawler.sources.openalex import OpenAlexSource
from tests.conftest import FakeResponse, FakeSession

WORK = {
    "id": "https://openalex.org/W123",
    "display_name": "Designing for Delight",
    "doi": "https://doi.org/10.1145/1234.5678",
    "publication_year": 2021,
    "cited_by_count": 42,
    "abstract_inverted_index": {
        "We": [0], "study": [1], "delight": [2], "in": [3], "interfaces": [4]
    },
    "keywords": [{"display_name": "human-computer interaction", "score": 0.9}],
    "authorships": [
        {
            "author": {"display_name": "Ada Lovelace", "orcid": "https://orcid.org/0000"},
            "institutions": [{"display_name": "Analytical Engine Lab"}],
        }
    ],
    "primary_location": {
        "landing_page_url": "https://dl.acm.org/doi/10.1145/1234.5678",
        "source": {"display_name": "Proceedings of the CHI Conference"},
    },
    "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"},
    "open_access": {"oa_url": "https://example.org/paper.pdf"},
}


def _handler_factory(source_id="S999"):
    def handler(url, params):
        if url.endswith("/sources"):
            return FakeResponse({"results": [
                {"id": f"https://openalex.org/{source_id}",
                 "display_name": "Proceedings of the CHI Conference",
                 "works_count": 5000},
            ]})
        # works endpoint: first page returns the work + a next cursor,
        # second page (cursor advanced) returns nothing to stop pagination.
        if params.get("cursor") == "*":
            return FakeResponse({"results": [WORK], "meta": {"next_cursor": "END"}})
        return FakeResponse({"results": [], "meta": {"next_cursor": None}})
    return handler


def make_source():
    session = FakeSession(_handler_factory())
    return OpenAlexSource(session=session, min_interval=0, max_retries=1), session


def test_resolve_venue_picks_highest_works_count():
    src, _ = make_source()
    sid, name = src.resolve_venue("CHI")
    assert sid == "S999"
    assert "CHI" in name


def test_resolve_venue_passes_through_explicit_id():
    src, session = make_source()
    sid, _ = src.resolve_venue("S4306420956")
    assert sid == "S4306420956"
    # No /sources lookup should have happened.
    assert all(not u.endswith("/sources") for u, _ in session.calls)


def test_search_parses_all_requested_fields():
    src, _ = make_source()
    papers = list(src.search(venue="CHI", limit=10))
    assert len(papers) == 1
    p = papers[0]
    assert p.title == "Designing for Delight"
    assert p.year == 2021
    assert p.abstract == "We study delight in interfaces"
    assert p.keywords == ["human-computer interaction"]
    assert p.authors[0].name == "Ada Lovelace"
    assert p.authors[0].affiliation == "Analytical Engine Lab"
    assert p.doi == "10.1145/1234.5678"
    assert p.venue == "Proceedings of the CHI Conference"
    assert p.open_access_url == "https://example.org/paper.pdf"
    assert p.source == "openalex"


def test_search_applies_venue_filter_in_request():
    src, session = make_source()
    list(src.search(venue="CHI", year_from=2020, year_to=2022, limit=1))
    works_calls = [p for u, p in session.calls if u.endswith("/works")]
    assert works_calls, "expected a /works request"
    flt = works_calls[0]["filter"]
    assert "primary_location.source.id:S999" in flt
    assert "from_publication_date:2020-01-01" in flt
    assert "to_publication_date:2022-12-31" in flt


def test_limit_is_respected():
    # Feed two works on the first page; limit=1 must stop after one.
    def handler(url, params):
        if url.endswith("/sources"):
            return FakeResponse({"results": [
                {"id": "https://openalex.org/S1", "display_name": "x", "works_count": 1}]})
        return FakeResponse({"results": [WORK, WORK], "meta": {"next_cursor": "END"}})

    src = OpenAlexSource(session=FakeSession(handler), min_interval=0, max_retries=1)
    assert len(list(src.search(venue="CHI", limit=1))) == 1


def test_abstract_reconstruction_orders_by_position():
    assert OpenAlexSource._reconstruct_abstract(
        {"b": [1], "a": [0], "c": [2]}
    ) == "a b c"
    assert OpenAlexSource._reconstruct_abstract(None) is None
