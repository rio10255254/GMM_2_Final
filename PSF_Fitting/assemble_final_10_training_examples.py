from __future__ import annotations

"""Assemble ten slide-ready Source/Label pairs from the reviewed selections."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
PROJECT_ROOT = Path(__file__).resolve().parents[1]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Slide_Assets/Training_Data_Representatives'))
SELECTED = ROOT / "selected"
OUTPUT = ROOT / "Final_10_Representative_Categories"

SELECTIONS = [
    {
        "number": 1,
        "slug": "mixed_boundary_fields",
        "phase": "foundation",
        "category_zh": "混合邊界場",
        "category_en": "Mixed boundary fields",
        "folder": SELECTED / "foundation" / "mixed_boundaries",
    },
    {
        "number": 2,
        "slug": "universal_mixed_shapes",
        "phase": "foundation",
        "category_zh": "多形貌混合結構",
        "category_en": "Universal mixed shapes",
        "folder": SELECTED / "foundation" / "universal_shapes",
    },
    {
        "number": 3,
        "slug": "fine_line_grid",
        "phase": "foundation",
        "category_zh": "細線格結構",
        "category_en": "Fine line grid",
        "folder": SELECTED / "expanded_foundation" / "micro_lines_grid",
    },
    {
        "number": 4,
        "slug": "edge_defects",
        "phase": "foundation",
        "category_zh": "邊緣缺陷",
        "category_en": "Edge defects",
        "folder": SELECTED / "expanded_foundation" / "micro_edge_defect",
    },
    {
        "number": 5,
        "slug": "mixed_microstructure_field",
        "phase": "foundation",
        "category_zh": "混合微結構場",
        "category_en": "Mixed microstructure field",
        "folder": SELECTED / "expanded_foundation" / "micro_mixed_field",
    },
    {
        "number": 6,
        "slug": "clean_dark_mixed_motion",
        "phase": "synthetic_precision",
        "category_zh": "乾淨暗對比混合位移",
        "category_en": "Clean dark mixed motion",
        "folder": SELECTED / "expanded_precision_synthetic" / "clean_dark_mixed",
    },
    {
        "number": 7,
        "slug": "clean_line_circle_motion",
        "phase": "synthetic_precision",
        "category_zh": "細線與圓形已知位移",
        "category_en": "Clean line-circle motion",
        "folder": SELECTED / "expanded_precision_synthetic" / "clean_dark_line_circle",
    },
    {
        "number": 8,
        "slug": "textured_dark_mixed_motion",
        "phase": "synthetic_precision",
        "category_zh": "含紋理暗對比混合位移",
        "category_en": "Textured dark mixed motion",
        "folder": SELECTED / "expanded_precision_synthetic" / "textured_dark_mixed",
    },
    {
        "number": 9,
        "slug": "step_touching_ellipses",
        "phase": "synthetic_precision",
        "category_zh": "相接橢圓步進位移",
        "category_en": "Step-like touching ellipses",
        "folder": SELECTED / "expanded_precision_synthetic" / "step_touching_ellipses",
    },
    {
        "number": 10,
        "slug": "step_dark_annulus",
        "phase": "synthetic_precision",
        "category_zh": "暗環形步進位移",
        "category_en": "Step-like dark annulus",
        "folder": SELECTED / "expanded_precision_synthetic" / "step_dark_annulus",
    },
]


def make_pair(source_path: Path, label_path: Path, output_path: Path) -> None:
    source = Image.open(source_path).convert("L")
    label = Image.open(label_path).convert("L")
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 20)
    tile = 420
    gap = 8
    margin = 8
    label_height = 30
    canvas = Image.new(
        "RGB",
        (margin * 2 + tile * 2 + gap, margin * 2 + tile + label_height),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for index, (image, caption) in enumerate(((source, "Source"), (label, "Training label"))):
        # Every selected crop is square. Resize all of them to the same display
        # footprint so 256 px and 512 px source files receive equal visual weight.
        resized = image.resize((tile, tile), Image.Resampling.LANCZOS)
        x0 = margin + index * (tile + gap)
        canvas.paste(resized.convert("RGB"), (x0, margin))
        draw.text((x0, margin + tile + 7), caption, fill="black", font=font)
    canvas.save(output_path, optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for item in SELECTIONS:
        source = item["folder"] / "01_source.png"
        label = item["folder"] / "02_training_label.png"
        if not source.exists() or not label.exists():
            raise FileNotFoundError(f"Missing reviewed pair for {item['category_en']}: {item['folder']}")
        filename = f"{item['number']:02d}_{item['slug']}.png"
        output = OUTPUT / filename
        make_pair(source, label, output)
        records.append(
            {
                **{key: value for key, value in item.items() if key != "folder"},
                "source": str(source),
                "training_label": str(label),
                "slide_image": str(output),
                "display_policy": "native grayscale values; resize only; no contrast enhancement",
            }
        )
    (OUTPUT / "selection_manifest.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
