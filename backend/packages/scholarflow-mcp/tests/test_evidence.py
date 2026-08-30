import pytest

from scholarflow_mcp.evidence import verify_evidence_spans


def test_locates_unicode_quote_across_whitespace_and_preserves_offsets() -> None:
    page_text = "The UAV’s trajectory\nremained stable."

    result = verify_evidence_spans(
        pages=[{"document_id": "paper-1", "page_number": 4, "text": page_text}],
        claims=[
            {
                "claim_id": "claim-1",
                "text": "The trajectory remained stable.",
                "evidence_spans": [
                    {
                        "document_id": "paper-1",
                        "page_number": 4,
                        "quote": "the uav’s trajectory remained stable",
                    }
                ],
            }
        ],
    )

    span = result["claims"][0]["evidence_spans"][0]
    assert span["status"] == "located"
    assert span["matched_text"] == "The UAV’s trajectory\nremained stable"
    assert page_text[span["character_start"] : span["character_end"]] == span["matched_text"]
    assert result["claims"][0]["semantic_support"] == "not_assessed"
    assert "semantic claim support is not assessed" in result["scope"]


def test_reports_partial_missing_and_empty_evidence_without_overclaiming() -> None:
    result = verify_evidence_spans(
        pages=[{"document_id": "paper-1", "page_number": 1, "text": "Measured accuracy was 94%."}],
        claims=[
            {
                "claim_id": "partial",
                "text": "Accuracy was measured.",
                "evidence_spans": [
                    {"document_id": "paper-1", "page_number": 1, "quote": "accuracy was 94%"},
                    {"document_id": "paper-1", "page_number": 2, "quote": "unavailable page"},
                ],
            },
            {
                "claim_id": "unlocated",
                "text": "The experiment was replicated.",
                "evidence_spans": [{"document_id": "paper-1", "page_number": 1, "quote": "replicated independently"}],
            },
            {"claim_id": "none", "text": "No evidence supplied.", "evidence_spans": []},
        ],
    )

    assert [claim["evidence_status"] for claim in result["claims"]] == [
        "partially_located",
        "unlocated",
        "no_evidence",
    ]
    assert result["claims"][0]["evidence_spans"][1]["status"] == "page_missing"
    assert result["claims"][1]["evidence_spans"][0]["status"] == "quote_not_found"
    assert result["summary"] == {
        "claim_count": 3,
        "span_count": 3,
        "located_spans": 1,
        "unlocated_spans": 2,
    }


@pytest.mark.parametrize(
    ("pages", "claims", "message"),
    [
        ({}, [], "pages must be a list"),
        ([], {}, "claims must be a list"),
        (["not-an-object"], [], "each page must be an object"),
        ([], ["not-an-object"], "each claim must be an object"),
    ],
)
def test_rejects_malformed_collections(pages: object, claims: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        verify_evidence_spans(pages=pages, claims=claims)  # type: ignore[arg-type]


def test_rejects_duplicate_pages_and_empty_quotes() -> None:
    duplicate_pages = [
        {"document_id": "paper-1", "page_number": 1, "text": "first"},
        {"document_id": "paper-1", "page_number": 1, "text": "second"},
    ]
    with pytest.raises(ValueError, match="duplicate page"):
        verify_evidence_spans(pages=duplicate_pages, claims=[])

    with pytest.raises(ValueError, match="evidence quote must be a non-empty string"):
        verify_evidence_spans(
            pages=[{"document_id": "paper-1", "page_number": 1, "text": "text"}],
            claims=[
                {
                    "claim_id": "claim-1",
                    "text": "claim",
                    "evidence_spans": [{"document_id": "paper-1", "page_number": 1, "quote": "   "}],
                }
            ],
        )
