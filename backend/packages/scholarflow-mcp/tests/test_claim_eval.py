import pytest

from scholarflow_mcp.claim_eval import evaluate_claim_predictions


def test_evaluates_three_way_predictions_and_penalizes_missing_items() -> None:
    gold = [
        {"case_id": "s1", "label": "supported"},
        {"case_id": "s2", "label": "supported"},
        {"case_id": "c1", "label": "contradicted"},
        {"case_id": "c2", "label": "contradicted"},
        {"case_id": "i1", "label": "insufficient"},
        {"case_id": "i2", "label": "insufficient"},
    ]
    predictions = [
        {"case_id": "s1", "label": "supported"},
        {"case_id": "s2", "label": "contradicted"},
        {"case_id": "c1", "label": "contradicted"},
        {"case_id": "c2", "label": "contradicted"},
        {"case_id": "i1", "label": "insufficient"},
    ]

    result = evaluate_claim_predictions(gold, predictions)

    assert result["case_count"] == 6
    assert result["prediction_count"] == 5
    assert result["missing_predictions"] == 1
    assert result["coverage"] == pytest.approx(5 / 6)
    assert result["accuracy"] == pytest.approx(4 / 6)
    assert result["confusion_matrix"]["supported"]["contradicted"] == 1
    assert result["confusion_matrix"]["insufficient"]["missing"] == 1
    assert len(result["gold_sha256"]) == 64


def test_rejects_unknown_prediction_ids_and_invalid_labels() -> None:
    gold = [{"case_id": "case-1", "label": "supported"}]
    with pytest.raises(ValueError, match="unknown case IDs"):
        evaluate_claim_predictions(gold, [{"case_id": "other", "label": "supported"}])
    with pytest.raises(ValueError, match="label must be one of"):
        evaluate_claim_predictions(gold, [{"case_id": "case-1", "label": "maybe"}])
