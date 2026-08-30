from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any

from scholarflow_mcp.models import DeduplicationResult, PaperRecord, SourceRef
from scholarflow_mcp.normalization import author_surnames, normalize_title

_CONFLICT_FIELDS = ("title", "year", "published_date", "venue")


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _informative_title(title: str) -> bool:
    tokens = title.split()
    return len(tokens) >= 4 and len(title) >= 24


def _year_compatible(left: int | None, right: int | None, tolerance: int) -> bool:
    return left is None or right is None or abs(left - right) <= tolerance


def _author_overlap(left: PaperRecord, right: PaperRecord) -> float:
    left_names = set(author_surnames(left.authors))
    right_names = set(author_surnames(right.authors))
    if not left_names or not right_names:
        return 0.0
    return len(left_names & right_names) / min(len(left_names), len(right_names))


def _same_first_author(left: PaperRecord, right: PaperRecord) -> bool:
    left_names = author_surnames(left.authors)
    right_names = author_surnames(right.authors)
    return bool(left_names and right_names and left_names[0] == right_names[0])


def _are_duplicates(left: PaperRecord, right: PaperRecord) -> bool:
    if left.doi and right.doi and left.doi == right.doi:
        return True
    if left.arxiv_id and right.arxiv_id and left.arxiv_id == right.arxiv_id:
        return True
    if left.openalex_id and right.openalex_id and left.openalex_id == right.openalex_id:
        return True

    left_title = normalize_title(left.title)
    right_title = normalize_title(right.title)
    if not (_informative_title(left_title) and _informative_title(right_title)):
        return False
    if not _same_first_author(left, right) or _author_overlap(left, right) < 0.5:
        return False

    if left_title == right_title:
        return _year_compatible(left.year, right.year, tolerance=1)

    left_tokens = set(left_title.split())
    right_tokens = set(right_title.split())
    token_overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence_ratio = SequenceMatcher(a=left_title, b=right_title, autojunk=False).ratio()
    return token_overlap >= 0.85 and sequence_ratio >= 0.94 and _year_compatible(left.year, right.year, tolerance=1)


def _quality(record: PaperRecord) -> tuple[int, int, int, int, int]:
    return (
        int(bool(record.doi)) + int(bool(record.arxiv_id)) + int(bool(record.openalex_id)),
        int(bool(record.venue)),
        len(record.abstract or ""),
        len(record.authors),
        record.cited_by_count or 0,
    )


def _different(field_name: str, left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    if field_name == "title":
        return normalize_title(str(left)) != normalize_title(str(right))
    return left != right


def _append_conflict(conflicts: dict[str, list[Any]], field_name: str, values: list[Any]) -> None:
    unique: list[Any] = []
    for value in values:
        if value is not None and value not in unique:
            unique.append(value)
    if len(unique) > 1:
        conflicts[field_name] = unique


def _merge_cluster(records: list[PaperRecord]) -> PaperRecord:
    ranked = sorted(enumerate(records), key=lambda item: (_quality(item[1]), -item[0]), reverse=True)
    canonical = deepcopy(ranked[0][1])
    canonical.sources = []
    canonical.conflicts = {}

    for field_name in _CONFLICT_FIELDS:
        values = [getattr(record, field_name) for record in records]
        if any(_different(field_name, values[0], value) for value in values[1:]):
            _append_conflict(canonical.conflicts, field_name, values)

    for record in records:
        for source in record.sources:
            if source not in canonical.sources:
                canonical.sources.append(source)
        for field_name, values in record.conflicts.items():
            _append_conflict(canonical.conflicts, field_name, [*canonical.conflicts.get(field_name, []), *values])

        for field_name in (
            "doi",
            "arxiv_id",
            "openalex_id",
            "abstract",
            "venue",
            "published_date",
            "publication_type",
            "landing_page_url",
            "pdf_url",
            "year",
        ):
            current = getattr(canonical, field_name)
            candidate = getattr(record, field_name)
            if current in (None, "") and candidate not in (None, ""):
                setattr(canonical, field_name, candidate)
        if len(record.authors) > len(canonical.authors):
            canonical.authors = list(record.authors)
        if (record.cited_by_count or 0) > (canonical.cited_by_count or 0):
            canonical.cited_by_count = record.cited_by_count
        if record.is_retracted:
            canonical.is_retracted = True

    canonical.sources.sort(key=lambda source: (source.provider, source.provider_id))
    return canonical


def deduplicate_records(records: list[PaperRecord]) -> DeduplicationResult:
    if not records:
        return DeduplicationResult(records=[], input_count=0, duplicates_removed=0)

    groups = _DisjointSet(len(records))
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            if _are_duplicates(records[left], records[right]):
                groups.union(left, right)

    clustered: dict[int, list[tuple[int, PaperRecord]]] = {}
    for index, record in enumerate(records):
        clustered.setdefault(groups.find(index), []).append((index, record))

    ordered_clusters = sorted(clustered.values(), key=lambda cluster: min(item[0] for item in cluster))
    merged = [_merge_cluster([record for _, record in cluster]) for cluster in ordered_clusters]
    return DeduplicationResult(
        records=merged,
        input_count=len(records),
        duplicates_removed=len(records) - len(merged),
    )


def source_key(source: SourceRef) -> tuple[str, str]:
    return source.provider, source.provider_id
