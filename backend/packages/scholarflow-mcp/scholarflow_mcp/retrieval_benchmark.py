from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scholarflow_mcp.output import write_utf8_stdout
from scholarflow_mcp.retrieval import retrieve_claim_evidence
from scholarflow_mcp.scifact import SCIFACT_CITATION, SCIFACT_SOURCE, _read_jsonl


def run_scifact_retrieval_benchmark(
    corpus_path: Path,
    claims_path: Path,
    *,
    top_k: int = 5,
    chunk_characters: int = 320,
    chunk_overlap: int = 40,
    limit: int | None = None,
) -> dict[str, Any]:
    """Measure gold-rationale sentence retrieval among a claim's cited abstracts."""
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be a positive integer")
    corpus: dict[str, list[str]] = {}
    for record in _read_jsonl(corpus_path):
        doc_id = str(record.get("doc_id", "")).strip()
        abstract = record.get("abstract")
        if not doc_id or not isinstance(abstract, list) or any(not isinstance(sentence, str) for sentence in abstract):
            raise ValueError("SciFact corpus records must contain doc_id and a string-list abstract")
        corpus[doc_id] = abstract

    cases: list[dict[str, Any]] = []
    for claim_record in _read_jsonl(claims_path):
        claim_id = str(claim_record.get("id", "")).strip()
        claim_text = claim_record.get("claim")
        evidence = claim_record.get("evidence")
        cited_doc_ids = claim_record.get("cited_doc_ids", [])
        if (
            not claim_id
            or not isinstance(claim_text, str)
            or not claim_text.strip()
            or not isinstance(evidence, dict)
            or not isinstance(cited_doc_ids, list)
        ):
            raise ValueError("SciFact claims must contain id, claim, cited_doc_ids, and evidence")
        if not evidence:
            continue
        selected_doc_ids = list(dict.fromkeys(str(doc_id) for doc_id in cited_doc_ids))
        uncited_gold = set(map(str, evidence)) - set(selected_doc_ids)
        if uncited_gold:
            raise ValueError(f"SciFact claim {claim_id} has gold documents outside cited_doc_ids")
        missing_documents = set(selected_doc_ids) - set(corpus)
        if missing_documents:
            raise ValueError(f"SciFact claim {claim_id} cites unavailable documents")
        pages = [
            {"document_id": doc_id, "page_number": 1, "text": "\n".join(corpus[doc_id])} for doc_id in selected_doc_ids
        ]
        if not pages:
            raise ValueError(f"SciFact claim {claim_id} has no cited abstracts")
        spans_by_mode = {
            mode: retrieve_claim_evidence(
                pages=pages,
                claims=[{"claim_id": claim_id, "text": claim_text}],
                top_k=top_k,
                chunk_characters=chunk_characters,
                chunk_overlap=chunk_overlap,
                mode=mode,
            )["claims"][0]["evidence_spans"]
            for mode in ("hybrid", "word_bm25")
        }
        for doc_id, rationales in evidence.items():
            doc_id = str(doc_id)
            if doc_id not in corpus or not isinstance(rationales, list):
                raise ValueError(f"SciFact evidence references an unavailable document: {doc_id}")
            for rationale_index, rationale in enumerate(rationales):
                sentence_indices = rationale.get("sentences") if isinstance(rationale, dict) else None
                if (
                    not isinstance(sentence_indices, list)
                    or not sentence_indices
                    or any(
                        isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(corpus[doc_id])
                        for index in sentence_indices
                    )
                ):
                    raise ValueError(f"SciFact rationale for claim {claim_id} has invalid sentence indices")
                gold_sentences = [corpus[doc_id][index].strip() for index in sentence_indices]
                first_ranks = {
                    mode: next(
                        (
                            span["retrieval_rank"]
                            for span in spans
                            if span["document_id"] == doc_id
                            and any(sentence and sentence in span["quote"] for sentence in gold_sentences)
                        ),
                        None,
                    )
                    for mode, spans in spans_by_mode.items()
                }
                complete_hits = {
                    mode: all(
                        sentence and any(span["document_id"] == doc_id and sentence in span["quote"] for span in spans)
                        for sentence in gold_sentences
                    )
                    for mode, spans in spans_by_mode.items()
                }
                cases.append(
                    {
                        "case_id": f"scifact:{claim_id}:{doc_id}:rationale-{rationale_index}",
                        "first_gold_rank": first_ranks["hybrid"],
                        "complete_rationale_hit": complete_hits["hybrid"],
                        "baseline_first_gold_rank": first_ranks["word_bm25"],
                        "baseline_complete_rationale_hit": complete_hits["word_bm25"],
                        "candidate_document_count": len(pages),
                        "retrieved_candidate_count": len(spans_by_mode["hybrid"]),
                    }
                )
                if limit is not None and len(cases) >= limit:
                    break
            if limit is not None and len(cases) >= limit:
                break
        if limit is not None and len(cases) >= limit:
            break
    if not cases:
        raise ValueError("SciFact input contains no labeled rationale cases")
    count = len(cases)
    return {
        "metadata": {
            "dataset": "SciFact",
            "source": SCIFACT_SOURCE,
            "citation": SCIFACT_CITATION,
            "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
            "claims_sha256": hashlib.sha256(claims_path.read_bytes()).hexdigest(),
            "scope": "cited-document abstract evidence retrieval, not open-corpus retrieval",
            "gold_match": "a full annotated rationale sentence appears within a retrieved text window",
            "comparison": "paired BM25 word-only ablation and BM25 word+character RRF on identical cases and chunks",
            "redistribution": "source data is user-supplied and not bundled",
        },
        "configuration": {
            "top_k": top_k,
            "chunk_characters": chunk_characters,
            "chunk_overlap": chunk_overlap,
            "limit": limit,
        },
        "metrics": {
            "case_count": count,
            "any_gold_sentence_hit_rate_at_k": sum(case["first_gold_rank"] is not None for case in cases) / count,
            "complete_rationale_hit_rate_at_k": sum(case["complete_rationale_hit"] for case in cases) / count,
            "mrr_at_k": sum(1 / case["first_gold_rank"] for case in cases if case["first_gold_rank"]) / count,
            "baseline_word_bm25": {
                "any_gold_sentence_hit_rate_at_k": sum(case["baseline_first_gold_rank"] is not None for case in cases)
                / count,
                "complete_rationale_hit_rate_at_k": sum(case["baseline_complete_rationale_hit"] for case in cases)
                / count,
                "mrr_at_k": sum(
                    1 / case["baseline_first_gold_rank"] for case in cases if case["baseline_first_gold_rank"]
                )
                / count,
            },
        },
        "cases": cases,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate cited-document abstract evidence retrieval on local SciFact data."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-characters", type=int, default=320)
    parser.add_argument("--chunk-overlap", type=int, default=40)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_scifact_retrieval_benchmark(
        args.corpus,
        args.claims,
        top_k=args.top_k,
        chunk_characters=args.chunk_characters,
        chunk_overlap=args.chunk_overlap,
        limit=args.limit,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
