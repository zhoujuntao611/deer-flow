from typing import Any

import pytest

from scholarflow_mcp.retrieval import assess_retrieved_claim_evidence


class FakeJudge:
    def __init__(self) -> None:
        self.cases: list[dict[str, Any]] = []

    async def classify(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        self.cases = cases
        return {
            "results": [
                {
                    "claim_id": case["claim_id"],
                    "label": "supported",
                    "confidence": 0.8,
                    "rationale": "The retrieved sentence supports the claim.",
                    "cited_span_ids": [case["evidence_spans"][0]["span_id"]],
                }
                for case in cases
            ],
            "judge": {"provider": "fake", "model": "test"},
        }


@pytest.mark.asyncio
async def test_retrieval_to_verification_to_judge_keeps_citation() -> None:
    judge = FakeJudge()
    text = "The detector achieved 94% accuracy on held-out flights."
    result = await assess_retrieved_claim_evidence(
        pages=[{"document_id": "study", "page_number": 2, "text": text}],
        claims=[{"claim_id": "c1", "text": "The detector achieved 94% accuracy on held-out flights."}],
        judge=judge,
    )

    span = result["claims"][0]["evidence_spans"][0]
    assert span["matched_text"] == text
    assert text[span["character_start"] : span["character_end"]] == span["matched_text"]
    assert span["retrieval_rank"] == 1
    assert result["claims"][0]["cited_span_ids"] == [span["span_id"]]
    assert result["claims"][0]["semantic_support"] == "supported"
    assert judge.cases[0]["evidence_spans"][0]["span_id"] == span["span_id"]


@pytest.mark.asyncio
async def test_no_retrieved_candidates_abstains_without_model_call() -> None:
    result = await assess_retrieved_claim_evidence(
        pages=[{"document_id": "study", "page_number": 1, "text": "Naval history of the Mediterranean."}],
        claims=[{"claim_id": "c1", "text": "量子传感器灵敏度"}],
    )
    assert result["claims"][0]["semantic_support"] == "insufficient"
    assert result["claims"][0]["assessor"] == "deterministic_precheck"
    assert result["judge"] is None
    assert result["retrieval"]["claims_without_candidates"] == 1
