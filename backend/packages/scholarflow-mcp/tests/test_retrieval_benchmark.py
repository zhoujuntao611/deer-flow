import json

from scholarflow_mcp.retrieval_benchmark import run_scifact_retrieval_benchmark


def test_scifact_benchmark_reports_cited_document_sentence_hit(tmp_path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    claims = tmp_path / "claims_dev.jsonl"
    corpus.write_text(
        "\n".join(
            json.dumps(item)
            for item in [
                {"doc_id": 10, "abstract": ["Background information.", "Treatment reduced risk by 40%."]},
                {"doc_id": 11, "abstract": ["A different laboratory studied navigation."]},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    claims.write_text(
        json.dumps(
            {
                "id": 1,
                "claim": "Treatment reduced risk by 40%.",
                "cited_doc_ids": [10, 11],
                "evidence": {"10": [{"label": "SUPPORT", "sentences": [1]}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_scifact_retrieval_benchmark(corpus, claims, top_k=3, chunk_characters=120, chunk_overlap=10)

    assert result["metrics"]["case_count"] == 1
    assert result["metrics"]["any_gold_sentence_hit_rate_at_k"] == 1.0
    assert result["metrics"]["complete_rationale_hit_rate_at_k"] == 1.0
    assert result["metrics"]["mrr_at_k"] == 1.0
    assert result["cases"][0]["first_gold_rank"] == 1
    assert result["metadata"]["scope"] == "cited-document abstract evidence retrieval, not open-corpus retrieval"
