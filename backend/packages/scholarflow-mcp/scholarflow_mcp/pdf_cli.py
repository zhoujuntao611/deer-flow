from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from scholarflow_mcp.output import write_utf8_stdout
from scholarflow_mcp.pdf import DEFAULT_MAX_PAGES, MAX_PDF_BYTES, extract_pdf_pages


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract bounded embedded text from a local PDF without OCR or network access."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if args.input.stat().st_size > MAX_PDF_BYTES:
        parser.error(f"PDF must contain at most {MAX_PDF_BYTES} bytes")
    result = extract_pdf_pages(
        args.input.read_bytes(),
        document_id=args.document_id,
        max_pages=args.max_pages,
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
