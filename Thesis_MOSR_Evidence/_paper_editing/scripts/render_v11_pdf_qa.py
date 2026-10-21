from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont


PDF = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\_paper_editing\qa\v11_render_20260718\論文完整版_20260716_v11.pdf")
ROOT = PDF.parent
PAGE_DIR = ROOT / "pages"
CONTACT_DIR = ROOT / "contact_sheets"
HIGH_DIR = ROOT / "highres"
MANIFEST = ROOT / "visual_qa_manifest.json"

HIGHRES_PAGES = {
    1, 2, 3, 4, 6, 7, 8, 9, 10, 11,
    16, 21, 37, 38, 50, 60, 74, 75, 76, 90, 100, 112,
    113, 114, 145, 146, 147, 156, 165, 175, 190, 200,
    206, 207, 208, 209, 210, 211, 220, 221,
}


def page_metrics(image: Image.Image) -> dict:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    ink = gray < 245
    h, w = ink.shape
    border = max(3, int(round(min(h, w) * 0.012)))
    edge = np.zeros_like(ink)
    edge[:border, :] = True
    edge[-border:, :] = True
    edge[:, :border] = True
    edge[:, -border:] = True
    return {
        "width": int(w),
        "height": int(h),
        "ink_fraction": float(ink.mean()),
        "border_ink_fraction": float((ink & edge).sum() / max(1, edge.sum())),
    }


def make_contact_sheet(page_paths: list[Path], start_page: int, output: Path) -> None:
    cols, rows = 4, 5
    thumb_w, thumb_h = 300, 424
    label_h, gap = 28, 12
    canvas = Image.new(
        "RGB",
        (cols * thumb_w + (cols + 1) * gap, rows * (thumb_h + label_h) + (rows + 1) * gap),
        "#d8d8d8",
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    for idx, path in enumerate(page_paths):
        row, col = divmod(idx, cols)
        x = gap + col * (thumb_w + gap)
        y = gap + row * (thumb_h + label_h + gap)
        with Image.open(path) as im:
            page = im.convert("RGB")
            page.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            px = x + (thumb_w - page.width) // 2
            py = y + (thumb_h - page.height) // 2
            canvas.paste(page, (px, py))
        label = f"Page {start_page + idx}"
        draw.text((x + 4, y + thumb_h + 4), label, fill="black", font=font)
    canvas.save(output, optimize=True)


def main() -> None:
    if not PDF.exists():
        raise FileNotFoundError(PDF)
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    HIGH_DIR.mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(PDF))
    page_records = []
    page_paths: list[Path] = []
    for index in range(len(pdf)):
        page_no = index + 1
        page = pdf[index]
        image = page.render(scale=1.15).to_pil().convert("RGB")
        out = PAGE_DIR / f"page-{page_no:03d}.png"
        image.save(out, optimize=True)
        metrics = page_metrics(image)
        metrics.update({"page": page_no, "path": str(out)})
        page_records.append(metrics)
        page_paths.append(out)
        if page_no in HIGHRES_PAGES:
            high = page.render(scale=2.15).to_pil().convert("RGB")
            high.save(HIGH_DIR / f"page-{page_no:03d}.png", optimize=True)

    contact_paths = []
    batch = 20
    for start in range(0, len(page_paths), batch):
        group = page_paths[start:start + batch]
        out = CONTACT_DIR / f"contact-{start + 1:03d}-{start + len(group):03d}.png"
        make_contact_sheet(group, start + 1, out)
        contact_paths.append(str(out))

    manifest = {
        "pdf": str(PDF),
        "page_count": len(page_records),
        "rendered_page_count": len(page_paths),
        "contact_sheet_count": len(contact_paths),
        "highres_pages": sorted(HIGHRES_PAGES),
        "blank_like_pages": [r["page"] for r in page_records if r["ink_fraction"] < 0.001],
        "high_border_ink_pages": [r["page"] for r in page_records if r["border_ink_fraction"] > 0.02],
        "contact_sheets": contact_paths,
        "pages": page_records,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in (
        "page_count", "rendered_page_count", "contact_sheet_count",
        "blank_like_pages", "high_border_ink_pages"
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
