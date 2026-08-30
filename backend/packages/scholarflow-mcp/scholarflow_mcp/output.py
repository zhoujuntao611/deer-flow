from __future__ import annotations

import sys


def write_utf8_stdout(value: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    print(value)
