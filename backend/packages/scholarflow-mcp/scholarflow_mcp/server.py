from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from scholarflow_mcp.application import run_search
from scholarflow_mcp.claim_assessment import assess_claim_evidence as assess_claims
from scholarflow_mcp.dedup import deduplicate_records
from scholarflow_mcp.evidence import verify_evidence_spans as verify_spans
from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.pdf import extract_pdf_base64
from scholarflow_mcp.retrieval import assess_retrieved_claim_evidence as assess_retrieved
from scholarflow_mcp.retrieval import retrieve_claim_evidence as retrieve_evidence

mcp = FastMCP("ScholarFlow Academic Search")


@mcp.tool()
async def search_literature(
    query: str,
    max_results: int = 20,
    from_year: int | None = None,
    to_year: int | None = None,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """Search arXiv, Crossref, and OpenAlex, then normalize and deduplicate the results."""
    return await run_search(
        query,
        max_results=max_results,
        from_year=from_year,
        to_year=to_year,
        providers=providers,
    )


@mcp.tool()
def normalize_papers(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize and deduplicate caller-supplied scholarly metadata without network access."""
    parsed = [PaperRecord.from_mapping(record) for record in records]
    result = deduplicate_records(parsed)
    return {
        "records": [record.to_dict() for record in result.records],
        "input_count": result.input_count,
        "unique_records": len(result.records),
        "duplicates_removed": result.duplicates_removed,
    }


@mcp.tool()
def verify_evidence_spans(
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Locate quoted evidence on declared pages. This does not judge whether evidence supports a claim."""
    return verify_spans(pages=pages, claims=claims)


@mcp.tool()
def extract_pdf_pages(
    pdf_base64: str,
    document_id: str,
    max_pages: int = 50,
) -> dict[str, Any]:
    """Extract bounded embedded page text from caller-supplied PDF bytes. This performs no OCR or URL fetching."""
    return extract_pdf_base64(pdf_base64, document_id=document_id, max_pages=max_pages)


@mcp.tool()
async def assess_claim_evidence(
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Locate supplied quotes, then classify support using a configured model judge with explicit uncertainty."""
    return await assess_claims(pages=pages, claims=claims)


@mcp.tool()
def retrieve_claim_evidence(
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    top_k: int = 5,
    chunk_characters: int = 800,
    chunk_overlap: int = 120,
    mode: str = "hybrid",
) -> dict[str, Any]:
    """Retrieve candidate quotes from supplied pages with BM25 fusion and exact page offsets; no support judgement."""
    return retrieve_evidence(
        pages=pages,
        claims=claims,
        top_k=top_k,
        chunk_characters=chunk_characters,
        chunk_overlap=chunk_overlap,
        mode=mode,
    )


@mcp.tool()
async def assess_retrieved_claim_evidence(
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    top_k: int = 5,
    chunk_characters: int = 800,
    chunk_overlap: int = 120,
    mode: str = "hybrid",
) -> dict[str, Any]:
    """Retrieve candidates, verify their source offsets, then judge claim support with cited span IDs."""
    return await assess_retrieved(
        pages=pages,
        claims=claims,
        top_k=top_k,
        chunk_characters=chunk_characters,
        chunk_overlap=chunk_overlap,
        mode=mode,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
