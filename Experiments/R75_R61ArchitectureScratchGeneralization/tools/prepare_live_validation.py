"""Prepare the fixed thesis center-nine pillar crop for observation-only validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SOURCE_IMAGE = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/20260618_100MG/Image__2026-06-18__17-10-31.bmp')
)
OUTPUT_DIR = EXPERIMENT_DIR / "data" / "live_validation"
OUTPUT_IMAGE = OUTPUT_DIR / "pillar_center9_50x_raw.bmp"
CROP_X = 713
CROP_Y = 628
CROP_WIDTH = 232
CROP_HEIGHT = 232
PILLAR_IDS = [22, 23, 24, 28, 29, 30, 34, 35, 36]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"無法讀取九宮格來源影像：{path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(f"無法寫出九宮格觀察影像：{path}")
    encoded.tofile(path)


def main() -> int:
    if not SOURCE_IMAGE.is_file():
        raise FileNotFoundError(SOURCE_IMAGE)
    source = read_gray(SOURCE_IMAGE)
    y1 = CROP_Y + CROP_HEIGHT
    x1 = CROP_X + CROP_WIDTH
    if y1 > source.shape[0] or x1 > source.shape[1]:
        raise ValueError(f"裁切範圍超出來源影像：source={source.shape}, crop={(CROP_X, CROP_Y, x1, y1)}")
    crop = source[CROP_Y:y1, CROP_X:x1].copy()
    if crop.shape != (CROP_HEIGHT, CROP_WIDTH):
        raise RuntimeError(f"九宮格裁切尺寸錯誤：{crop.shape}")
    write_bmp(OUTPUT_IMAGE, crop)
    metadata = {
        "role": "observation_only_no_loss_no_selection_no_training_control",
        "source_image": str(SOURCE_IMAGE),
        "source_sha256": sha256(SOURCE_IMAGE),
        "output_image": str(OUTPUT_IMAGE),
        "output_sha256": sha256(OUTPUT_IMAGE),
        "source_shape_hw": list(source.shape),
        "crop_xywh": [CROP_X, CROP_Y, CROP_WIDTH, CROP_HEIGHT],
        "crop_shape_hw": list(crop.shape),
        "pillar_ids": PILLAR_IDS,
        "magnification": "50x",
        "capture_date": "2026-06-18",
        "pixel_scale_nm_per_px": 69.0,
        "selection_basis": "Formal thesis center-nine SEM mapping J8:L10",
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
