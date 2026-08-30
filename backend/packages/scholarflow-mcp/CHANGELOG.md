# Changelog

All notable ScholarFlow MCP changes are recorded here. The package follows semantic
versioning independently from the DeerFlow application.

## Unreleased

## 0.2.0 - 2026-08-30

### Added

- Bounded embedded-text extraction from caller-supplied PDF bytes, with source hashes,
  page provenance, truncation diagnostics, and explicit no-OCR scope.
- Optional Responses API claim-evidence judge with strict structured output and
  span-citation validation.
- Three-way claim evaluation metrics plus a local SciFact import and manual benchmark
  workflow that does not redistribute source data.

## 0.1.0 - 2026-08-30

### Added

- Concurrent arXiv, Crossref, and OpenAlex provider adapters.
- Deterministic identifier and title-author-year entity resolution with provenance and
  conflict retention.
- Reciprocal-rank fusion, global result limiting, and partial-failure diagnostics.
- MCP stdio tools plus a UTF-8 JSON command-line search client.
- Deterministic page-level evidence quote location through MCP and CLI, with original
  text offsets and an explicit `semantic_support: not_assessed` boundary.
- Offline pairwise deduplication regression gate and manual known-item live benchmark.
- Dedicated tests, CI workflow, locked dependencies, and wheel/sdist build verification.

### Fixed

- Accept incomplete Crossref date parts without dropping the entire provider response.
- Avoid extracting arXiv-like number patterns from unrelated DOI strings.
- Emit Unicode paper metadata reliably in Windows terminals.
