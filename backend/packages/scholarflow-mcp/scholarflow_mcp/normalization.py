from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_ARXIV_PREFIX = re.compile(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)", re.IGNORECASE)
_ARXIV_ID = re.compile(r"(?P<id>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7}))(?:v\d+)?", re.IGNORECASE)
_ARXIV_DOI_PREFIX = re.compile(r"^10\.48550/arxiv\.", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[^\w]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unquote(value).strip()
    normalized = _DOI_PREFIX.sub("", normalized)
    normalized = normalized.strip().rstrip(".,;)").casefold()
    return normalized or None


def normalize_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unquote(value).strip().split("?", 1)[0].split("#", 1)[0]
    normalized = _ARXIV_PREFIX.sub("", normalized).removesuffix(".pdf")
    normalized = _ARXIV_DOI_PREFIX.sub("", normalized)
    match = _ARXIV_ID.fullmatch(normalized)
    return match.group("id").casefold() if match else None


def normalize_openalex_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().rstrip("/").rsplit("/", 1)[-1].upper()
    return normalized if re.fullmatch(r"W\d+", normalized) else None


def normalize_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    without_marks = "".join(character for character in decomposed if not unicodedata.combining(character))
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", without_marks)).strip()


def author_surnames(authors: list[str]) -> tuple[str, ...]:
    surnames: list[str] = []
    for author in authors:
        normalized = normalize_title(author)
        if normalized:
            surnames.append(normalized.split()[-1])
    return tuple(surnames)
