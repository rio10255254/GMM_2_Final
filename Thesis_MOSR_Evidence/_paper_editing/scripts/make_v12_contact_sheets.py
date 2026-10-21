from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\_paper_editing\qa\v12_final_render_20260720_c")
PAGES = ROOT / "pages"
CONTACTS = ROOT / "contact_sheets"
REPORT = ROOT / "page_image_audit.json"


def get_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def main() -> None:
    page_paths = sorted(PAGES.glob("page-*.png"))
    if len(page_paths) != 228:
        raise RuntimeError(f"Expected 228 rendered pages, found {len(page_paths)}")

    CONTACTS.mkdir(parents=True, exist_ok=True)
    thumb_w, thumb_h = 320, 452
    cell_w, cell_h = 350, 500
    cols, rows = 4, 4
    font = get_font(22)
    audit: list[dict[str, object]] = []

    for page_number, path in enumerate(page_paths, start=1):
        with Image.open(path) as im:
            gray = im.convert("L")
            mask = gray.point(lambda value: 255 if value < 245 else 0)
            bbox = mask.getbbox()
            histogram = gray.histogram()
            ink = sum(histogram[:245])
            total = gray.width * gray.height
            audit.append(
                {
                    "page": page_number,
                    "size": [gray.width, gray.height],
                    "ink_fraction": ink / total,
                    "ink_bbox": list(bbox) if bbox else None,
                    "possibly_blank": bbox is None or ink / total < 0.0004,
                    "touches_outer_10px": bool(
                        bbox
                        and (
                            bbox[0] <= 10
                            or bbox[1] <= 10
                            or bbox[2] >= gray.width - 10
                            or bbox[3] >= gray.height - 10
                        )
                    ),
                }
            )

    for start in range(0, len(page_paths), cols * rows):
        canvas = Image.new("RGB", (cell_w * cols, cell_h * rows), "#d8d8d8")
        draw = ImageDraw.Draw(canvas)
        batch = page_paths[start : start + cols * rows]
        for offset, path in enumerate(batch):
            page_number = start + offset + 1
            row, col = divmod(offset, cols)
            x = col * cell_w + (cell_w - thumb_w) // 2
            y = row * cell_h + 38
            with Image.open(path) as im:
                thumb = im.convert("RGB")
                thumb.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                px = x + (thumb_w - thumb.width) // 2
                py = y + (thumb_h - thumb.height) // 2
                canvas.paste(thumb, (px, py))
            label = f"Page {page_number}"
            label_box = draw.textbbox((0, 0), label, font=font)
            label_w = label_box[2] - label_box[0]
            draw.text((col * cell_w + (cell_w - label_w) // 2, row * cell_h + 7), label, fill="black", font=font)
        sheet_number = start // (cols * rows) + 1
        canvas.save(CONTACTS / f"contact_{sheet_number:02d}_pages_{start + 1:03d}-{start + len(batch):03d}.png")

    summary = {
        "rendered_pages": len(page_paths),
        "contact_sheets": len(list(CONTACTS.glob("contact_*.png"))),
        "possibly_blank_pages": [row["page"] for row in audit if row["possibly_blank"]],
        "outer_edge_pages": [row["page"] for row in audit if row["touches_outer_10px"]],
        "pages": audit,
    }
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "pages"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
