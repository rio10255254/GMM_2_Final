from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


def page_number(path: Path) -> int:
    return int(path.stem.rsplit("-", 1)[-1])


def content_metrics(image: Image.Image) -> dict[str, float | int]:
    gray = image.convert("L")
    background = Image.new("L", gray.size, 255)
    difference = ImageChops.difference(gray, background)
    mask = difference.point(lambda value: 255 if value > 12 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return {
            "ink_percent": 0.0,
            "left": -1,
            "top": -1,
            "right": -1,
            "bottom": -1,
            "top_margin_percent": 100.0,
            "bottom_margin_percent": 100.0,
        }

    histogram = mask.histogram()
    ink_pixels = histogram[255]
    width, height = gray.size
    return {
        "ink_percent": ink_pixels * 100.0 / (width * height),
        "left": bbox[0],
        "top": bbox[1],
        "right": bbox[2],
        "bottom": bbox[3],
        "top_margin_percent": bbox[1] * 100.0 / height,
        "bottom_margin_percent": (height - bbox[3]) * 100.0 / height,
    }


def build_sheet(paths: list[Path], output: Path) -> None:
    page_width = 600
    page_height = 848
    label_height = 30
    gutter = 18
    margin = 18
    sheet = Image.new(
        "RGB",
        (
            margin * 2 + page_width * 2 + gutter,
            margin * 2 + (page_height + label_height) * 2 + gutter,
        ),
        "#d7d7d7",
    )
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(paths):
        page = Image.open(path).convert("RGB")
        page.thumbnail((page_width, page_height), Image.Resampling.LANCZOS)
        row, column = divmod(index, 2)
        x = margin + column * (page_width + gutter)
        y = margin + row * (page_height + label_height + gutter)
        draw.rectangle((x, y, x + page_width, y + label_height - 1), fill="white")
        draw.text((x + 8, y + 7), f"Physical page {page_number(path)}", fill="black")
        image_x = x + (page_width - page.width) // 2
        image_y = y + label_height + (page_height - page.height) // 2
        sheet.paste(page, (image_x, image_y))
        draw.rectangle(
            (image_x, image_y, image_x + page.width - 1, image_y + page.height - 1),
            outline="#777777",
            width=1,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("render_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    pages = sorted(args.render_dir.glob("page-*.png"), key=page_number)
    if not pages:
        raise RuntimeError(f"No rendered pages found in {args.render_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(pages), 4):
        batch = pages[start : start + 4]
        end = page_number(batch[-1])
        name = f"pages-{page_number(batch[0]):03d}-{end:03d}.jpg"
        build_sheet(batch, args.output_dir / name)

    metrics_path = args.output_dir / "page_layout_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = [
            "page",
            "ink_percent",
            "left",
            "top",
            "right",
            "bottom",
            "top_margin_percent",
            "bottom_margin_percent",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for path in pages:
            row = {"page": page_number(path), **content_metrics(Image.open(path))}
            writer.writerow(row)

    print(f"Pages: {len(pages)}")
    print(f"Sheets: {(len(pages) + 3) // 4}")
    print(f"Metrics: {metrics_path}")


if __name__ == "__main__":
    main()
