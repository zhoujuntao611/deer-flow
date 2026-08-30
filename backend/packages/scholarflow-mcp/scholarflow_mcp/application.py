from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import httpx

from scholarflow_mcp.providers import ArxivProvider, CrossrefProvider, OpenAlexProvider
from scholarflow_mcp.service import LiteratureSearchService

SUPPORTED_PROVIDERS = ("arxiv", "crossref", "openalex")


def timeout_seconds() -> float:
    raw = os.getenv("SCHOLARFLOW_HTTP_TIMEOUT_SECONDS", "20")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("SCHOLARFLOW_HTTP_TIMEOUT_SECONDS must be numeric") from exc
    if not 1 <= value <= 120:
        raise ValueError("SCHOLARFLOW_HTTP_TIMEOUT_SECONDS must be between 1 and 120")
    return value


def normalize_provider_names(providers: Sequence[str] | None) -> list[str]:
    selected = [provider.casefold() for provider in (providers or SUPPORTED_PROVIDERS)]
    unknown = sorted(set(selected) - set(SUPPORTED_PROVIDERS))
    if unknown:
        raise ValueError(f"unknown providers: {', '.join(unknown)}")
    return list(dict.fromkeys(selected))


async def run_search(
    query: str,
    *,
    max_results: int = 20,
    from_year: int | None = None,
    to_year: int | None = None,
    providers: Sequence[str] | None = None,
) -> dict[str, Any]:
    selected = normalize_provider_names(providers)
    timeout = timeout_seconds()
    headers = {"User-Agent": "ScholarFlow/0.2 (multi-source scholarly metadata search)"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        available = {
            "arxiv": ArxivProvider(
                client=client,
                endpoint=os.getenv("SCHOLARFLOW_ARXIV_ENDPOINT", "https://export.arxiv.org/api/query"),
            ),
            "crossref": CrossrefProvider(
                client=client,
                contact_email=os.getenv("SCHOLARFLOW_CONTACT_EMAIL"),
                endpoint=os.getenv("SCHOLARFLOW_CROSSREF_ENDPOINT", "https://api.crossref.org"),
            ),
            "openalex": OpenAlexProvider(
                client=client,
                api_key=os.getenv("SCHOLARFLOW_OPENALEX_API_KEY"),
                endpoint=os.getenv("SCHOLARFLOW_OPENALEX_ENDPOINT", "https://api.openalex.org"),
            ),
        }
        service = LiteratureSearchService(
            providers=[available[name] for name in selected],
            provider_timeout_seconds=timeout,
        )
        result = await service.search(
            query,
            max_results=max_results,
            from_year=from_year,
            to_year=to_year,
        )
    return result.to_dict()
