import pytest

from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.service import LiteratureSearchService


class _Provider:
    def __init__(self, name: str, records=None, error: Exception | None = None) -> None:
        self.name = name
        self._records = records or []
        self._error = error

    async def search(self, query: str, *, limit: int, from_year: int | None, to_year: int | None):
        if self._error:
            raise self._error
        return self._records


@pytest.mark.asyncio
async def test_partial_provider_failure_returns_results_and_diagnostics() -> None:
    record = PaperRecord(
        provider="openalex",
        provider_id="W1",
        title="Evidence first agents",
        authors=["Ada Lovelace"],
        year=2026,
    )
    service = LiteratureSearchService(
        providers=[
            _Provider("openalex", [record]),
            _Provider("crossref", error=TimeoutError("provider timed out")),
        ]
    )

    result = await service.search("evidence first agents", max_results=10)

    assert len(result.records) == 1
    assert result.total_raw_records == 1
    assert result.provider_status[0].status == "ok"
    assert result.provider_status[1].status == "error"
    assert "TimeoutError" in result.provider_status[1].error


@pytest.mark.asyncio
async def test_invalid_year_range_fails_before_calling_providers() -> None:
    service = LiteratureSearchService(providers=[_Provider("openalex")])

    with pytest.raises(ValueError, match="from_year"):
        await service.search("query", from_year=2026, to_year=2025)


@pytest.mark.asyncio
async def test_reciprocal_rank_fusion_rewards_cross_provider_agreement_before_limit() -> None:
    shared_a = PaperRecord(
        provider="crossref",
        provider_id="10.1000/shared",
        doi="10.1000/shared",
        title="Shared evidence paper",
        authors=["Ada Lovelace"],
        year=2026,
    )
    shared_b = PaperRecord(
        provider="openalex",
        provider_id="W1",
        doi="10.1000/shared",
        title="Shared evidence paper",
        authors=["Ada Lovelace"],
        year=2026,
    )
    crossref_only = PaperRecord(
        provider="crossref",
        provider_id="10.1000/crossref",
        title="Crossref only paper",
        authors=["Grace Hopper"],
        year=2026,
    )
    openalex_only = PaperRecord(
        provider="openalex",
        provider_id="W2",
        title="OpenAlex only paper",
        authors=["Alan Turing"],
        year=2026,
    )
    service = LiteratureSearchService(
        providers=[
            _Provider("crossref", [crossref_only, shared_a]),
            _Provider("openalex", [openalex_only, shared_b]),
        ]
    )

    result = await service.search("evidence", max_results=2)

    assert result.unique_before_limit == 3
    assert len(result.records) == 2
    assert result.records[0].doi == "10.1000/shared"
    assert result.records[0].fused_relevance_score > result.records[1].fused_relevance_score
