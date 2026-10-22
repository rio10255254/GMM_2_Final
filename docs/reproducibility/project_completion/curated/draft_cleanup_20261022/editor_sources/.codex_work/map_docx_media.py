from __future__ import annotations

import hashlib
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: map_docx_media.py DOCUMENT.docx SOURCE_FIGURE_DIR")

    document = Path(sys.argv[1])
    source_dir = Path(sys.argv[2])

    sources: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            sources[digest(path.read_bytes())].append(path)

    with zipfile.ZipFile(document) as archive:
        for name in sorted(n for n in archive.namelist() if n.startswith("word/media/")):
            matches = sources.get(digest(archive.read(name)), [])
            if matches:
                print(f"{name}\t{matches[0]}")


if __name__ == "__main__":
    main()
