from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(
    r"D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results"
    r"\thesis_v8_language_cleanup"
)
SOURCE = ROOT / "original_architecture_media"
OUTPUT = ROOT / "patched_architecture_media"
DOCX = ROOT / "thesis_v8_language_working.docx"

TIMES = Path(r"C:\Windows\Fonts\times.ttf")
TIMES_BOLD = Path(r"C:\Windows\Fonts\timesbd.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(TIMES_BOLD if bold else TIMES), size=size)


def centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    spacing: int = 4,
) -> None:
    left, top, right, bottom = box
    bounds = draw.multiline_textbbox((0, 0), text, font=text_font, spacing=spacing, align="center")
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = left + (right - left - width) / 2 - bounds[0]
    y = top + (bottom - top - height) / 2 - bounds[1]
    draw.multiline_text(
        (x, y), text, font=text_font, fill=fill, spacing=spacing, align="center"
    )


def patch_network_diagram() -> Path:
    image = Image.open(SOURCE / "image41.png").convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Preserve the original architecture and replace only the two coined labels.
    orange = image.getpixel((885, 235))
    draw.rectangle((875, 225, 1007, 282), fill=orange)
    centered_text(
        draw,
        (875, 225, 1007, 282),
        "PSF residual\ncorrection",
        font(16, bold=True),
        (255, 255, 255, 255),
        spacing=1,
    )

    draw.rectangle((590, 411, 826, 447), fill=(255, 255, 255, 0))
    centered_text(
        draw,
        (590, 411, 826, 447),
        "Anti-aliased upsampling",
        font(17, bold=True),
        (220, 0, 0, 255),
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "image41.png"
    image.save(target)
    return target


def patch_legend() -> Path:
    image = Image.open(SOURCE / "image42.png").convert("RGBA")
    draw = ImageDraw.Draw(image)
    rows = [
        ((115, 0, 1806, 123), "Convolution + GroupNorm + SiLU"),
        ((115, 123, 1806, 240), "Residual block"),
        ((115, 240, 1806, 358), "Bilinear interpolation"),
        ((115, 358, 1806, 475), "Reflection padding"),
        ((115, 475, 1806, 618), "Depthwise low-pass filter"),
    ]
    label_font = font(62, bold=True)
    for box, label in rows:
        draw.rectangle(box, fill=(255, 255, 255, 0))
        left, top, right, bottom = box
        text_box = (135, top, right, bottom)
        bounds = draw.textbbox((0, 0), label, font=label_font)
        height = bounds[3] - bounds[1]
        y = top + (bottom - top - height) / 2 - bounds[1]
        draw.text((135, y), label, font=label_font, fill=(0, 0, 0, 255))

    target = OUTPUT / "image42.png"
    image.save(target)
    return target


def patch_psf_fusion_diagram() -> Path:
    image = Image.open(SOURCE / "image43.png").convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Keep all original boxes and connections. Only descriptive labels are clarified.
    blue = image.getpixel((1500, 1230))
    draw.rectangle((1450, 1235, 2198, 1352), fill=blue)
    centered_text(
        draw,
        (1450, 1235, 2198, 1352),
        "Weight estimation",
        font(70, bold=True),
        (0, 0, 0, 255),
    )

    gray = image.getpixel((2700, 1400))
    draw.rectangle((2610, 1332, 3072, 1636), fill=gray)
    centered_text(
        draw,
        (2610, 1332, 3072, 1636),
        "Weighted\nfusion",
        font(75, bold=True),
        (0, 0, 0, 255),
        spacing=2,
    )

    beta_blue = image.getpixel((3600, 1450))
    draw.rectangle((3508, 1418, 4090, 1548), fill=beta_blue)
    centered_text(
        draw,
        (3508, 1418, 4090, 1548),
        "Residual scale β",
        font(68, bold=True),
        (0, 0, 0, 255),
    )

    target = OUTPUT / "image43.png"
    image.save(target)
    return target


def replace_docx_media(replacements: dict[str, Path]) -> None:
    fd, temp_name = tempfile.mkstemp(suffix=".docx", dir=str(DOCX.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(DOCX, "r") as src, zipfile.ZipFile(
            temp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as dst:
            for item in src.infolist():
                data = replacements[item.filename].read_bytes() if item.filename in replacements else src.read(item.filename)
                dst.writestr(item, data)
        os.replace(temp_path, DOCX)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> None:
    patched = {
        "word/media/image41.png": patch_network_diagram(),
        "word/media/image42.png": patch_legend(),
        "word/media/image43.png": patch_psf_fusion_diagram(),
    }
    replace_docx_media(patched)
    print(f"Restored original architecture layout and updated labels in: {DOCX}")
    for path in patched.values():
        print(f"  {path.name}: {Image.open(path).size}")


if __name__ == "__main__":
    main()
