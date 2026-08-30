from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scholarflow_mcp.claim_eval import evaluate_claim_predictions
from scholarflow_mcp.judge import MAX_JUDGE_CLAIMS, ClaimJudge, JudgeConfig, OpenAIResponsesJudge
from scholarflow_mcp.output import write_utf8_stdout


async def run_claim_benchmark(dataset: dict[str, Any], judge: ClaimJudge) -> dict[str, Any]:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("benchmark dataset must contain a non-empty cases list")
    predictions: list[dict[str, Any]] = []
    judge_runs: list[dict[str, Any] | None] = []
    for start in range(0, len(cases), MAX_JUDGE_CLAIMS):
        batch = cases[start : start + MAX_JUDGE_CLAIMS]
        judge_cases = [
            {
                "claim_id": case.get("case_id", case.get("claim_id")),
                "claim_text": case.get("claim_text"),
                "evidence_spans": case.get("evidence_spans"),
            }
            for case in batch
        ]
        judged = await judge.classify(judge_cases)
        judge_runs.append(judged.get("judge"))
        predictions.extend(
            {
                "case_id": result["claim_id"],
                "label": result["label"],
                "confidence": result["confidence"],
                "rationale": result["rationale"],
                "cited_span_ids": result["cited_span_ids"],
            }
            for result in judged["results"]
        )
    return {
        "metadata": {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dataset": dataset.get("metadata", {}),
            "judge_runs": judge_runs,
        },
        "metrics": evaluate_claim_predictions(cases, predictions),
        "predictions": predictions,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a manual model judge over claim-evidence benchmark cases.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-macro-f1", type=float)
    args = parser.parse_args(argv)

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    judge = OpenAIResponsesJudge(JudgeConfig.from_environment())
    result = asyncio.run(run_claim_benchmark(dataset, judge))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    if args.min_macro_f1 is not None and result["metrics"]["macro_f1"] < args.min_macro_f1:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
