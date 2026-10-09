import json

from scholarflow_mcp.retrieval_cli import main


def test_retrieval_cli_writes_traceable_candidates(tmp_path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            {
                "pages": [{"document_id": "study", "page_number": 1, "text": "The detector reached 94% accuracy."}],
                "claims": [{"claim_id": "claim", "text": "Detector accuracy reached 94%."}],
            }
        ),
        encoding="utf-8",
    )

    assert main([str(input_path), "--output", str(output_path)]) == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["claims"][0]["evidence_spans"][0]["document_id"] == "study"
    assert result["retriever"]["mode"] == "hybrid"
