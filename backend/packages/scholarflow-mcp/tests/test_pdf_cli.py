import json

from scholarflow_mcp.pdf_cli import main
from tests.pdf_fixture import minimal_text_pdf


def test_pdf_cli_writes_machine_readable_output(tmp_path) -> None:
    input_path = tmp_path / "paper.pdf"
    input_path.write_bytes(minimal_text_pdf("CLI evidence."))
    output_path = tmp_path / "pages.json"

    exit_code = main([str(input_path), "--document-id", "paper-cli", "--max-pages", "1", "--output", str(output_path)])

    assert exit_code == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["document_id"] == "paper-cli"
    assert "CLI evidence." in result["pages"][0]["text"]
