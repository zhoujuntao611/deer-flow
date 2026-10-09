from typing import Any

import pytest

from scholarflow_mcp.retrieval import retrieve_claim_evidence


def test_retrieval_ranks_relevant_page_and_preserves_exact_offsets() -> None:
    relevant = (
        "Methods were compared.\nThe detector achieved 94% accuracy on held-out flights.\nThe sample had 50 runs."
    )
    result = retrieve_claim_evidence(
        pages=[
            {"document_id": "other", "page_number": 1, "text": "The weather was sunny throughout the flight."},
            {"document_id": "study", "page_number": 3, "text": relevant},
        ],
        claims=[{"claim_id": "c1", "text": "The detector achieved 94% accuracy on held-out flights."}],
        top_k=2,
        chunk_characters=80,
        chunk_overlap=10,
    )

    span = result["claims"][0]["evidence_spans"][0]
    assert span["document_id"] == "study"
    assert span["page_number"] == 3
    assert relevant[span["character_start"] : span["character_end"]] == span["quote"]
    assert "94% accuracy" in span["quote"]
    assert span["retrieval_rank"] == 1
    assert span["retrieval_score"] > 0
    assert set(span["channel_ranks"]) == {"word_bm25", "character_bm25"}


def test_chinese_query_and_zero_match_abstention() -> None:
    pages = [
        {"document_id": "a", "page_number": 1, "text": "该方法降低了无人机导航误差，室内测试平均误差为二米。"},
        {"document_id": "b", "page_number": 1, "text": "数据库备份每日凌晨执行。"},
    ]
    matching = retrieve_claim_evidence(
        pages=pages,
        claims=[{"claim_id": "cn", "text": "无人机导航误差降低"}],
    )
    assert matching["claims"][0]["evidence_spans"][0]["document_id"] == "a"

    no_match = retrieve_claim_evidence(
        pages=pages,
        claims=[{"claim_id": "none", "text": "火星地质年代"}],
    )
    assert no_match["claims"][0]["evidence_spans"] == []
    assert no_match["summary"]["claims_without_candidates"] == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"top_k": 11}, "top_k"),
        ({"chunk_characters": 50}, "chunk_characters"),
        ({"chunk_overlap": 500}, "chunk_overlap"),
    ],
)
def test_retrieval_rejects_invalid_bounds(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        retrieve_claim_evidence(
            pages=[{"document_id": "doc", "page_number": 1, "text": "Text."}],
            claims=[{"claim_id": "c1", "text": "Text."}],
            **kwargs,
        )


def test_retrieval_rejects_duplicate_claims_and_oversized_corpus() -> None:
    with pytest.raises(ValueError, match="duplicate claim_id"):
        retrieve_claim_evidence(
            pages=[],
            claims=[{"claim_id": "same", "text": "first"}, {"claim_id": "same", "text": "second"}],
        )

    with pytest.raises(ValueError, match="total page text"):
        retrieve_claim_evidence(
            pages=[{"document_id": str(index), "page_number": 1, "text": "x" * 200_000} for index in range(26)],
            claims=[],
        )
