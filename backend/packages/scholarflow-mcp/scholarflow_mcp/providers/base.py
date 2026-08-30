from __future__ import annotations

from typing import Protocol

from scholarflow_mcp.models import PaperRecord


class ScholarlyProvider(Protocol):
    name: str

    async def search(
        self,
        query: str,
        *,
        limit: int,
        from_year: int | None,
        to_year: int | None,
    ) -> list[PaperRecord]: ...
