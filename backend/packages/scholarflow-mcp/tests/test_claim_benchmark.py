from typing import Any

import pytest

from scholarflow_mcp.claim_benchmark import run_claim_benchmark


class GoldEchoJudge:
    def __init__(self, labels: dict[str, str]) -> None:
        self.labels = labels

    async def classify(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "results": [
                {
                    "claim_id": case["claim_id"],
                    "label": self.labels[case["claim_id"]],
                    "confidence": 1.0,
                    "rationale": "Test fixture verdict.",
                    "cited_span_ids": [case["evidence_spans"][0]["span_id"]],
                }
                for case in cases
            ],
            "judge": {"provider": "fixture", "model": "gold-echo"},
        }


@pytest.mark.asyncio
async def test_runs_batched_claim_benchmark_and_reports_scope() -> None:
    cases = [
        {
            "case_id": f"case-{index}",
            "claim_text": f"Claim {index}",
            "evidence_spans": [{"span_id": f"span-{index}", "text": f"Evidence {index}"}],
            "label": label,
        }
        for index, label in enumerate(("supported", "contradicted", "insufficient"))
    ]
    labels = {case["case_id"]: case["label"] for case in cases}

    result = await run_claim_benchmark({"metadata": {"dataset": "fixture"}, "cases": cases}, GoldEchoJudge(labels))

    assert result["metrics"]["macro_f1"] == 1.0
    assert result["metrics"]["coverage"] == 1.0
    assert "retrieval and PDF extraction are not measured" in result["metrics"]["metric_scope"]
    assert result["metadata"]["dataset"]["dataset"] == "fixture"
