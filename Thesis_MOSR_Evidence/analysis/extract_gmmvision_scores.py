"""Extract one uniquely-prefixed batch from GmmVisionTool's append-only score log."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=None)
    args = parser.parse_args()
    lines = [
        line for line in args.source.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith(f"FileName, {args.prefix}")
    ]
    if args.expected is not None and len(lines) != args.expected:
        raise RuntimeError(f"Expected {args.expected} {args.prefix!r} rows, found {len(lines)}")
    indices = []
    for line in lines:
        match = re.match(r"FileName,\s*[^,]*?(\d+)\.bmp,", line)
        if match is None:
            raise RuntimeError(f"Cannot parse frame index: {line}")
        indices.append(int(match.group(1)))
    if indices and indices != list(range(min(indices), max(indices) + 1)):
        raise RuntimeError(f"Non-contiguous indices: {indices[:3]} ... {indices[-3:]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
