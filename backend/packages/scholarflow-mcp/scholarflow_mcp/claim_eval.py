from __future__ import annotations

import hashlib
import json
from typing import Any

from scholarflow_mcp.judge import SEMANTIC_LABELS


def _case_id(value: dict[str, Any]) -> str:
    raw = value.get("case_id", value.get("claim_id"))
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("each item must contain a non-empty case_id or claim_id")
    return raw.strip()


def _label(value: dict[str, Any], *, kind: str) -> str:
    raw = value.get("label", value.get("semantic_support"))
    if raw not in SEMANTIC_LABELS:
        raise ValueError(f"{kind} label must be one of: {', '.join(SEMANTIC_LABELS)}")
    return raw


def _indexed_labels(items: Any, *, kind: str) -> dict[str, str]:
    if not isinstance(items, list) or not items:
        raise ValueError(f"{kind} items must be a non-empty list")
    indexed: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"each {kind} item must be an object")
        item_id = _case_id(item)
        if item_id in indexed:
            raise ValueError(f"duplicate {kind} case ID: {item_id}")
        indexed[item_id] = _label(item, kind=kind)
    return indexed


def evaluate_claim_predictions(gold_cases: Any, predictions: Any) -> dict[str, Any]:
    gold = _indexed_labels(gold_cases, kind="gold")
    predicted = _indexed_labels(predictions, kind="prediction")
    unknown = sorted(set(predicted) - set(gold))
    if unknown:
        raise ValueError(f"predictions contain unknown case IDs: {', '.join(unknown)}")

    confusion: dict[str, dict[str, int]] = {
        gold_label: {predicted_label: 0 for predicted_label in (*SEMANTIC_LABELS, "missing")}
        for gold_label in SEMANTIC_LABELS
    }
    correct = 0
    for case_id, gold_label in gold.items():
        predicted_label = predicted.get(case_id, "missing")
        confusion[gold_label][predicted_label] += 1
        correct += predicted_label == gold_label

    per_label: dict[str, dict[str, float | int]] = {}
    for label in SEMANTIC_LABELS:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in SEMANTIC_LABELS if other != label)
        false_negative = sum(confusion[label][other] for other in (*SEMANTIC_LABELS, "missing") if other != label)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "support": sum(confusion[label].values()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    case_count = len(gold)
    canonical_gold = json.dumps(sorted(gold.items()), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "case_count": case_count,
        "prediction_count": len(predicted),
        "missing_predictions": case_count - len(predicted),
        "coverage": len(predicted) / case_count,
        "accuracy": correct / case_count,
        "macro_precision": sum(float(per_label[label]["precision"]) for label in SEMANTIC_LABELS)
        / len(SEMANTIC_LABELS),
        "macro_recall": sum(float(per_label[label]["recall"]) for label in SEMANTIC_LABELS) / len(SEMANTIC_LABELS),
        "macro_f1": sum(float(per_label[label]["f1"]) for label in SEMANTIC_LABELS) / len(SEMANTIC_LABELS),
        "per_label": per_label,
        "confusion_matrix": confusion,
        "gold_sha256": hashlib.sha256(canonical_gold).hexdigest(),
        "metric_scope": "oracle-evidence three-way classification; retrieval and PDF extraction are not measured",
    }
