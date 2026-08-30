from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from scholarflow_mcp.output import write_utf8_stdout
from scholarflow_mcp.scifact import import_scifact_cases


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert caller-downloaded SciFact JSONL files into ScholarFlow claim-evidence cases."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--exclude-insufficient", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    result = import_scifact_cases(
        args.corpus,
        args.claims,
        limit=args.limit,
        include_insufficient=not args.exclude_insufficient,
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
