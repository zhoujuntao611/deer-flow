from scholarflow_mcp.dedup import deduplicate_records
from scholarflow_mcp.models import PaperRecord


def _paper(provider: str, provider_id: str, **values) -> PaperRecord:
    defaults = {
        "title": "A useful research paper",
        "authors": ["Ada Lovelace"],
        "year": 2025,
    }
    defaults.update(values)
    return PaperRecord(provider=provider, provider_id=provider_id, **defaults)


def test_same_doi_merges_and_preserves_provenance() -> None:
    result = deduplicate_records(
        [
            _paper("crossref", "10.1000/example", doi="https://doi.org/10.1000/EXAMPLE", venue="Journal A"),
            _paper(
                "openalex",
                "W123",
                doi="doi:10.1000/example",
                abstract="The longer record should contribute its abstract.",
                cited_by_count=42,
            ),
        ]
    )

    assert result.duplicates_removed == 1
    assert len(result.records) == 1
    paper = result.records[0]
    assert paper.doi == "10.1000/example"
    assert paper.abstract == "The longer record should contribute its abstract."
    assert paper.cited_by_count == 42
    assert {(source.provider, source.provider_id) for source in paper.sources} == {
        ("crossref", "10.1000/example"),
        ("openalex", "W123"),
    }


def test_preprint_and_published_version_merge_by_title_author_and_year() -> None:
    result = deduplicate_records(
        [
            _paper(
                "arxiv",
                "2501.01234",
                title="Evidence First Retrieval for Long Horizon Research Agents",
                authors=["Ada Lovelace", "Grace Hopper"],
                year=2025,
                arxiv_id="2501.01234v2",
            ),
            _paper(
                "crossref",
                "10.5555/agent.2026.7",
                title="Evidence-First Retrieval for Long-Horizon Research Agents",
                authors=["Ada Lovelace", "Grace M. Hopper"],
                year=2026,
                doi="10.5555/agent.2026.7",
                venue="Proceedings of Verifiable Agents",
            ),
        ]
    )

    assert result.duplicates_removed == 1
    paper = result.records[0]
    assert paper.arxiv_id == "2501.01234"
    assert paper.doi == "10.5555/agent.2026.7"
    assert paper.venue == "Proceedings of Verifiable Agents"


def test_generic_titles_with_different_authors_do_not_merge() -> None:
    result = deduplicate_records(
        [
            _paper("crossref", "a", title="Editorial Introduction", authors=["Ada Lovelace"]),
            _paper("openalex", "b", title="Editorial Introduction", authors=["Alan Turing"]),
        ]
    )

    assert result.duplicates_removed == 0
    assert len(result.records) == 2


def test_conflicting_years_are_reported_without_overwriting_silently() -> None:
    result = deduplicate_records(
        [
            _paper("crossref", "10.1000/conflict", doi="10.1000/conflict", year=2024),
            _paper("openalex", "W9", doi="10.1000/conflict", year=2026),
        ]
    )

    assert result.records[0].year == 2024
    assert result.records[0].conflicts["year"] == [2024, 2026]
