import json

import httpx
import pytest

from scholarflow_mcp.normalization import normalize_arxiv_id
from scholarflow_mcp.providers.arxiv import ArxivProvider
from scholarflow_mcp.providers.crossref import CrossrefProvider
from scholarflow_mcp.providers.openalex import OpenAlexProvider


def test_arxiv_normalization_accepts_known_forms_without_mining_unrelated_dois() -> None:
    assert normalize_arxiv_id("https://arxiv.org/pdf/2501.01234v2.pdf?download=1") == "2501.01234"
    assert normalize_arxiv_id("10.48550/arXiv.2501.01234") == "2501.01234"
    assert normalize_arxiv_id("10.1234/archive.2501.01234") is None


@pytest.mark.asyncio
async def test_arxiv_uses_term_conjunction_instead_of_overly_strict_phrase() -> None:
    feed = b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search_query"] == 'all:"GNSS" AND all:"spoofing" AND all:"UAV"'
        assert request.url.params["sortBy"] == "relevance"
        return httpx.Response(200, content=feed)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await ArxivProvider(client=client).search("GNSS spoofing UAV", limit=5, from_year=None, to_year=None)

    assert records == []


@pytest.mark.asyncio
async def test_openalex_maps_inverted_abstract_and_identifiers() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "doi": "https://doi.org/10.1000/example",
                "title": "Verified research",
                "publication_year": 2025,
                "publication_date": "2025-04-03",
                "authorships": [
                    {"author": {"display_name": "Ada Lovelace"}},
                    {"author": {"display_name": "Grace Hopper"}},
                ],
                "primary_location": {
                    "landing_page_url": "https://example.org/paper",
                    "pdf_url": "https://example.org/paper.pdf",
                    "source": {"display_name": "Journal of Evidence"},
                },
                "abstract_inverted_index": {"Results": [2], "Reliable": [0], "are": [1]},
                "cited_by_count": 12,
                "type": "article",
            }
        ]
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "verified agents"
        assert request.url.params["sort"] == "relevance_score:desc"
        assert request.url.params["filter"] == "from_publication_date:2024-01-01,to_publication_date:2025-12-31"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await OpenAlexProvider(client=client).search(
            "verified agents", limit=10, from_year=2024, to_year=2025
        )

    assert len(records) == 1
    assert records[0].openalex_id == "W123"
    assert records[0].doi == "10.1000/example"
    assert records[0].abstract == "Reliable are Results"
    assert records[0].authors == ["Ada Lovelace", "Grace Hopper"]


@pytest.mark.asyncio
async def test_crossref_maps_dates_authors_and_arxiv_relation() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/example",
                    "title": ["Verified research"],
                    "author": [{"given": "Ada", "family": "Lovelace"}],
                    "published-print": {"date-parts": [[2025, 4, 3]]},
                    "container-title": ["Journal of Evidence"],
                    "abstract": "<jats:p>Structured abstract.</jats:p>",
                    "URL": "https://doi.org/10.1000/example",
                    "is-referenced-by-count": 7,
                    "type": "journal-article",
                    "alternative-id": ["arXiv:2501.01234"],
                }
            ]
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query.bibliographic"] == "verified agents"
        assert request.url.params["filter"] == "from-pub-date:2025-01-01,until-pub-date:2025-12-31"
        return httpx.Response(200, content=json.dumps(payload).encode(), headers={"content-type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await CrossrefProvider(client=client).search("verified agents", limit=5, from_year=2025, to_year=2025)

    assert len(records) == 1
    assert records[0].doi == "10.1000/example"
    assert records[0].arxiv_id == "2501.01234"
    assert records[0].published_date == "2025-04-03"
    assert records[0].abstract == "Structured abstract."


@pytest.mark.asyncio
async def test_crossref_accepts_scalar_archive_metadata() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.48550/arXiv.2501.01234",
                    "title": ["A preprint record"],
                    "archive": "arXiv:2501.01234",
                }
            ]
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await CrossrefProvider(client=client).search("preprint", limit=1, from_year=None, to_year=None)

    assert records[0].arxiv_id == "2501.01234"
    assert records[0].is_retracted is None


@pytest.mark.asyncio
async def test_crossref_preserves_unknown_retraction_state_and_detects_relation() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/retracted",
                    "title": ["A retracted work"],
                    "relation": {"is-retracted-by": [{"id-type": "doi", "id": "10.1000/notice"}]},
                }
            ]
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await CrossrefProvider(client=client).search("retracted", limit=1, from_year=None, to_year=None)

    assert records[0].is_retracted is True


@pytest.mark.asyncio
async def test_crossref_skips_null_date_parts_instead_of_failing_provider() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/unknown-date",
                    "title": ["A work with incomplete deposit metadata"],
                    "published-print": {"date-parts": [[None]]},
                    "issued": {"date-parts": [[2024, None, None]]},
                }
            ]
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await CrossrefProvider(client=client).search("work", limit=1, from_year=None, to_year=None)

    assert records[0].published_date == "2024-01-01"
    assert records[0].year == 2024
