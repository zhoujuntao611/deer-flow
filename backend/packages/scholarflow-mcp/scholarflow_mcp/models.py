from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from scholarflow_mcp.normalization import normalize_arxiv_id, normalize_doi, normalize_openalex_id


@dataclass(frozen=True)
class SourceRef:
    provider: str
    provider_id: str
    url: str | None = None
    rank: int | None = None


@dataclass
class PaperRecord:
    provider: str
    provider_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    published_date: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    abstract: str | None = None
    venue: str | None = None
    cited_by_count: int | None = None
    publication_type: str | None = None
    landing_page_url: str | None = None
    pdf_url: str | None = None
    is_retracted: bool | None = None
    fused_relevance_score: float | None = None
    sources: list[SourceRef] = field(default_factory=list)
    conflicts: dict[str, list[Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.provider = self.provider.strip().casefold()
        self.provider_id = self.provider_id.strip()
        self.title = self.title.strip()
        self.authors = [author.strip() for author in self.authors if author and author.strip()]
        self.doi = normalize_doi(self.doi)
        self.arxiv_id = normalize_arxiv_id(self.arxiv_id)
        self.openalex_id = normalize_openalex_id(self.openalex_id)
        if not self.sources:
            self.sources = [SourceRef(self.provider, self.provider_id, self.landing_page_url)]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> PaperRecord:
        allowed = cls.__dataclass_fields__.keys()
        payload = {key: item for key, item in value.items() if key in allowed and key not in {"sources", "conflicts"}}
        raw_sources = value.get("sources", [])
        payload["sources"] = [
            source if isinstance(source, SourceRef) else SourceRef(**source) for source in raw_sources
        ]
        payload["conflicts"] = dict(value.get("conflicts", {}))
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeduplicationResult:
    records: list[PaperRecord]
    input_count: int
    duplicates_removed: int


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    status: str
    record_count: int
    error: str | None = None


@dataclass(frozen=True)
class LiteratureSearchResult:
    query: str
    records: list[PaperRecord]
    provider_status: list[ProviderStatus]
    total_raw_records: int
    unique_before_limit: int
    duplicates_removed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "records": [record.to_dict() for record in self.records],
            "provider_status": [asdict(status) for status in self.provider_status],
            "total_raw_records": self.total_raw_records,
            "unique_before_limit": self.unique_before_limit,
            "unique_records": len(self.records),
            "duplicates_removed": self.duplicates_removed,
        }
