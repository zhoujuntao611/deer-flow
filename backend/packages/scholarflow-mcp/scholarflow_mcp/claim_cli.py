from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from scholarflow_mcp.claim_assessment import assess_claim_evidence
from scholarflow_mcp.output import write_utf8_stdout


async def _run(input_path: Path) -> dict:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return await assess_claim_evidence(pages=payload.get("pages", []), claims=payload.get("claims", []))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Locate supplied quotes and classify claim support with the configured model judge."
    )
    parser.add_argument("input", type=Path, help="JSON containing 'pages' and 'claims'")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    result = asyncio.run(_run(args.input))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
