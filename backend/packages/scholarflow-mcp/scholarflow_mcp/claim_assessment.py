from __future__ import annotations

from collections import Counter
from typing import Any

from scholarflow_mcp.evidence import verify_evidence_spans
from scholarflow_mcp.judge import ClaimJudge, JudgeConfig, OpenAIResponsesJudge


async def assess_claim_evidence(
    *,
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    judge: ClaimJudge | None = None,
) -> dict[str, Any]:
    """Locate evidence first, then classify semantic support using only located spans."""
    located = verify_evidence_spans(pages=pages, claims=claims)
    judge_cases: list[dict[str, Any]] = []
    deterministic_results: dict[str, dict[str, Any]] = {}
    for claim in located["claims"]:
        usable_spans = [span for span in claim["evidence_spans"] if span["status"] == "located"]
        if not usable_spans:
            deterministic_results[claim["claim_id"]] = {
                "claim_id": claim["claim_id"],
                "label": "insufficient",
                "confidence": None,
                "rationale": "No supplied evidence quote could be located, so semantic support was not assessed.",
                "cited_span_ids": [],
                "assessor": "deterministic_precheck",
            }
            continue
        judge_cases.append(
            {
                "claim_id": claim["claim_id"],
                "claim_text": claim["text"],
                "evidence_spans": [{"span_id": span["span_id"], "text": span["matched_text"]} for span in usable_spans],
            }
        )

    judge_metadata: dict[str, Any] | None = None
    judged_results: dict[str, dict[str, Any]] = {}
    if judge_cases:
        configured_judge = judge or OpenAIResponsesJudge(JudgeConfig.from_environment())
        judged = await configured_judge.classify(judge_cases)
        judge_metadata = judged.get("judge")
        for result in judged["results"]:
            judged_results[result["claim_id"]] = {**result, "assessor": "model_judge"}

    assessed_claims: list[dict[str, Any]] = []
    for claim in located["claims"]:
        verdict = deterministic_results.get(claim["claim_id"]) or judged_results[claim["claim_id"]]
        assessed_claims.append(
            {
                **claim,
                "semantic_support": verdict["label"],
                "confidence": verdict["confidence"],
                "rationale": verdict["rationale"],
                "cited_span_ids": verdict["cited_span_ids"],
                "assessor": verdict["assessor"],
            }
        )

    label_counts = Counter(claim["semantic_support"] for claim in assessed_claims)
    return {
        "claims": assessed_claims,
        "summary": {
            **located["summary"],
            "label_counts": {
                label: label_counts.get(label, 0) for label in ("supported", "contradicted", "insufficient")
            },
            "model_assessed_claims": len(judged_results),
            "precheck_insufficient_claims": len(deterministic_results),
        },
        "judge": judge_metadata,
        "scope": (
            "labels are model judgements over caller-supplied, page-located quotes; "
            "they are not independent verification of scientific truth"
        ),
    }
