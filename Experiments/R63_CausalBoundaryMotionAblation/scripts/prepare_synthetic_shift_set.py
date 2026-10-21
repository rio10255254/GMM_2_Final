"""Create a pre-registered shift set from the package-manifest-unseen 50x SEM-CD capture."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import shift as ndi_shift


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
SOURCE_TABLE = (
    REPO_ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
    / "cd"
    / "tables"
    / "center9_cd_per_pillar.csv"
)
OUTPUT_ROOT = EXPERIMENT_ROOT / "results" / "synthetic_shift_inputs" / "50x_unseen"
PATCH_SIZE = 256
MAGNITUDES = (0.08, 0.4, 0.8, 2.0, 8.0)
DIRECTION_DEGREES = tuple(range(0, 360, 45))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def name_number(value: float) -> str:
    sign = "p" if value >= 0 else "m"
    return f"{sign}{abs(value):07.3f}".replace(".", "p")


def main() -> None:
    table = pd.read_csv(SOURCE_TABLE)
    if len(table) != 9:
        raise RuntimeError(f"Expected nine SEM-linked pillars, found {len(table)}")
    source_paths = {Path(value) for value in table["raw_source_image"].unique()}
    if len(source_paths) != 1:
        raise RuntimeError(f"Expected one shared Raw image, found {source_paths}")
    source_path = next(iter(source_paths))
    with Image.open(source_path) as image:
        source = np.asarray(image.convert("L"), dtype=np.float32)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    half = PATCH_SIZE // 2
    for row in table.itertuples(index=False):
        center_x = float(row.raw_x_px)
        center_y = float(row.raw_y_px)
        x0 = int(round(center_x)) - half
        y0 = int(round(center_y)) - half
        patch = source[y0 : y0 + PATCH_SIZE, x0 : x0 + PATCH_SIZE]
        if patch.shape != (PATCH_SIZE, PATCH_SIZE):
            raise RuntimeError(f"P{row.sem_index}: bad crop shape {patch.shape}")
        ref_name = f"P{int(row.sem_index):02d}_ref.bmp"
        Image.fromarray(np.clip(np.rint(patch), 0, 255).astype(np.uint8)).save(OUTPUT_ROOT / ref_name)
        records.append(
            {
                "pillar_id": int(row.sem_index),
                "case": "reference",
                "magnitude_px": 0.0,
                "direction_deg": 0,
                "true_dx_px": 0.0,
                "true_dy_px": 0.0,
                "reference_file": ref_name,
                "file": ref_name,
                "source_center_x_px": center_x,
                "source_center_y_px": center_y,
            }
        )
        for magnitude in MAGNITUDES:
            for direction in DIRECTION_DEGREES:
                radians = math.radians(direction)
                dx = magnitude * math.cos(radians)
                dy = magnitude * math.sin(radians)
                shifted = ndi_shift(
                    patch,
                    shift=(dy, dx),
                    order=3,
                    mode="reflect",
                    prefilter=True,
                )
                filename = (
                    f"P{int(row.sem_index):02d}_mag{str(magnitude).replace('.', 'p')}"
                    f"_a{direction:03d}_dx{name_number(dx)}_dy{name_number(dy)}.bmp"
                )
                Image.fromarray(np.clip(np.rint(shifted), 0, 255).astype(np.uint8)).save(
                    OUTPUT_ROOT / filename
                )
                records.append(
                    {
                        "pillar_id": int(row.sem_index),
                        "case": "shifted",
                        "magnitude_px": magnitude,
                        "direction_deg": direction,
                        "true_dx_px": dx,
                        "true_dy_px": dy,
                        "reference_file": ref_name,
                        "file": filename,
                        "source_center_x_px": center_x,
                        "source_center_y_px": center_y,
                    }
                )

    manifest_csv = OUTPUT_ROOT / "shift_manifest.csv"
    with manifest_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    expected = 9 * (1 + len(MAGNITUDES) * len(DIRECTION_DEGREES))
    if len(records) != expected:
        raise RuntimeError(f"Expected {expected} cases, created {len(records)}")
    metadata = {
        "source_image": str(source_path.resolve()),
        "source_sha256": sha256(source_path),
        "source_training_manifest_matches": 0,
        "patch_size": PATCH_SIZE,
        "pillar_count": 9,
        "magnitudes_px": list(MAGNITUDES),
        "direction_degrees": list(DIRECTION_DEGREES),
        "interpolation": "scipy.ndimage.shift order=3 mode=reflect",
        "case_count": len(records),
        "shifted_case_count": len(records) - 9,
        "manifest": str(manifest_csv.resolve()),
    }
    (OUTPUT_ROOT / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
