# SciFact cited-document evidence retrieval

This offline benchmark evaluates evidence discovery after a claim's cited document IDs
are known. It reads the caller's local SciFact `corpus.jsonl` and labeled
`claims_dev.jsonl`, builds one page from each cited abstract, and asks ScholarFlow to
retrieve text windows for the claim. Each annotated rationale is one case. A hit means
that a **full gold rationale sentence** appears in a Top-K window from the gold
document. `complete_rationale_hit_rate_at_k` requires every sentence of one annotated
rationale to appear across the Top-K windows. These are retrieval metrics; they do not
measure PDF extraction, scientific correctness, or open-corpus paper retrieval.

The package does not bundle or download SciFact data. Obtain it from the
[maintainer repository](https://github.com/allenai/scifact), then run from the DeerFlow
repository root:

```bash
uv run --project backend/packages/scholarflow-mcp \
  scholarflow-retrieval-benchmark \
  --corpus data/corpus.jsonl --claims data/claims_dev.jsonl \
  --top-k 5 --chunk-characters 320 --chunk-overlap 40 \
  --output scifact-retrieval.json
```

The command evaluates two paired modes on the same claims, cited abstracts, chunks,
and Top-K budget: word-token BM25 as an ablation baseline, and word-token plus
character n-gram BM25 with reciprocal-rank fusion. The output includes source-file
SHA-256 hashes and case-level ranks. No article text is copied into the result.

## Local development-set measurement

Measured on 2026-10-09 using SciFact's labeled development split. The chunk boundary
rule was adjusted while inspecting this development set, so this table is a development
measurement, not a held-out estimate or a statistical significance claim.

| Mode | Cases | Any full gold sentence HitRate@5 | Complete rationale HitRate@5 | MRR@5 |
| --- | ---: | ---: | ---: | ---: |
| Word BM25 ablation | 338 | 62.1% | 60.1% | 0.3862 |
| Word + character BM25, RRF | 338 | 65.4% | 63.9% | 0.3999 |

- Corpus SHA-256: `b8d6c89624cb2ed74dee8938effc4f5d8bd2086887880af8110d64be4ceade62`
- Claims SHA-256: `86f0435d08fdb65d1aa41d1472684f57e6e71930626497bdf4d7a9ec1a632217`

The 3.3 percentage-point HitRate@5 improvement is relative to the word-only ablation
on these exact cases. A new dataset or a broader candidate pool may produce a
different result. Query-document semantic equivalence, claim support, and citation
truthfulness require separate evaluation; this benchmark scores literal occurrence
of annotated sentences in retrieved windows.
