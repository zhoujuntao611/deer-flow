# SciFact semantic evaluation protocol

ScholarFlow uses SciFact only as a caller-downloaded, human-annotated benchmark. The
repository does not bundle, mirror, or automatically download its claims or abstracts.

## Prepare cases

Download the official data from the
[SciFact maintainer repository](https://github.com/allenai/scifact). Use a labeled train
or development split; the public test split does not include gold labels.

```bash
uv run --project backend/packages/scholarflow-mcp scholarflow-import-scifact \
  --corpus data/corpus.jsonl \
  --claims data/claims_dev.jsonl \
  --output scifact-dev-cases.json
```

Each annotated rationale becomes one `supported` or `contradicted` case containing its
gold sentence spans. A cited abstract for which annotators supplied no evidence becomes
an `insufficient` case unless `--exclude-insufficient` is used.

## Run the model judge

Set `SCHOLARFLOW_JUDGE_API_KEY` and `SCHOLARFLOW_JUDGE_MODEL`, then run:

```bash
uv run --project backend/packages/scholarflow-mcp scholarflow-claim-benchmark \
  scifact-dev-cases.json --output scifact-dev-result.json
```

The result records the dataset metadata, model and request IDs, predictions, label-wise
precision/recall/F1, macro-F1, accuracy, coverage, confusion matrix, and a SHA-256 over
the evaluated gold case IDs and labels.

## Claim boundary

This is an **oracle-evidence classification** benchmark: the judge receives annotated
evidence rather than retrieving it. It does not measure literature retrieval, PDF text
extraction, evidence discovery, or scientific truth. Do not compare model runs unless
the gold hash, import options, judge model, and endpoint configuration are recorded.
