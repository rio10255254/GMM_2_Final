from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--columns", type=int, default=3)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--cell-width", type=int, default=520)
    ap.add_argument("--cell-height", type=int, default=390)
    args = ap.parse_args()
    files = sorted(args.input_dir.glob("*.png"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    margin, label_h = 14, 34
    font = ImageFont.load_default(size=18)
    per = args.columns * args.rows
    for no, start in enumerate(range(0, len(files), per), start=1):
        batch = files[start:start+per]
        w = margin + args.columns * (args.cell_width + margin)
        h = margin + args.rows * (args.cell_height + label_h + margin)
        canvas = Image.new("RGB", (w, h), "#d0d0d0")
        draw = ImageDraw.Draw(canvas)
        for slot, path in enumerate(batch):
            row, col = divmod(slot, args.columns)
            x = margin + col * (args.cell_width + margin)
            y = margin + row * (args.cell_height + label_h + margin)
            im = Image.open(path).convert("RGB")
            im.thumbnail((args.cell_width, args.cell_height), Image.Resampling.LANCZOS)
            canvas.paste(im, (x+(args.cell_width-im.width)//2, y+(args.cell_height-im.height)//2))
            label = path.stem
            box = draw.textbbox((0,0), label, font=font)
            draw.text((x+(args.cell_width-(box[2]-box[0]))//2, y+args.cell_height+5), label, fill="black", font=font)
        canvas.save(args.output_dir / f"contact_{no:02d}.png")
    print(f"files={len(files)} sheets={(len(files)+per-1)//per}")


if __name__ == "__main__":
    main()
