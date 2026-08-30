import json

from scholarflow_mcp.evidence_cli import main


def _write_input(tmp_path, quote: str):
    input_path = tmp_path / "evidence.json"
    input_path.write_text(
        json.dumps(
            {
                "pages": [{"document_id": "paper-1", "page_number": 3, "text": "A verified quotation."}],
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "text": "A claim.",
                        "evidence_spans": [{"document_id": "paper-1", "page_number": 3, "quote": quote}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return input_path


def test_cli_writes_located_result_to_file(tmp_path) -> None:
    input_path = _write_input(tmp_path, "verified quotation")
    output_path = tmp_path / "result.json"

    exit_code = main([str(input_path), "--output", str(output_path)])

    assert exit_code == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["summary"]["located_spans"] == 1


def test_cli_returns_one_when_any_span_is_unlocated(tmp_path, capsys) -> None:
    input_path = _write_input(tmp_path, "missing quotation")

    exit_code = main([str(input_path)])

    assert exit_code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["summary"]["unlocated_spans"] == 1
