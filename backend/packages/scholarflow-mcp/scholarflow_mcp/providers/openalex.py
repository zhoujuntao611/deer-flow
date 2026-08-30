from __future__ import annotations

from typing import Any

import httpx

from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.normalization import normalize_openalex_id


def _restore_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positions = [(position, word) for word, offsets in index.items() for position in offsets]
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


class OpenAlexProvider:
    name = "openalex"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        api_key: str | None = None,
        endpoint: str = "https://api.openalex.org",
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")

    async def search(
        self,
        query: str,
        *,
        limit: int,
        from_year: int | None,
        to_year: int | None,
    ) -> list[PaperRecord]:
        params: dict[str, str | int] = {
            "search": query,
            "per_page": limit,
            "sort": "relevance_score:desc",
        }
        filters: list[str] = []
        if from_year is not None:
            filters.append(f"from_publication_date:{from_year}-01-01")
        if to_year is not None:
            filters.append(f"to_publication_date:{to_year}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if self._api_key:
            params["api_key"] = self._api_key

        response = await self._client.get(f"{self._endpoint}/works", params=params)
        response.raise_for_status()
        payload = response.json()
        return [self._map_work(work) for work in payload.get("results", []) if work.get("title")]

    def _map_work(self, work: dict[str, Any]) -> PaperRecord:
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        openalex_id = normalize_openalex_id(work.get("id"))
        return PaperRecord(
            provider=self.name,
            provider_id=openalex_id or str(work.get("id", "")),
            title=work["title"],
            authors=[
                authorship["author"]["display_name"]
                for authorship in work.get("authorships", [])
                if authorship.get("author", {}).get("display_name")
            ],
            year=work.get("publication_year"),
            published_date=work.get("publication_date"),
            doi=work.get("doi"),
            openalex_id=openalex_id,
            abstract=_restore_abstract(work.get("abstract_inverted_index")),
            venue=source.get("display_name"),
            cited_by_count=work.get("cited_by_count"),
            publication_type=work.get("type"),
            landing_page_url=location.get("landing_page_url") or work.get("doi"),
            pdf_url=location.get("pdf_url"),
            is_retracted=work.get("is_retracted"),
        )
