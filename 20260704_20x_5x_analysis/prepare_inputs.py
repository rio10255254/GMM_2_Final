from __future__ import annotations

import csv
import os
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[1]


ANALYSIS_ROOT = Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis'))
SOURCES = [
    {
        "group": "20x_0p5um",
        "magnification": "20x",
        "step_label": "0.5um",
        "nominal_step_um": 0.5,
        "source_dir": Path(str(PROJECT_ROOT / '20260704_20x/0.5um')),
    },
    {
        "group": "20x_1um",
        "magnification": "20x",
        "step_label": "1um",
        "nominal_step_um": 1.0,
        "source_dir": Path(str(PROJECT_ROOT / '20260704_20x/1um')),
    },
    {
        "group": "5x_0p5um",
        "magnification": "5x",
        "step_label": "0.5um",
        "nominal_step_um": 0.5,
        "source_dir": Path(str(PROJECT_ROOT / '20260704_5x/0.5um')),
    },
    {
        "group": "5x_1um",
        "magnification": "5x",
        "step_label": "1um",
        "nominal_step_um": 1.0,
        "source_dir": Path(str(PROJECT_ROOT / '20260704_5x/1um')),
    },
]


def image_files(path: Path) -> list[Path]:
    exts = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts)


def link_or_copy(src: Path, dst: Path) -> str:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def main() -> None:
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    mapping_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for spec in SOURCES:
        group = str(spec["group"])
        src_dir = Path(spec["source_dir"])
        files = image_files(src_dir)
        if not files:
            raise FileNotFoundError(f"No image files found in {src_dir}")

        out_dir = ANALYSIS_ROOT / "raw_inputs" / group / "bmp"
        out_dir.mkdir(parents=True, exist_ok=True)
        for stale in out_dir.glob("*.bmp"):
            stale.unlink()

        first_size = None
        first_mode = None
        for idx, src in enumerate(files):
            work_name = f"frame_{idx:04d}.bmp"
            dst = out_dir / work_name
            link_mode = link_or_copy(src, dst)
            with Image.open(dst) as im:
                size = f"{im.size[0]}x{im.size[1]}"
                mode = im.mode
            if first_size is None:
                first_size = size
                first_mode = mode
            ts = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            mapping_rows.append(
                {
                    "group": group,
                    "magnification": spec["magnification"],
                    "step_label": spec["step_label"],
                    "nominal_step_um": spec["nominal_step_um"],
                    "index": idx,
                    "work_name": work_name,
                    "original_name": src.name,
                    "original_path": str(src),
                    "work_path": str(dst),
                    "timestamp": ts,
                    "link_mode": link_mode,
                    "bytes": src.stat().st_size,
                    "image_size": size,
                    "mode": mode,
                }
            )

        summary_rows.append(
            {
                "group": group,
                "magnification": spec["magnification"],
                "step_label": spec["step_label"],
                "nominal_step_um": spec["nominal_step_um"],
                "source_dir": str(src_dir),
                "raw_input_dir": str(out_dir),
                "image_count": len(files),
                "first_file": files[0].name,
                "last_file": files[-1].name,
                "image_size": first_size,
                "mode": first_mode,
            }
        )

    with (ANALYSIS_ROOT / "input_mapping.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(mapping_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(mapping_rows)

    with (ANALYSIS_ROOT / "input_summary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Prepared {len(summary_rows)} groups at {ANALYSIS_ROOT}")
    for row in summary_rows:
        print(f"{row['group']}: {row['image_count']} images, {row['image_size']}, {row['mode']}")


if __name__ == "__main__":
    main()
