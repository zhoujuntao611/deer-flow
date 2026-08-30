import json

from scholarflow_mcp.scifact import import_scifact_cases


def test_imports_human_annotated_rationales_without_bundling_source_data(tmp_path) -> None:
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "doc_id": 10,
                    "title": "A",
                    "abstract": ["Background.", "Treatment reduced risk."],
                    "structured": False,
                },
                {"doc_id": 11, "title": "B", "abstract": ["No relevant finding was reported."], "structured": False},
            ]
        ),
        encoding="utf-8",
    )
    claims_path = tmp_path / "claims_dev.jsonl"
    claims_path.write_text(
        json.dumps(
            {
                "id": 7,
                "claim": "Treatment reduced risk.",
                "evidence": {"10": [{"label": "SUPPORT", "sentences": [1]}]},
                "cited_doc_ids": [10, 11],
            }
        ),
        encoding="utf-8",
    )

    result = import_scifact_cases(corpus_path, claims_path)

    assert result["metadata"]["dataset"] == "SciFact"
    assert result["metadata"]["case_count"] == 2
    assert "not bundled" in result["metadata"]["redistribution"]
    assert result["cases"][0]["label"] == "supported"
    assert result["cases"][0]["evidence_spans"][0]["text"] == "Treatment reduced risk."
    assert result["cases"][1]["label"] == "insufficient"
    assert result["cases"][1]["source"]["evidence_mode"] == "cited_abstract_without_annotated_evidence"
