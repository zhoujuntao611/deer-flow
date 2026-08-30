from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 20_000_000
MAX_PDF_PAGES = 200
DEFAULT_MAX_PAGES = 50
MAX_PAGE_CHARACTERS = 200_000
MAX_TOTAL_CHARACTERS = 5_000_000


def _document_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("document_id must be a non-empty string")
    return value.strip()


def _page_limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_PDF_PAGES:
        raise ValueError(f"max_pages must be an integer between 1 and {MAX_PDF_PAGES}")
    return value


def decode_pdf_base64(value: Any) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("pdf_base64 must be a non-empty base64 string")
    compact = "".join(value.split())
    if len(compact) > ((MAX_PDF_BYTES + 2) // 3) * 4:
        raise ValueError(f"decoded PDF must contain at most {MAX_PDF_BYTES} bytes")
    try:
        return base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("pdf_base64 is not valid base64") from exc


def extract_pdf_pages(
    pdf_bytes: bytes,
    *,
    document_id: str,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Extract bounded page text from caller-supplied PDF bytes without OCR or network access."""
    normalized_document_id = _document_id(document_id)
    page_limit = _page_limit(max_pages)
    if not isinstance(pdf_bytes, bytes):
        raise ValueError("pdf_bytes must be bytes")
    if not pdf_bytes:
        raise ValueError("PDF must not be empty")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"PDF must contain at most {MAX_PDF_BYTES} bytes")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("input does not start with a PDF header")

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("encrypted PDF requires a password and cannot be extracted")
        total_pages = len(reader.pages)
    except ValueError:
        raise
    except (PdfReadError, OSError, TypeError, ValueError) as exc:
        raise ValueError("PDF could not be parsed") from exc

    if total_pages > MAX_PDF_PAGES:
        raise ValueError(f"PDF must contain at most {MAX_PDF_PAGES} pages")

    selected_pages = min(total_pages, page_limit)
    pages: list[dict[str, Any]] = []
    empty_pages: list[int] = []
    total_characters = 0
    for page_index in range(selected_pages):
        try:
            text = reader.pages[page_index].extract_text() or ""
        except Exception as exc:
            raise ValueError(f"text extraction failed on page {page_index + 1}") from exc
        if len(text) > MAX_PAGE_CHARACTERS:
            raise ValueError(f"extracted page {page_index + 1} exceeds {MAX_PAGE_CHARACTERS} characters")
        total_characters += len(text)
        if total_characters > MAX_TOTAL_CHARACTERS:
            raise ValueError(f"extracted document exceeds {MAX_TOTAL_CHARACTERS} characters")
        if not text.strip():
            empty_pages.append(page_index + 1)
        pages.append(
            {
                "document_id": normalized_document_id,
                "page_number": page_index + 1,
                "text": text,
                "character_count": len(text),
            }
        )

    warnings: list[str] = []
    if empty_pages:
        warnings.append("empty pages may be scanned images; OCR is not performed")
    if selected_pages < total_pages:
        warnings.append("output was truncated by max_pages")

    return {
        "document_id": normalized_document_id,
        "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "byte_count": len(pdf_bytes),
        "total_pages": total_pages,
        "extracted_pages": selected_pages,
        "truncated": selected_pages < total_pages,
        "empty_pages": empty_pages,
        "total_characters": total_characters,
        "pages": pages,
        "warnings": warnings,
        "scope": "embedded PDF text only; OCR, layout reconstruction, and semantic interpretation are not performed",
    }


def extract_pdf_base64(
    pdf_base64: str,
    *,
    document_id: str,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    return extract_pdf_pages(
        decode_pdf_base64(pdf_base64),
        document_id=document_id,
        max_pages=max_pages,
    )
