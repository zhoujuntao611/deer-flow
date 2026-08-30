# ScholarFlow Academic Search MCP

This package is an independently runnable MCP server. Keep it decoupled from
`deerflow.*` and `app.*` so it can be released and used by other agent runtimes.

## Invariants

- Provider adapters map remote responses into `PaperRecord`; they do not deduplicate.
- `dedup.py` is the only entity-resolution authority.
- Strong identity uses normalized DOI, arXiv ID, or OpenAlex ID.
- Title-based version merging requires an informative title, compatible publication
  year, matching first author, and author overlap. Generic titles must not merge.
- Never silently discard conflicting title/year/date/venue values; expose them through
  `PaperRecord.conflicts`.
- One provider failure must not discard successful results from other providers.
- Provider ranks are fused only after deduplication; `max_results` applies globally,
  and tie-breaking must remain deterministic.
- Unit tests and the committed benchmark must remain offline and use synthetic metadata.
- The search CLI emits UTF-8 JSON on stdout; logs and diagnostics must not corrupt that
  machine-readable stream. Exit code `2` means all selected providers failed.
- The known-item benchmark is manual and networked. Call its metric HitRate@K, never
  Recall@K, unless a complete human-labeled relevance pool has been added.
- Evidence verification accepts caller-supplied page text only; it must not read local
  paths or fetch URLs supplied in tool arguments.
- A located quote proves textual presence and page coordinates only. Keep
  `semantic_support` as `not_assessed`; never describe this result as claim validation.

## Commands

From the repository root:

```bash
uv run --project backend/packages/scholarflow-mcp --extra dev pytest backend/packages/scholarflow-mcp/tests -q
uv run --project backend/packages/scholarflow-mcp --extra dev ruff check backend/packages/scholarflow-mcp
uv run --project backend/packages/scholarflow-mcp --extra dev ruff format --check backend/packages/scholarflow-mcp
uv run --project backend/packages/scholarflow-mcp scholarflow-dedup-benchmark
uv run --project backend/packages/scholarflow-mcp scholarflow-search "query" --max-results 5
uv run --project backend/packages/scholarflow-mcp scholarflow-known-item-benchmark --max-results 10
uv run --project backend/packages/scholarflow-mcp scholarflow-verify-evidence backend/packages/scholarflow-mcp/examples/evidence_input.json
```

Live provider smoke tests are manual and never part of the default test suite.
