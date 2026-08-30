from __future__ import annotations

import html
import re
from typing import Any

import httpx

from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.normalization import normalize_arxiv_id, normalize_doi

_TAG = re.compile(r"<[^>]+>")


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _values(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _date(item: dict[str, Any]) -> tuple[str | None, int | None]:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if not parts or not parts[0]:
            continue
        values = parts[0]
        if values[0] is None:
            continue
        year = int(values[0])
        month = int(values[1]) if len(values) > 1 and values[1] is not None else 1
        day = int(values[2]) if len(values) > 2 and values[2] is not None else 1
        return f"{year:04d}-{month:02d}-{day:02d}", year
    return None, None


def _authors(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for author in item.get("author", []):
        name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
        if name:
            values.append(name)
    return values


def _abstract(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(html.unescape(_TAG.sub(" ", value)).split()) or None


def _arxiv_id(item: dict[str, Any]) -> str | None:
    candidates = [*_values(item.get("alternative-id")), *_values(item.get("archive"))]
    for candidate in candidates:
        normalized = normalize_arxiv_id(str(candidate))
        if normalized:
            return normalized
    return None


def _is_retracted(item: dict[str, Any]) -> bool | None:
    relation = item.get("relation") or {}
    if relation.get("is-retracted-by"):
        return True
    if item.get("subtype") == "retraction":
        return True
    updates = _values(item.get("update-to"))
    if any(isinstance(update, dict) and update.get("type") == "retraction" for update in updates):
        return True
    return None


class CrossrefProvider:
    name = "crossref"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        contact_email: str | None = None,
        endpoint: str = "https://api.crossref.org",
    ) -> None:
        self._client = client
        self._contact_email = contact_email
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
            "query.bibliographic": query,
            "rows": limit,
        }
        filters: list[str] = []
        if from_year is not None:
            filters.append(f"from-pub-date:{from_year}-01-01")
        if to_year is not None:
            filters.append(f"until-pub-date:{to_year}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if self._contact_email:
            params["mailto"] = self._contact_email

        response = await self._client.get(f"{self._endpoint}/works", params=params)
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        return [self._map_work(item) for item in items if _first(item.get("title"))]

    def _map_work(self, item: dict[str, Any]) -> PaperRecord:
        published_date, year = _date(item)
        doi = normalize_doi(item.get("DOI"))
        return PaperRecord(
            provider=self.name,
            provider_id=doi or str(item.get("URL", "")),
            title=str(_first(item.get("title"))),
            authors=_authors(item),
            year=year,
            published_date=published_date,
            doi=doi,
            arxiv_id=_arxiv_id(item),
            abstract=_abstract(item.get("abstract")),
            venue=_first(item.get("container-title")),
            cited_by_count=item.get("is-referenced-by-count"),
            publication_type=item.get("type"),
            landing_page_url=item.get("URL"),
            is_retracted=_is_retracted(item),
        )
