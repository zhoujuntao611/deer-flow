from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from scholarflow_mcp.claim_assessment import assess_claim_evidence
from scholarflow_mcp.evidence import _index_pages, _required_text
from scholarflow_mcp.judge import MAX_CLAIM_CHARACTERS, MAX_EVIDENCE_CHARACTERS, MAX_JUDGE_CLAIMS, ClaimJudge

MAX_TOTAL_PAGE_CHARACTERS = 5_000_000
MAX_CHUNKS = 20_000
DEFAULT_CHUNK_CHARACTERS = 800
DEFAULT_CHUNK_OVERLAP = 120
MAX_RETRIEVED_SPANS = 10
RRF_K = 60
RetrievalMode = Literal["hybrid", "word_bm25"]
_WORD_RUNS = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]+")


@dataclass(frozen=True)
class _Chunk:
    document_id: str
    page_number: int
    start: int
    end: int
    text: str


def _word_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    tokens: list[str] = []
    for match in _WORD_RUNS.finditer(normalized):
        term = match.group()
        if "\u3400" <= term[0] <= "\u9fff":
            tokens.extend(term[index : index + 2] for index in range(len(term) - 1))
            if len(term) == 1:
                tokens.append(term)
        else:
            tokens.append(term)
    return tokens


def _character_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    compact = "".join(character for character in normalized if character.isalnum())
    if not compact:
        return []
    size = 2 if any("\u3400" <= character <= "\u9fff" for character in compact) else 3
    if len(compact) < size:
        return [compact]
    return [compact[index : index + size] for index in range(len(compact) - size + 1)]


