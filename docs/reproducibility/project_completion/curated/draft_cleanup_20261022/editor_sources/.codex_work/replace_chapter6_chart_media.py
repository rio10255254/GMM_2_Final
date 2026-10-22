from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

from PIL import Image


MEDIA_TO_FIGURE = {
    "image65.png": "00c_signed_pillar_contrast.png",
    "image75.png": "08_center9_cd_error_summary.png",
    "image78.png": "10_50x_0p5um_step_trace.png",
    "image79.png": "11_50x_1um_step_trace.png",
    "image80.png": "12_20x_0p5um_step_trace.png",
    "image81.png": "13_20x_1um_step_trace.png",
    "image82.png": "14_step_stability_summary.png",
    "image83.png": "15_nine_pillar_consistency_summary.png",
    "image84.png": "16_nominal_command_consistency.png",
    "image85.png": "17_stepwise_local_improvement_rate.png",
    "image88.png": "20_20x_0p5um_usable_vs_top30.png",
}


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def conform_size(data: bytes, target_size: tuple[int, int], name: str) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        if image.size == target_size:
            return data
        if abs(image.width - target_size[0]) > 20 or abs(image.height - target_size[1]) > 20:
            raise RuntimeError(
                f"image dimensions changed too much for {name}: {image.size} -> {target_size}"
            )
        converted = image.convert("RGB")
        canvas = Image.new("RGB", target_size, "white")
        left = (target_size[0] - converted.width) // 2
        top = (target_size[1] - converted.height) // 2
        source_left = max(0, -left)
        source_top = max(0, -top)
        source_right = min(converted.width, target_size[0] - left)
        source_bottom = min(converted.height, target_size[1] - top)
        cropped = converted.crop((source_left, source_top, source_right, source_bottom))
        canvas.paste(cropped, (max(0, left), max(0, top)))
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        return output.getvalue()


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: replace_chapter6_chart_media.py INPUT.docx OUTPUT.docx FIGURE_DIR"
        )

    input_document = Path(sys.argv[1])
    output_document = Path(sys.argv[2])
    figure_dir = Path(sys.argv[3])
    if input_document.resolve() == output_document.resolve():
        raise RuntimeError("Input and output documents must differ.")

    missing = [name for name in MEDIA_TO_FIGURE.values() if not (figure_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"Missing replacement figures: {missing}")

    replaced: list[tuple[str, str, tuple[int, int], tuple[int, int]]] = []
    with zipfile.ZipFile(input_document, "r") as source_zip, zipfile.ZipFile(
        output_document, "w"
    ) as target_zip:
        for info in source_zip.infolist():
            data = source_zip.read(info.filename)
            if info.filename.startswith("word/media/"):
                media_name = Path(info.filename).name
                figure_name = MEDIA_TO_FIGURE.get(media_name)
                if figure_name:
                    source_size = image_size(data)
                    replacement_data = (figure_dir / figure_name).read_bytes()
                    replacement_size = image_size(replacement_data)
                    data = conform_size(replacement_data, source_size, figure_name)
                    replaced.append((media_name, figure_name, source_size, replacement_size))
            target_zip.writestr(info, data)

    if len(replaced) != len(MEDIA_TO_FIGURE):
        output_document.unlink(missing_ok=True)
        raise RuntimeError(
            f"Expected {len(MEDIA_TO_FIGURE)} replacements, found {len(replaced)}"
        )

    for media_name, figure_name, source_size, replacement_size in replaced:
        print(f"{media_name}\t{figure_name}\t{source_size}\t{replacement_size}")
    print(f"REPLACED={len(replaced)}")


if __name__ == "__main__":
    main()
