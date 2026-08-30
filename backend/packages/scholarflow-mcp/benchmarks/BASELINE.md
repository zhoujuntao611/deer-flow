# Known-item retrieval baseline

This is a saved summary of one manual live run, not a CI guarantee and not a
full-relevance recall evaluation.

- Run time: `2026-08-29T16:48:09Z`
- ScholarFlow: `0.1.0`
- Python: `3.12.13`
- Platform: `Windows 11 10.0.22631`
- Suite SHA-256: `b1b3507d1c68d138177ab7fb158ccb97ffe493ade830d5798abd23d501336a6f`
- Providers: arXiv, Crossref, OpenAlex
- Queries: 8
- HitRate@10: `1.0` (8/8 known works found)
- MRR@10: `0.479167`
- Provider availability: `1.0` (24/24 provider calls returned successfully)
- Cross-source deduplication rate: `0.069124`
- Latency: P50 `1457.783 ms`, P95 `2602.849 ms`

Observed target ranks:

- Attention Is All You Need: 4
- BERT: 3
- Retrieval-Augmented Generation: 1
- LoRA: 6
- ReAct: 2
- AlphaFold: 3
- Diabetic retinopathy detection: 4
- Gravitational-wave observation: 1

Public APIs, indexes, rankings, and network conditions change. Re-run the suite before
using this baseline in a release note or resume. The committed target set establishes
known-item identity only; it does not label every relevant result for each query.
