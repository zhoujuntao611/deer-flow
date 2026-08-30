import json

import pytest

from scholarflow_mcp.known_item_benchmark import _load_cases, evaluate_suite


@pytest.mark.asyncio
async def test_known_item_benchmark_reports_honest_scope_and_metrics(tmp_path) -> None:
    suite = tmp_path / "suite.json"
    suite.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "known-paper",
                        "query": "known paper",
                        "targets": [{"doi": "10.1000/known"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    async def fake_search(*args, **kwargs):
        return {
            "records": [
                {"doi": "10.1000/other", "arxiv_id": None, "openalex_id": None},
                {"doi": "https://doi.org/10.1000/KNOWN", "arxiv_id": None, "openalex_id": None},
            ],
            "provider_status": [
                {"provider": "crossref", "status": "ok", "record_count": 2, "error": None},
                {"provider": "openalex", "status": "error", "record_count": 0, "error": "offline"},
            ],
            "total_raw_records": 3,
            "unique_before_limit": 2,
            "unique_records": 2,
            "duplicates_removed": 1,
        }

    result = await evaluate_suite(suite, max_results=10, searcher=fake_search)

    assert result["metric_scope"] == "known-item retrieval; not full relevance recall"
    assert result["hit_rate_at_k"] == 1.0
    assert result["mean_reciprocal_rank_at_k"] == 0.5
    assert result["provider_availability"] == 0.5
    assert result["deduplication_rate"] == pytest.approx(1 / 3)
    assert result["cases"][0]["rank"] == 2


def test_known_item_suite_rejects_targets_without_supported_identifiers(tmp_path) -> None:
    suite = tmp_path / "invalid.json"
    suite.write_text(
        json.dumps({"cases": [{"id": "invalid", "query": "query", "targets": [{"title": "paper"}]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no supported target identifier"):
        _load_cases(suite)
