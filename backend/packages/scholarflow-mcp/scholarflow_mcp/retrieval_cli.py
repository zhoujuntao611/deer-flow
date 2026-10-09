from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from scholarflow_mcp.output import write_utf8_stdout
from scholarflow_mcp.retrieval import assess_retrieved_claim_evidence, retrieve_claim_evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Retrieve page-level evidence candidates for claims in a JSON artifact."
    )
    parser.add_argument("input", type=Path, help="JSON containing 'pages' and 'claims'")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-characters", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--mode", choices=("hybrid", "word_bm25"), default="hybrid")
    parser.add_argument("--assess", action="store_true", help="Run the configured model judge on retrieved candidates")
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    options = {
        "pages": payload.get("pages", []),
        "claims": payload.get("claims", []),
        "top_k": args.top_k,
        "chunk_characters": args.chunk_characters,
        "chunk_overlap": args.chunk_overlap,
        "mode": args.mode,
    }
    result = (
        asyncio.run(assess_retrieved_claim_evidence(**options)) if args.assess else retrieve_claim_evidence(**options)
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
