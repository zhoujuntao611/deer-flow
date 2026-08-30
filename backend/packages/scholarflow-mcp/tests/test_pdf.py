import base64

import pytest

from scholarflow_mcp.pdf import decode_pdf_base64, extract_pdf_base64, extract_pdf_pages
from tests.pdf_fixture import minimal_text_pdf


def test_extracts_embedded_text_with_page_provenance() -> None:
    pdf_bytes = minimal_text_pdf("Evidence appears on this page.")

    result = extract_pdf_pages(pdf_bytes, document_id="paper-1")

    assert result["total_pages"] == 1
    assert result["extracted_pages"] == 1
    assert result["truncated"] is False
    assert result["empty_pages"] == []
    assert result["pages"][0]["document_id"] == "paper-1"
    assert result["pages"][0]["page_number"] == 1
    assert "Evidence appears on this page." in result["pages"][0]["text"]
    assert len(result["sha256"]) == 64
    assert "semantic interpretation" in result["scope"]


def test_extracts_from_base64_and_ignores_transport_whitespace() -> None:
    encoded = base64.b64encode(minimal_text_pdf()).decode("ascii")
    wrapped = "\n".join(encoded[index : index + 40] for index in range(0, len(encoded), 40))

    result = extract_pdf_base64(wrapped, document_id="paper-2", max_pages=1)

    assert result["document_id"] == "paper-2"
    assert result["pages"][0]["page_number"] == 1


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("not-base64", "not valid base64"),
        ("", "non-empty base64 string"),
    ],
)
def test_rejects_invalid_base64(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        decode_pdf_base64(value)


@pytest.mark.parametrize(
    ("pdf_bytes", "message"),
    [
        (b"", "must not be empty"),
        (b"plain text", "does not start with a PDF header"),
        (b"%PDF-invalid", "could not be parsed"),
    ],
)
def test_rejects_non_pdf_or_malformed_bytes(pdf_bytes: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        extract_pdf_pages(pdf_bytes, document_id="paper-1")


def test_rejects_invalid_limits_and_document_id() -> None:
    pdf_bytes = minimal_text_pdf()
    with pytest.raises(ValueError, match="document_id"):
        extract_pdf_pages(pdf_bytes, document_id=" ")
    with pytest.raises(ValueError, match="max_pages"):
        extract_pdf_pages(pdf_bytes, document_id="paper-1", max_pages=0)
