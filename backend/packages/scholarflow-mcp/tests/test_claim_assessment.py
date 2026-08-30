from typing import Any

import pytest

from scholarflow_mcp.claim_assessment import assess_claim_evidence


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
                    "confidence": 0.9,
                    "rationale": "The located evidence directly states the claim.",
                    "cited_span_ids": [case["evidence_spans"][0]["span_id"]],
                }
                for case in cases
            ],
            "judge": {"provider": "fake", "model": "test"},
        }


@pytest.mark.asyncio
async def test_locates_before_semantic_assessment_and_preserves_provenance() -> None:
    judge = FakeJudge()
    result = await assess_claim_evidence(
        pages=[{"document_id": "paper-1", "page_number": 2, "text": "Accuracy reached 94%."}],
        claims=[
            {
                "claim_id": "claim-1",
                "text": "Accuracy reached 94%.",
                "evidence_spans": [{"span_id": "span-a", "document_id": "paper-1", "page_number": 2, "quote": "94%"}],
            }
        ],
        judge=judge,
    )

    assert judge.cases[0]["evidence_spans"] == [{"span_id": "span-a", "text": "94%"}]
    claim = result["claims"][0]
    assert claim["semantic_support"] == "supported"
    assert claim["cited_span_ids"] == ["span-a"]
    assert claim["assessor"] == "model_judge"
    assert result["summary"]["model_assessed_claims"] == 1
    assert "not independent verification" in result["scope"]


@pytest.mark.asyncio
async def test_unlocated_evidence_is_insufficient_without_calling_judge() -> None:
    result = await assess_claim_evidence(
        pages=[{"document_id": "paper-1", "page_number": 1, "text": "Different text."}],
        claims=[
            {
                "claim_id": "claim-1",
                "text": "A claim.",
                "evidence_spans": [{"document_id": "paper-1", "page_number": 1, "quote": "missing quote"}],
            }
        ],
    )

    claim = result["claims"][0]
    assert claim["semantic_support"] == "insufficient"
    assert claim["confidence"] is None
    assert claim["assessor"] == "deterministic_precheck"
    assert result["judge"] is None
    assert result["summary"]["precheck_insufficient_claims"] == 1
