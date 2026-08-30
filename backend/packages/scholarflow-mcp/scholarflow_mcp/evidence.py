from __future__ import annotations

import unicodedata
from typing import Any

MAX_PAGES = 500
MAX_PAGE_CHARACTERS = 200_000
MAX_CLAIMS = 100
MAX_SPANS_PER_CLAIM = 20
MAX_QUOTE_CHARACTERS = 10_000


def _normalized_with_offsets(value: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    offsets: list[int] = []
    for original_index, original_character in enumerate(value):
        normalized_piece = unicodedata.normalize("NFKC", original_character).casefold().replace("\u00ad", "")
        for character in normalized_piece:
            if character.isspace():
                if characters and characters[-1] != " ":
                    characters.append(" ")
                    offsets.append(original_index)
                continue
            characters.append(character)
            offsets.append(original_index)

    if characters and characters[-1] == " ":
        characters.pop()
        offsets.pop()
    return "".join(characters), offsets


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _positive_page_number(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("page_number must be a positive integer")
    return value


def _index_pages(pages: list[dict[str, Any]]) -> dict[tuple[str, int], str]:
    if not isinstance(pages, list):
        raise ValueError("pages must be a list")
    if len(pages) > MAX_PAGES:
        raise ValueError(f"pages must contain at most {MAX_PAGES} entries")
    indexed: dict[tuple[str, int], str] = {}
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("each page must be an object")
        document_id = _required_text(page.get("document_id"), "document_id")
        page_number = _positive_page_number(page.get("page_number"))
        text = page.get("text")
        if not isinstance(text, str):
            raise ValueError("page text must be a string")
        if len(text) > MAX_PAGE_CHARACTERS:
            raise ValueError(f"page text must contain at most {MAX_PAGE_CHARACTERS} characters")
        key = document_id, page_number
        if key in indexed:
            raise ValueError(f"duplicate page: {document_id} page {page_number}")
        indexed[key] = text
    return indexed


def _locate_quote(page_text: str, quote: str) -> dict[str, Any]:
    normalized_page, offsets = _normalized_with_offsets(page_text)
    normalized_quote, _ = _normalized_with_offsets(quote)
    if not normalized_quote:
        raise ValueError("evidence quote must contain searchable text")

    start = normalized_page.find(normalized_quote)
    if start < 0:
        return {"status": "quote_not_found", "occurrence_count": 0}
    end = start + len(normalized_quote)
    occurrence_count = normalized_page.count(normalized_quote)
    original_start = offsets[start]
    original_end = offsets[end - 1] + 1
    return {
        "status": "located",
        "occurrence_count": occurrence_count,
        "character_start": original_start,
        "character_end": original_end,
        "matched_text": page_text[original_start:original_end],
    }


def verify_evidence_spans(
    *,
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Locate quoted evidence on declared pages without judging semantic claim support."""
    if not isinstance(claims, list):
        raise ValueError("claims must be a list")
    if len(claims) > MAX_CLAIMS:
        raise ValueError(f"claims must contain at most {MAX_CLAIMS} entries")
    indexed_pages = _index_pages(pages)
    seen_claim_ids: set[str] = set()
    verified_claims: list[dict[str, Any]] = []
    located_spans = 0
    total_spans = 0

    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("each claim must be an object")
        claim_id = _required_text(claim.get("claim_id"), "claim_id")
        if claim_id in seen_claim_ids:
            raise ValueError(f"duplicate claim_id: {claim_id}")
        seen_claim_ids.add(claim_id)
        claim_text = _required_text(claim.get("text"), "claim text")
        spans = claim.get("evidence_spans", [])
        if not isinstance(spans, list):
            raise ValueError("evidence_spans must be a list")
        if len(spans) > MAX_SPANS_PER_CLAIM:
            raise ValueError(f"each claim may contain at most {MAX_SPANS_PER_CLAIM} evidence spans")

        verified_spans: list[dict[str, Any]] = []
        for span in spans:
            if not isinstance(span, dict):
                raise ValueError("each evidence span must be an object")
            document_id = _required_text(span.get("document_id"), "document_id")
            page_number = _positive_page_number(span.get("page_number"))
            quote = _required_text(span.get("quote"), "evidence quote")
            if len(quote) > MAX_QUOTE_CHARACTERS:
                raise ValueError(f"evidence quote must contain at most {MAX_QUOTE_CHARACTERS} characters")
            key = document_id, page_number
            location = (
                _locate_quote(indexed_pages[key], quote)
                if key in indexed_pages
                else {"status": "page_missing", "occurrence_count": 0}
            )
            total_spans += 1
            located_spans += location["status"] == "located"
            verified_spans.append(
                {
                    "document_id": document_id,
                    "page_number": page_number,
                    "quote": quote,
                    **location,
                }
            )

        if not verified_spans:
            evidence_status = "no_evidence"
        elif all(span["status"] == "located" for span in verified_spans):
            evidence_status = "all_spans_located"
        elif any(span["status"] == "located" for span in verified_spans):
            evidence_status = "partially_located"
        else:
            evidence_status = "unlocated"
        verified_claims.append(
            {
                "claim_id": claim_id,
                "text": claim_text,
                "evidence_status": evidence_status,
                "semantic_support": "not_assessed",
                "evidence_spans": verified_spans,
            }
        )

    return {
        "claims": verified_claims,
        "summary": {
            "claim_count": len(verified_claims),
            "span_count": total_spans,
            "located_spans": located_spans,
            "unlocated_spans": total_spans - located_spans,
        },
        "scope": "quote presence and page coordinates only; semantic claim support is not assessed",
    }
