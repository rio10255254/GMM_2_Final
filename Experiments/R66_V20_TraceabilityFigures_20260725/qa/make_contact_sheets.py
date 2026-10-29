import argparse
from pathlib import Path

from PIL import Image, ImageDraw
PROJECT_ROOT = Path(__file__).resolve().parents[3]


DEFAULT_ROOT = Path(
    str(PROJECT_ROOT / 'Experiments/R66_V20_TraceabilityFigures_20260725/qa/v20_final_render')
)
COLS = 4
ROWS = 3
THUMB = (248, 350)
LABEL_H = 24
MARGIN = 12


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root
    out = root / "contact_sheets"
    pages = sorted(
        root.glob("page-*.png"),
        key=lambda p: int(p.stem.split("-")[-1]),
    )
    if not pages:
        raise RuntimeError("No rendered page PNGs found")
    out.mkdir(parents=True, exist_ok=True)
    per_sheet = COLS * ROWS
    for start in range(0, len(pages), per_sheet):
        batch = pages[start : start + per_sheet]
        width = MARGIN + COLS * (THUMB[0] + MARGIN)
        height = MARGIN + ROWS * (THUMB[1] + LABEL_H + MARGIN)
        sheet = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(sheet)
        for offset, page in enumerate(batch):
            row, col = divmod(offset, COLS)
            x = MARGIN + col * (THUMB[0] + MARGIN)
            y = MARGIN + row * (THUMB[1] + LABEL_H + MARGIN)
            with Image.open(page) as source:
                thumb = source.convert("RGB")
                thumb.thumbnail(THUMB)
                px = x + (THUMB[0] - thumb.width) // 2
                py = y + (THUMB[1] - thumb.height) // 2
                sheet.paste(thumb, (px, py))
            page_number = int(page.stem.split("-")[-1])
            draw.text((x, y + THUMB[1] + 4), f"PDF page {page_number}", fill="black")
        first = int(batch[0].stem.split("-")[-1])
        last = int(batch[-1].stem.split("-")[-1])
        sheet.save(out / f"pages_{first:03d}_{last:03d}.jpg", quality=90)
    print(f"Created {len(list(out.glob('*.jpg')))} contact sheets for {len(pages)} pages")


if __name__ == "__main__":
    main()
