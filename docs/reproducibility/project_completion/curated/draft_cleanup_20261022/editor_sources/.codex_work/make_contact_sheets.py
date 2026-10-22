from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def page_number(path: Path) -> int:
    return int(re.search(r"(\d+)$", path.stem).group(1))


def main() -> None:
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    columns = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    rows = columns
    group_size = columns * rows
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("sheet_*.png"):
        old.unlink()

    pages = sorted(source.glob("page-*.png"), key=page_number)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    for start in range(0, len(pages), group_size):
        group = pages[start : start + group_size]
        with Image.open(group[0]) as first:
            width, height = first.size
        bar = 42
        sheet = Image.new("RGB", (width * columns, (height + bar) * rows), "#d0d0d0")
        draw = ImageDraw.Draw(sheet)
        for offset, path in enumerate(group):
            page = Image.open(path).convert("RGB")
            col, row = offset % columns, offset // columns
            x, y = col * width, row * (height + bar)
            draw.rectangle((x, y, x + width, y + bar), fill="white")
            draw.text((x + 14, y + 6), f"Page {page_number(path)}", fill="black", font=font)
            sheet.paste(page, (x, y + bar))
            page.close()
        first_page = page_number(group[0])
        last_page = page_number(group[-1])
        target = output / f"sheet_{start // group_size + 1:03d}_pages_{first_page:03d}_{last_page:03d}.png"
        sheet.save(target, optimize=True)
        sheet.close()
    print(f"sheets={len(list(output.glob('sheet_*.png')))} pages={len(pages)}")


if __name__ == "__main__":
    main()
