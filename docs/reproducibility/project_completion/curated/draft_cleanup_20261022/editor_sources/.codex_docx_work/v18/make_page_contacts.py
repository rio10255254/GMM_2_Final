from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
PROJECT_ROOT = Path(__file__).resolve().parents[8]


SOURCE = Path(str(PROJECT_ROOT / 'PSF_Fitting/.codex_docx_work/v18/word_pages'))
OUTPUT = Path(str(PROJECT_ROOT / 'PSF_Fitting/.codex_docx_work/v18/word_contacts'))


def page_number(path: Path) -> int:
    match = re.search(r"-(\d+)\.png$", path.name)
    return int(match.group(1))


def main() -> None:
    pages = sorted(SOURCE.glob("page-*.png"), key=page_number)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=20)
    cols, rows = 4, 3
    cell_w, cell_h, label_h, margin = 300, 390, 30, 12
    per_sheet = cols * rows
    for chunk_index, start in enumerate(range(0, len(pages), per_sheet), 1):
        chunk = pages[start : start + per_sheet]
        canvas = Image.new(
            "RGB",
            (margin + cols * (cell_w + margin), margin + rows * (cell_h + label_h + margin)),
            "#d6d6d6",
        )
        draw = ImageDraw.Draw(canvas)
        for i, page in enumerate(chunk):
            row, col = divmod(i, cols)
            x = margin + col * (cell_w + margin)
            y = margin + row * (cell_h + label_h + margin)
            image = Image.open(page).convert("RGB")
            image.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            canvas.paste(image, (x + (cell_w - image.width) // 2, y + (cell_h - image.height) // 2))
            draw.text((x, y + cell_h + 3), f"PDF page {page_number(page)}", fill="black", font=font)
        canvas.save(OUTPUT / f"contact_{chunk_index:02d}.png")
    print(f"pages={len(pages)} contacts={(len(pages)+per_sheet-1)//per_sheet}")


if __name__ == "__main__":
    main()
