from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from scholarflow_mcp.claim_eval import evaluate_claim_predictions
from scholarflow_mcp.output import write_utf8_stdout


def _items(path: Path, key: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return payload[key]
    raise ValueError(f"{path} must contain a JSON list or a '{key}' list")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate three-way claim-evidence predictions against gold labels.")
    parser.add_argument("gold", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-macro-f1", type=float)
    args = parser.parse_args(argv)

    result = evaluate_claim_predictions(_items(args.gold, "cases"), _items(args.predictions, "predictions"))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    else:
        write_utf8_stdout(rendered)
    return int(args.min_macro_f1 is not None and result["macro_f1"] < args.min_macro_f1)


if __name__ == "__main__":
    raise SystemExit(main())
