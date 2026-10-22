from __future__ import annotations

import hashlib
import io
import os
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def conform_size(data: bytes, target_size: tuple[int, int], name: str) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        if image.size == target_size:
            return data
        if abs(image.width - target_size[0]) > 16 or abs(image.height - target_size[1]) > 16:
            raise RuntimeError(
                f"image dimensions changed too much for {name}: {image.size} -> {target_size}"
            )
        converted = image.convert("RGB")
        canvas = Image.new("RGB", target_size, "white")
        left = (target_size[0] - converted.width) // 2
        top = (target_size[1] - converted.height) // 2
        source_left = max(0, -left)
        source_top = max(0, -top)
        source_right = min(converted.width, target_size[0] - left)
        source_bottom = min(converted.height, target_size[1] - top)
        cropped = converted.crop((source_left, source_top, source_right, source_bottom))
        canvas.paste(cropped, (max(0, left), max(0, top)))
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        return output.getvalue()


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: replace_docx_media.py DOCUMENT.docx ORIGINAL_FIGURES REPLACEMENT_FIGURES"
        )

    document = Path(sys.argv[1])
    original_dir = Path(sys.argv[2])
    replacement_dir = Path(sys.argv[3])
    temp_document = document.with_name(document.name + ".media-update.tmp")

    sources: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(original_dir.rglob("*")):
        if path.is_file():
            sources[digest(path.read_bytes())].append(path)

    replaced: list[tuple[str, str]] = []
    with zipfile.ZipFile(document, "r") as source_zip, zipfile.ZipFile(
        temp_document, "w"
    ) as target_zip:
        for info in source_zip.infolist():
            data = source_zip.read(info.filename)
            if info.filename.startswith("word/media/"):
                matches = sources.get(digest(data), [])
                if matches:
                    replacement = replacement_dir / matches[0].name
                    if replacement.is_file():
                        replacement_data = replacement.read_bytes()
                        data = conform_size(
                            replacement_data, image_size(data), matches[0].name
                        )
                        replaced.append((info.filename, matches[0].name))
            target_zip.writestr(info, data)

    if len(replaced) < 20:
        temp_document.unlink(missing_ok=True)
        raise RuntimeError(f"expected at least 20 figure replacements, found {len(replaced)}")

    os.replace(temp_document, document)
    for media_name, figure_name in replaced:
        print(f"{media_name}\t{figure_name}")
    print(f"REPLACED={len(replaced)}")


if __name__ == "__main__":
    main()
