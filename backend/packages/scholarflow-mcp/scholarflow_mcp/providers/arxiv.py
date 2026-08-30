from __future__ import annotations

import re
from xml.etree import ElementTree

import httpx

from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.normalization import normalize_arxiv_id

_ATOM = "{http://www.w3.org/2005/Atom}"
_QUERY_TERM = re.compile(r"[\w-]+", re.UNICODE)


def _text(element: ElementTree.Element, name: str) -> str | None:
    child = element.find(f"{_ATOM}{name}")
    return " ".join((child.text or "").split()) if child is not None and child.text else None


def _search_expression(query: str) -> str:
    terms = _QUERY_TERM.findall(query)
    if not terms:
        raise ValueError("query must contain at least one searchable term")
    return " AND ".join(f'all:"{term}"' for term in terms)


class ArxivProvider:
    name = "arxiv"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        endpoint: str = "https://export.arxiv.org/api/query",
    ) -> None:
        self._client = client
        self._endpoint = endpoint

    async def search(
        self,
        query: str,
        *,
        limit: int,
        from_year: int | None,
        to_year: int | None,
    ) -> list[PaperRecord]:
        search_query = _search_expression(query)
        if from_year is not None or to_year is not None:
            start = f"{from_year or 1900}01010000"
            end = f"{to_year or 3000}12312359"
            search_query += f" AND submittedDate:[{start} TO {end}]"
        response = await self._client.get(
            self._endpoint,
            params={
                "search_query": search_query,
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        return [self._map_entry(entry) for entry in root.findall(f"{_ATOM}entry") if _text(entry, "title")]

    def _map_entry(self, entry: ElementTree.Element) -> PaperRecord:
        entry_id = _text(entry, "id") or ""
        arxiv_id = normalize_arxiv_id(entry_id)
        published = _text(entry, "published")
        links = {
            link.attrib.get("title") or link.attrib.get("rel", ""): link.attrib.get("href")
            for link in entry.findall(f"{_ATOM}link")
        }
        authors = [_text(author, "name") or "" for author in entry.findall(f"{_ATOM}author") if _text(author, "name")]
        return PaperRecord(
            provider=self.name,
            provider_id=arxiv_id or entry_id,
            title=_text(entry, "title") or "",
            authors=authors,
            year=int(published[:4]) if published else None,
            published_date=published[:10] if published else None,
            arxiv_id=arxiv_id,
            abstract=_text(entry, "summary"),
            publication_type="preprint",
            landing_page_url=links.get("alternate") or entry_id,
            pdf_url=links.get("pdf"),
        )