def _chunk_end(text: str, start: int, maximum: int, overlap: int) -> int:
    end = min(start + maximum, len(text))
    if end == len(text):
        return end
    threshold = start + max(overlap + 1, maximum // 4)
    candidates: list[int] = []
    for delimiter in ("\n\n", "\n", ". ", "。", "！", "？", "; "):
        location = text.rfind(delimiter, threshold, end)
        if location >= 0:
            candidates.append(location + len(delimiter))
    return max(candidates) if candidates else end


def _make_chunks(pages: dict[tuple[str, int], str], *, size: int, overlap: int) -> list[_Chunk]:
    chunks: list[_Chunk] = []
    for (document_id, page_number), text in sorted(pages.items()):
        start = 0
        while start < len(text):
            end = _chunk_end(text, start, size, overlap)
            selected = text[start:end]
            left_trim = len(selected) - len(selected.lstrip())
            right_trim = len(selected.rstrip())
            if selected.strip():
                chunk_start = start + left_trim
                chunk_end = start + right_trim
                chunks.append(_Chunk(document_id, page_number, chunk_start, chunk_end, text[chunk_start:chunk_end]))
                if len(chunks) > MAX_CHUNKS:
                    raise ValueError(f"pages produce more than {MAX_CHUNKS} retrieval chunks")
            if end == len(text):
                break
            start = end - overlap
    return chunks


def _bm25_scores(query: list[str], documents: list[list[str]]) -> dict[int, float]:
    if not query or not documents:
        return {}
    frequencies = [Counter(document) for document in documents]
    document_count = len(documents)
    average_length = sum(map(len, documents)) / document_count
    document_frequencies: Counter[str] = Counter()
    for frequency in frequencies:
        document_frequencies.update(frequency.keys())
    scores: dict[int, float] = {}
    for index, frequency in enumerate(frequencies):
        length_factor = 1.2 * (0.25 + 0.75 * len(documents[index]) / max(average_length, 1))
        score = 0.0
        for term in set(query):
            term_frequency = frequency.get(term, 0)
            if not term_frequency:
                continue
            idf = math.log1p((document_count - document_frequencies[term] + 0.5) / (document_frequencies[term] + 0.5))
            score += idf * (term_frequency * 2.2) / (term_frequency + length_factor)
        if score > 0:
            scores[index] = score
    return scores


def _rank_channel(query: str, chunks: list[_Chunk], tokenizer: Any) -> dict[int, int]:
    scores = _bm25_scores(tokenizer(query), [tokenizer(chunk.text) for chunk in chunks])
    ordered = sorted(
        scores,
        key=lambda index: (
            -scores[index],
            chunks[index].document_id,
            chunks[index].page_number,
            chunks[index].start,
        ),
    )
    return {index: rank for rank, index in enumerate(ordered, start=1)}


def _validate_options(top_k: Any, chunk_characters: Any, chunk_overlap: Any) -> None:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_RETRIEVED_SPANS:
        raise ValueError(f"top_k must be an integer between 1 and {MAX_RETRIEVED_SPANS}")
    if (
        isinstance(chunk_characters, bool)
        or not isinstance(chunk_characters, int)
        or not 64 <= chunk_characters <= 4000
    ):
        raise ValueError("chunk_characters must be an integer between 64 and 4000")
    if (
        isinstance(chunk_overlap, bool)
        or not isinstance(chunk_overlap, int)
        or not 0 <= chunk_overlap < chunk_characters // 2
    ):
        raise ValueError("chunk_overlap must be an integer below half of chunk_characters")


def _validate_claims(claims: Any) -> list[dict[str, str]]:
    if not isinstance(claims, list):
        raise ValueError("claims must be a list")
    if len(claims) > MAX_JUDGE_CLAIMS:
        raise ValueError(f"claims must contain at most {MAX_JUDGE_CLAIMS} entries")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("each claim must be an object")
        claim_id = _required_text(claim.get("claim_id"), "claim_id")
        if len(claim_id) > 200:
            raise ValueError("claim_id must contain at most 200 characters")
        if claim_id in seen:
            raise ValueError(f"duplicate claim_id: {claim_id}")
        seen.add(claim_id)
        text = _required_text(claim.get("text"), "claim text")
        if len(text) > MAX_CLAIM_CHARACTERS:
            raise ValueError(f"claim text must contain at most {MAX_CLAIM_CHARACTERS} characters")
        normalized.append({"claim_id": claim_id, "text": text})
    return normalized


def retrieve_claim_evidence(
    *,
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    top_k: int = 5,
    chunk_characters: int = DEFAULT_CHUNK_CHARACTERS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    mode: RetrievalMode = "hybrid",
) -> dict[str, Any]:
    """Retrieve candidate quotes from supplied pages with two BM25 channels and RRF.

    A candidate is a text window, not proof that the claim is true. Every window
    retains byte-for-byte source text and exact Python character offsets.
    """
    _validate_options(top_k, chunk_characters, chunk_overlap)
    if mode not in {"hybrid", "word_bm25"}:
        raise ValueError("mode must be hybrid or word_bm25")
    indexed_pages = _index_pages(pages)
    if sum(map(len, indexed_pages.values())) > MAX_TOTAL_PAGE_CHARACTERS:
        raise ValueError(f"total page text must contain at most {MAX_TOTAL_PAGE_CHARACTERS} characters")
    normalized_claims = _validate_claims(claims)
    chunks = _make_chunks(indexed_pages, size=chunk_characters, overlap=chunk_overlap)
    results: list[dict[str, Any]] = []
    for claim in normalized_claims:
        channel_ranks = {"word_bm25": _rank_channel(claim["text"], chunks, _word_tokens)}
        if mode == "hybrid":
            channel_ranks["character_bm25"] = _rank_channel(claim["text"], chunks, _character_tokens)
        candidate_indices = set().union(*(set(ranks) for ranks in channel_ranks.values()))
        fused = {
            index: sum(1 / (RRF_K + ranks[index]) for ranks in channel_ranks.values() if index in ranks)
            for index in candidate_indices
        }
        ranked = sorted(
            candidate_indices,
            key=lambda index: (
                -fused[index],
                chunks[index].document_id,
                chunks[index].page_number,
                chunks[index].start,
            ),
        )
        spans = []
        for rank, index in enumerate(ranked[:top_k], start=1):
            chunk = chunks[index]
            spans.append(
                {
                    "span_id": f"{claim['claim_id']}:retrieved-{rank}",
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number,
                    "quote": chunk.text,
                    "character_start": chunk.start,
                    "character_end": chunk.end,
                    "retrieval_rank": rank,
                    "retrieval_score": fused[index],
                    "channel_ranks": {name: ranks[index] for name, ranks in channel_ranks.items() if index in ranks},
                }
            )
        results.append({**claim, "candidate_count": len(ranked), "evidence_spans": spans})
    return {
        "claims": results,
        "summary": {
            "claim_count": len(results),
            "page_count": len(indexed_pages),
            "chunk_count": len(chunks),
            "returned_candidates": sum(len(result["evidence_spans"]) for result in results),
            "claims_without_candidates": sum(not result["evidence_spans"] for result in results),
        },
        "retriever": {
            "method": "word BM25 + character BM25, reciprocal-rank fusion" if mode == "hybrid" else "word BM25",
            "mode": mode,
            "rrf_k": RRF_K,
            "top_k": top_k,
            "chunk_characters": chunk_characters,
            "chunk_overlap": chunk_overlap,
        },
        "scope": (
            "lexical candidate retrieval from caller-supplied page text; "
            "relevance and semantic support are not established"
        ),
    }


async def assess_retrieved_claim_evidence(
    *,
    pages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    top_k: int = 5,
    chunk_characters: int = DEFAULT_CHUNK_CHARACTERS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    mode: RetrievalMode = "hybrid",
    judge: ClaimJudge | None = None,
) -> dict[str, Any]:
    """Retrieve, re-locate, and then model-judge claim evidence with cited span IDs."""
    if top_k * chunk_characters > MAX_EVIDENCE_CHARACTERS:
        raise ValueError(f"top_k * chunk_characters must not exceed {MAX_EVIDENCE_CHARACTERS}")
    retrieved = retrieve_claim_evidence(
        pages=pages,
        claims=claims,
        top_k=top_k,
        chunk_characters=chunk_characters,
        chunk_overlap=chunk_overlap,
        mode=mode,
    )
    assessed = await assess_claim_evidence(pages=pages, claims=retrieved["claims"], judge=judge)
    for result, source in zip(assessed["claims"], retrieved["claims"], strict=True):
        retrieval_by_id = {span["span_id"]: span for span in source["evidence_spans"]}
        for span in result["evidence_spans"]:
            candidate = retrieval_by_id[span["span_id"]]
            span.update(
                {
                    "retrieval_rank": candidate["retrieval_rank"],
                    "retrieval_score": candidate["retrieval_score"],
                    "channel_ranks": candidate["channel_ranks"],
                }
            )
    assessed["retrieval"] = retrieved["summary"]
    assessed["retriever"] = retrieved["retriever"]
    assessed["scope"] = (
        "candidate retrieval is lexical; evidence quotes were located on supplied pages; "
        "semantic labels are model judgements, not independent scientific truth"
    )
    return assessed
