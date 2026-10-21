from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PAGES = ROOT / "v19_format_pages_100dpi"
OUTPUT = ROOT / "v19_format_contact_sheets"
OUTPUT.mkdir(exist_ok=True)


def page_number(path: Path) -> int:
    return int(re.search(r"(\d+)$", path.stem).group(1))


files = sorted(PAGES.glob("page-*.jpg"), key=page_number)
font = ImageFont.load_default()
columns = 4
rows = 4
thumb_width = 320
label_height = 24
margin = 12
batch_size = columns * rows

for batch_index in range(math.ceil(len(files) / batch_size)):
    batch = files[batch_index * batch_size : (batch_index + 1) * batch_size]
    thumbs = []
    max_height = 0
    for path in batch:
        image = Image.open(path).convert("RGB")
        ratio = thumb_width / image.width
        thumb = image.resize((thumb_width, round(image.height * ratio)))
        max_height = max(max_height, thumb.height)
        thumbs.append((path, thumb))

    sheet_width = margin + columns * (thumb_width + margin)
    sheet_height = margin + rows * (max_height + label_height + margin)
    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (path, thumb) in enumerate(thumbs):
        row, column = divmod(index, columns)
        x = margin + column * (thumb_width + margin)
        y = margin + row * (max_height + label_height + margin)
        sheet.paste(thumb, (x, y + label_height))
        draw.text(
            (x, y + 4),
            f"PDF page {page_number(path)}",
            fill="black",
            font=font,
        )

    start = page_number(batch[0])
    end = page_number(batch[-1])
    sheet.save(OUTPUT / f"contact_{start:03d}_{end:03d}.jpg", quality=92)

print(f"Created {math.ceil(len(files) / batch_size)} sheets for {len(files)} pages")
