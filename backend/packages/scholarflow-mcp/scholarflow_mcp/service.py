from __future__ import annotations

import asyncio

from scholarflow_mcp.dedup import deduplicate_records
from scholarflow_mcp.models import LiteratureSearchResult, PaperRecord, ProviderStatus, SourceRef
from scholarflow_mcp.providers.base import ScholarlyProvider


class LiteratureSearchService:
    def __init__(self, *, providers: list[ScholarlyProvider], provider_timeout_seconds: float = 20.0) -> None:
        self._providers = providers
        self._provider_timeout_seconds = provider_timeout_seconds

    async def search(
        self,
        query: str,
        *,
        max_results: int = 20,
        candidates_per_provider: int | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
    ) -> LiteratureSearchResult:
        query = " ".join(query.split())
        if not query:
            raise ValueError("query must not be empty")
        if not 1 <= max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")
        candidate_limit = candidates_per_provider or max_results
        if not 1 <= candidate_limit <= 50:
            raise ValueError("candidates_per_provider must be between 1 and 50")
        if from_year is not None and to_year is not None and from_year > to_year:
            raise ValueError("from_year must be less than or equal to to_year")

        tasks = [
            asyncio.wait_for(
                provider.search(query, limit=candidate_limit, from_year=from_year, to_year=to_year),
                timeout=self._provider_timeout_seconds,
            )
            for provider in self._providers
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        raw_records: list[PaperRecord] = []
        statuses: list[ProviderStatus] = []
        for provider, outcome in zip(self._providers, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                statuses.append(
                    ProviderStatus(
                        provider=provider.name,
                        status="error",
                        record_count=0,
                        error=f"{type(outcome).__name__}: {outcome}",
                    )
                )
                continue
            for rank, record in enumerate(outcome, start=1):
                record.sources = [SourceRef(record.provider, record.provider_id, record.landing_page_url, rank)]
                raw_records.append(record)
            statuses.append(ProviderStatus(provider=provider.name, status="ok", record_count=len(outcome)))

        deduplicated = deduplicate_records(raw_records)
        for record in deduplicated.records:
            record.fused_relevance_score = round(
                sum(1 / (60 + source.rank) for source in record.sources if source.rank is not None),
                8,
            )
        ranked_records = sorted(
            deduplicated.records,
            key=lambda record: (-(record.fused_relevance_score or 0), record.title.casefold()),
        )
        return LiteratureSearchResult(
            query=query,
            records=ranked_records[:max_results],
            provider_status=statuses,
            total_raw_records=len(raw_records),
            unique_before_limit=len(deduplicated.records),
            duplicates_removed=deduplicated.duplicates_removed,
        )
