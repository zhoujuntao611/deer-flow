from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

from scholarflow_mcp.dedup import deduplicate_records, source_key
from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.output import write_utf8_stdout


def _pairs(groups: list[set[tuple[str, str]]]) -> set[frozenset[tuple[str, str]]]:
    return {frozenset(pair) for group in groups for pair in combinations(sorted(group), 2)}


def evaluate_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_records = payload["records"]
    records = [PaperRecord.from_mapping(record) for record in raw_records]
    result = deduplicate_records(records)

    expected_by_case: dict[str, set[tuple[str, str]]] = {}
    for raw, record in zip(raw_records, records, strict=True):
        expected_by_case.setdefault(raw["case_id"], set()).add((record.provider, record.provider_id))
    expected_pairs = _pairs(list(expected_by_case.values()))
    predicted_pairs = _pairs([{source_key(source) for source in record.sources} for record in result.records])

    true_positive = len(expected_pairs & predicted_pairs)
    precision = true_positive / len(predicted_pairs) if predicted_pairs else float(not expected_pairs)
    recall = true_positive / len(expected_pairs) if expected_pairs else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "fixture": str(path),
        "record_count": len(records),
        "expected_duplicate_pairs": len(expected_pairs),
        "predicted_duplicate_pairs": len(predicted_pairs),
        "pairwise_precision": round(precision, 6),
        "pairwise_recall": round(recall, 6),
        "pairwise_f1": round(f1, 6),
        "duplicates_removed": result.duplicates_removed,
    }


def _meets_thresholds(
    result: dict[str, Any],
    *,
    min_precision: float,
    min_recall: float,
    min_f1: float,
) -> bool:
    return (
        result["pairwise_precision"] >= min_precision
        and result["pairwise_recall"] >= min_recall
        and result["pairwise_f1"] >= min_f1
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ScholarFlow's deterministic paper deduplication")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parents[1] / "benchmarks" / "dedup_cases.json",
    )
    parser.add_argument("--min-precision", type=float, default=0.0)
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--min-f1", type=float, default=0.0)
    args = parser.parse_args()
    for value in (args.min_precision, args.min_recall, args.min_f1):
        if not 0 <= value <= 1:
            parser.error("benchmark thresholds must be between 0 and 1")
    result = evaluate_fixture(args.fixture)
    write_utf8_stdout(json.dumps(result, ensure_ascii=False, indent=2))
    if not _meets_thresholds(
        result,
        min_precision=args.min_precision,
        min_recall=args.min_recall,
        min_f1=args.min_f1,
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
