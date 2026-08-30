from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from scholarflow_mcp.evidence import verify_evidence_spans
from scholarflow_mcp.output import write_utf8_stdout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that quoted evidence exists on declared document pages; semantic support is not assessed."
    )
    parser.add_argument("input", type=Path, help="JSON containing 'pages' and 'claims'")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = verify_evidence_spans(pages=payload.get("pages", []), claims=payload.get("claims", []))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    return 0 if result["summary"]["unlocated_spans"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
