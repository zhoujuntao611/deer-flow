from pathlib import Path

from scholarflow_mcp.benchmark import _meets_thresholds, evaluate_fixture


def test_committed_synthetic_fixture_has_perfect_pairwise_score() -> None:
    fixture = Path(__file__).parents[1] / "benchmarks" / "dedup_cases.json"
    result = evaluate_fixture(fixture)

    assert result["pairwise_precision"] == 1.0
    assert result["pairwise_recall"] == 1.0
    assert result["pairwise_f1"] == 1.0
    assert result["record_count"] == 8


def test_benchmark_threshold_gate() -> None:
    result = {"pairwise_precision": 0.9, "pairwise_recall": 0.8, "pairwise_f1": 0.85}

    assert _meets_thresholds(result, min_precision=0.9, min_recall=0.8, min_f1=0.85)
    assert not _meets_thresholds(result, min_precision=0.91, min_recall=0.8, min_f1=0.85)
