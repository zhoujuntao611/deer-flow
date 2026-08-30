from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import platform
import sys
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from scholarflow_mcp.application import SUPPORTED_PROVIDERS, run_search
from scholarflow_mcp.normalization import normalize_arxiv_id, normalize_doi, normalize_openalex_id
from scholarflow_mcp.output import write_utf8_stdout

SearchFunction = Callable[..., Awaitable[dict[str, Any]]]


def _package_version() -> str:
    try:
        return version("scholarflow-mcp")
    except PackageNotFoundError:
        return "uninstalled"


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("known-item suite must contain a non-empty 'cases' list")

    seen: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("every benchmark case must have a unique non-empty id")
        seen.add(case_id)
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError(f"case {case_id!r} must have a non-empty query")
        targets = case.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ValueError(f"case {case_id!r} must have at least one target identifier")
        if not any(
            target.get(field)
            for target in targets
            if isinstance(target, dict)
            for field in ("doi", "arxiv_id", "openalex_id")
        ):
            raise ValueError(f"case {case_id!r} has no supported target identifier")
    return cases


def _normalized_ids(value: dict[str, Any]) -> dict[str, str | None]:
    return {
        "doi": normalize_doi(value.get("doi")),
        "arxiv_id": normalize_arxiv_id(value.get("arxiv_id")),
        "openalex_id": normalize_openalex_id(value.get("openalex_id")),
    }


def _matches_target(record: dict[str, Any], targets: list[dict[str, Any]]) -> bool:
    record_ids = _normalized_ids(record)
    for target in targets:
        target_ids = _normalized_ids(target)
        if any(record_ids[field] and record_ids[field] == target_ids[field] for field in record_ids):
            return True
    return False


def _target_rank(records: list[dict[str, Any]], targets: list[dict[str, Any]]) -> int | None:
    return next(
        (rank for rank, record in enumerate(records, start=1) if _matches_target(record, targets)),
        None,
    )


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


async def evaluate_suite(
    path: Path,
    *,
    max_results: int = 10,
    providers: Sequence[str] | None = None,
    searcher: SearchFunction = run_search,
) -> dict[str, Any]:
    cases = _load_cases(path)
    case_results: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    successful_provider_calls = 0
    attempted_provider_calls = 0
    total_raw_records = 0
    total_duplicates_removed = 0

    for case in cases:
        started = perf_counter()
        try:
            result = await searcher(
                case["query"],
                max_results=max_results,
                from_year=case.get("from_year"),
                to_year=case.get("to_year"),
                providers=providers,
            )
            latency_ms = round((perf_counter() - started) * 1000, 3)
            rank = _target_rank(result["records"], case["targets"])
            statuses = result["provider_status"]
            attempted_provider_calls += len(statuses)
            successful_provider_calls += sum(status["status"] == "ok" for status in statuses)
            total_raw_records += result["total_raw_records"]
            total_duplicates_removed += result["duplicates_removed"]
            case_results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "hit_at_k": rank is not None,
                    "rank": rank,
                    "latency_ms": latency_ms,
                    "provider_status": statuses,
                    "raw_records": result["total_raw_records"],
                    "unique_before_limit": result["unique_before_limit"],
                    "duplicates_removed": result["duplicates_removed"],
                }
            )
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000, 3)
            case_results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "hit_at_k": False,
                    "rank": None,
                    "latency_ms": latency_ms,
                    "provider_status": [],
                    "raw_records": 0,
                    "unique_before_limit": 0,
                    "duplicates_removed": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        latencies_ms.append(latency_ms)

    hits = sum(case["hit_at_k"] for case in case_results)
    reciprocal_rank_sum = sum(1 / case["rank"] for case in case_results if case["rank"] is not None)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scholarflow_version": _package_version(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "suite": path.name,
        "suite_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "metric_scope": "known-item retrieval; not full relevance recall",
        "query_count": len(case_results),
        "max_results": max_results,
        "providers": list(providers or SUPPORTED_PROVIDERS),
        "hit_count": hits,
        "hit_rate_at_k": round(hits / len(case_results), 6),
        "mean_reciprocal_rank_at_k": round(reciprocal_rank_sum / len(case_results), 6),
        "provider_availability": round(
            successful_provider_calls / attempted_provider_calls if attempted_provider_calls else 0.0,
            6,
        ),
        "deduplication_rate": round(
            total_duplicates_removed / total_raw_records if total_raw_records else 0.0,
            6,
        ),
        "latency_ms": {
            "p50": round(median(latencies_ms), 3),
            "p95": round(_percentile(latencies_ms, 0.95), 3),
        },
        "cases": case_results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a live known-item scholarly retrieval benchmark. This is not a full recall evaluation."
    )
    parser.add_argument(
        "--suite",
        type=Path,
        default=Path(__file__).parents[1] / "benchmarks" / "known_item_queries.json",
    )
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--providers", nargs="+", choices=SUPPORTED_PROVIDERS)
    parser.add_argument("--min-hit-rate", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 0 <= args.min_hit_rate <= 1:
        parser.error("--min-hit-rate must be between 0 and 1")

    result = asyncio.run(
        evaluate_suite(
            args.suite,
            max_results=args.max_results,
            providers=args.providers,
        )
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    return 0 if result["hit_rate_at_k"] >= args.min_hit_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
