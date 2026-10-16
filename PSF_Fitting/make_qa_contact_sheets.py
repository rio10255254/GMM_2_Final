from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


SOURCE = Path(r"D:\GMM_2_Final\PSF_Fitting\qa_v22_ablation\pages")
OUTPUT = Path(r"D:\GMM_2_Final\PSF_Fitting\qa_v22_ablation\contact_sheets")
OUTPUT.mkdir(parents=True, exist_ok=True)

pages = sorted(SOURCE.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
assert len(pages) == 254

cols, rows = 4, 8
thumb_w, thumb_h = 190, 246
label_h = 20
font = ImageFont.load_default()

for sheet_index, start in enumerate(range(0, len(pages), cols * rows), start=1):
    batch = pages[start : start + cols * rows]
    canvas = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "#dddddd")
    draw = ImageDraw.Draw(canvas)
    for offset, path in enumerate(batch):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w - 4, thumb_h - 4), Image.Resampling.LANCZOS)
        col, row = offset % cols, offset // cols
        x = col * thumb_w + (thumb_w - image.width) // 2
        y = row * (thumb_h + label_h) + (thumb_h - image.height) // 2
        canvas.paste(image, (x, y))
        page_number = start + offset + 1
        draw.text((col * thumb_w + 5, row * (thumb_h + label_h) + thumb_h + 2), f"PDF page {page_number}", fill="black", font=font)
    canvas.save(OUTPUT / f"contact-{sheet_index:02d}.png", dpi=(120, 120))

print(len(list(OUTPUT.glob("contact-*.png"))))
