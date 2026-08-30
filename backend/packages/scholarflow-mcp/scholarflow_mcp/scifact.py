from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCIFACT_SOURCE = "https://github.com/allenai/scifact"
SCIFACT_CITATION = "Wadden et al., Fact or Fiction: Verifying Scientific Claims, EMNLP 2020"
SCIFACT_LABELS = {"SUPPORT": "supported", "CONTRADICT": "contradicted"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object")
            records.append(value)
    return records


def import_scifact_cases(
    corpus_path: Path,
    claims_path: Path,
    *,
    limit: int | None = None,
    include_insufficient: bool = True,
) -> dict[str, Any]:
    """Convert a caller-downloaded SciFact split into oracle-evidence classification cases."""
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be a positive integer")
    corpus_records = _read_jsonl(corpus_path)
    corpus: dict[str, list[str]] = {}
    for record in corpus_records:
        doc_id = str(record.get("doc_id", "")).strip()
        abstract = record.get("abstract")
        if not doc_id or not isinstance(abstract, list) or any(not isinstance(item, str) for item in abstract):
            raise ValueError("each SciFact corpus record must contain doc_id and a string-list abstract")
        corpus[doc_id] = abstract

    cases: list[dict[str, Any]] = []
    for claim_record in _read_jsonl(claims_path):
        claim_id = str(claim_record.get("id", "")).strip()
        claim_text = claim_record.get("claim")
        evidence = claim_record.get("evidence")
        cited_doc_ids = claim_record.get("cited_doc_ids", [])
        if not claim_id or not isinstance(claim_text, str) or not claim_text.strip() or not isinstance(evidence, dict):
            raise ValueError("each SciFact claim must contain id, claim, and evidence")

        evidence_doc_ids: set[str] = set()
        for raw_doc_id, rationales in evidence.items():
            doc_id = str(raw_doc_id)
            evidence_doc_ids.add(doc_id)
            if doc_id not in corpus or not isinstance(rationales, list):
                raise ValueError(f"SciFact evidence references an unavailable document: {doc_id}")
            abstract = corpus[doc_id]
            for rationale_index, rationale in enumerate(rationales):
                if not isinstance(rationale, dict) or rationale.get("label") not in SCIFACT_LABELS:
                    raise ValueError(f"SciFact rationale for claim {claim_id} has an unsupported label")
                sentence_indices = rationale.get("sentences")
                if not isinstance(sentence_indices, list) or not sentence_indices:
                    raise ValueError(f"SciFact rationale for claim {claim_id} must contain sentence indices")
                spans: list[dict[str, str]] = []
                for sentence_index in sentence_indices:
                    if (
                        isinstance(sentence_index, bool)
                        or not isinstance(sentence_index, int)
                        or not 0 <= sentence_index < len(abstract)
                    ):
                        raise ValueError(f"SciFact rationale for claim {claim_id} has an invalid sentence index")
                    spans.append(
                        {
                            "span_id": f"doc-{doc_id}:sentence-{sentence_index}",
                            "text": abstract[sentence_index],
                        }
                    )
                cases.append(
                    {
                        "case_id": f"scifact:{claim_id}:{doc_id}:rationale-{rationale_index}",
                        "claim_id": f"scifact:{claim_id}:{doc_id}:rationale-{rationale_index}",
                        "claim_text": claim_text.strip(),
                        "evidence_spans": spans,
                        "label": SCIFACT_LABELS[rationale["label"]],
                        "source": {
                            "claim_id": claim_id,
                            "document_id": doc_id,
                            "sentence_indices": sentence_indices,
                            "evidence_mode": "gold_rationale",
                        },
                    }
                )

        if include_insufficient:
            for raw_doc_id in cited_doc_ids:
                doc_id = str(raw_doc_id)
                if doc_id in evidence_doc_ids or doc_id not in corpus:
                    continue
                abstract_text = " ".join(corpus[doc_id]).strip()
                if not abstract_text:
                    continue
                cases.append(
                    {
                        "case_id": f"scifact:{claim_id}:{doc_id}:no-evidence",
                        "claim_id": f"scifact:{claim_id}:{doc_id}:no-evidence",
                        "claim_text": claim_text.strip(),
                        "evidence_spans": [{"span_id": f"doc-{doc_id}:abstract", "text": abstract_text}],
                        "label": "insufficient",
                        "source": {
                            "claim_id": claim_id,
                            "document_id": doc_id,
                            "sentence_indices": [],
                            "evidence_mode": "cited_abstract_without_annotated_evidence",
                        },
                    }
                )

        if limit is not None and len(cases) >= limit:
            cases = cases[:limit]
            break

    return {
        "metadata": {
            "dataset": "SciFact",
            "source": SCIFACT_SOURCE,
            "citation": SCIFACT_CITATION,
            "case_count": len(cases),
            "include_insufficient": include_insufficient,
            "metric_scope": "oracle evidence classification; retrieval is excluded",
            "redistribution": "generated locally from user-supplied SciFact files; source data is not bundled",
        },
        "cases": cases,
    }
