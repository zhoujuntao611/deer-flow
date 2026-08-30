from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scholarflow_mcp.application import SUPPORTED_PROVIDERS, run_search
from scholarflow_mcp.output import write_utf8_stdout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scholarflow-search",
        description="Search scholarly sources and emit normalized, deduplicated JSON.",
    )
    parser.add_argument("query", help="Concise bibliographic query")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--providers", nargs="+", choices=SUPPORTED_PROVIDERS)
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    return parser


def _serialize(payload: dict[str, Any], *, compact: bool) -> str:
    if compact:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = asyncio.run(
        run_search(
            args.query,
            max_results=args.max_results,
            from_year=args.from_year,
            to_year=args.to_year,
            providers=args.providers,
        )
    )
    rendered = _serialize(payload, compact=args.compact)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)

    successful = any(status["status"] == "ok" for status in payload["provider_status"])
    return 0 if successful else 2


if __name__ == "__main__":
    raise SystemExit(main())
