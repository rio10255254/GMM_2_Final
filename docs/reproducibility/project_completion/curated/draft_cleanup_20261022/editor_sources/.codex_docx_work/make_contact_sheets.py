from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def page_number(path: Path) -> int:
    match = re.search(r"(\d+)$", path.stem)
    if not match:
        raise ValueError(path)
    return int(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("page_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--thumb-width", type=int, default=240)
    args = parser.parse_args()

    pages = sorted(args.page_dir.glob("page-*.png"), key=page_number)
    if not pages:
        raise RuntimeError("No page PNG files found")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    first = Image.open(pages[0])
    ratio = first.height / first.width
    thumb_h = round(args.thumb_width * ratio)
    label_h = 28
    margin = 12
    sheet_w = args.columns * args.thumb_width + (args.columns + 1) * margin
    sheet_h = args.rows * (thumb_h + label_h) + (args.rows + 1) * margin
    font = ImageFont.load_default(size=18)
    per_sheet = args.columns * args.rows

    for sheet_index in range(0, len(pages), per_sheet):
        batch = pages[sheet_index : sheet_index + per_sheet]
        canvas = Image.new("RGB", (sheet_w, sheet_h), "#c9c9c9")
        draw = ImageDraw.Draw(canvas)
        for slot, path in enumerate(batch):
            row, col = divmod(slot, args.columns)
            x = margin + col * (args.thumb_width + margin)
            y = margin + row * (thumb_h + label_h + margin)
            page = Image.open(path).convert("RGB")
            page.thumbnail((args.thumb_width, thumb_h), Image.Resampling.LANCZOS)
            canvas.paste(page, (x, y))
            label = f"Page {page_number(path)}"
            box = draw.textbbox((0, 0), label, font=font)
            tx = x + (args.thumb_width - (box[2] - box[0])) // 2
            draw.text((tx, y + thumb_h + 3), label, fill="black", font=font)
        start = page_number(batch[0])
        end = page_number(batch[-1])
        canvas.save(args.output_dir / f"contact_{start:03d}_{end:03d}.png")

    print(f"PAGES={len(pages)}")
    print(f"SHEETS={(len(pages) + per_sheet - 1) // per_sheet}")


if __name__ == "__main__":
    main()
