from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def key(path: Path):
    m = re.match(r"fig6-(\d+)_(\d+)", path.stem)
    return tuple(map(int, m.groups())) if m else (999, 999)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=999)
    ap.add_argument("--columns", type=int, default=3)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--cell-width", type=int, default=500)
    ap.add_argument("--cell-height", type=int, default=390)
    args = ap.parse_args()
    files = [p for p in args.input_dir.glob("fig6-*.png") if args.start <= key(p)[0] <= args.end]
    files.sort(key=key)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    margin, label_h = 16, 32
    font = ImageFont.load_default(size=20)
    per = args.columns * args.rows
    for batch_no, pos in enumerate(range(0, len(files), per), start=1):
        batch = files[pos:pos+per]
        w = margin + args.columns * (args.cell_width + margin)
        h = margin + args.rows * (args.cell_height + label_h + margin)
        canvas = Image.new("RGB", (w, h), "#d3d3d3")
        draw = ImageDraw.Draw(canvas)
        for slot, path in enumerate(batch):
            row, col = divmod(slot, args.columns)
            x = margin + col * (args.cell_width + margin)
            y = margin + row * (args.cell_height + label_h + margin)
            im = Image.open(path).convert("RGB")
            im.thumbnail((args.cell_width, args.cell_height), Image.Resampling.LANCZOS)
            px = x + (args.cell_width - im.width)//2
            py = y + (args.cell_height - im.height)//2
            canvas.paste(im, (px, py))
            label = path.stem
            bbox = draw.textbbox((0,0), label, font=font)
            draw.text((x + (args.cell_width-(bbox[2]-bbox[0]))//2, y+args.cell_height+4), label, fill="black", font=font)
        canvas.save(args.output_dir / f"figures_{batch_no:02d}.png")
    print(f"files={len(files)} sheets={(len(files)+per-1)//per}")


if __name__ == "__main__":
    main()
