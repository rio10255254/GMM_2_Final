from pathlib import Path

from PIL import Image, ImageDraw


SEM_DIR = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\20260618_100MG\SEM_data")
OUT_DIR = Path(__file__).resolve().parent / "sem_previews"
OUT_DIR.mkdir(parents=True, exist_ok=True)

thumbs = []
for index in range(1, 10):
    source = SEM_DIR / f"P-{index:02d}.tiff"
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        rgb = background.convert("RGB")
        preview_path = OUT_DIR / f"P-{index:02d}.png"
        rgb.save(preview_path)

        thumb = rgb.copy()
        thumb.thumbnail((480, 380), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (500, 420), "white")
        canvas.paste(thumb, ((500 - thumb.width) // 2, 26))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 6), f"P-{index:02d}", fill="black")
        thumbs.append(canvas)

contact = Image.new("RGB", (1500, 1260), "white")
for index, thumb in enumerate(thumbs):
    contact.paste(thumb, ((index % 3) * 500, (index // 3) * 420))
contact.save(OUT_DIR / "pillar_sem_contact_sheet.png")
print(OUT_DIR)
