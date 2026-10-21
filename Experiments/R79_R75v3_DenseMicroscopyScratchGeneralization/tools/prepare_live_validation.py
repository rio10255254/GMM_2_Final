"""Prepare three fixed real-optical crops for observation-only live validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = EXPERIMENT_DIR / "data" / "live_validation"
R78_LOCKED_RAW = Path(
    r"D:\GMM_2_Final\Experiments\R78_R75v2_BroadRealMicroscopeGeneralization"
) / "inputs" / "locked_raw"

# The crops are fixed before training. They are never copied into src/lbl/geom,
# never receive labels, and never affect loss, checkpoint selection, or stopping.
CROPS = (
    {
        "name": "5x_dense",
        "source": R78_LOCKED_RAW / "5x_0p5um" / "frame_0000.bmp",
        "output": OUTPUT_DIR / "5x_dense_raw.bmp",
        "crop_xywh": [1280, 160, 512, 512],
        "selection_basis": "dense low-magnification square field",
    },
    {
        "name": "20x_mixed",
        "source": R78_LOCKED_RAW / "20x_0p5um" / "frame_0000.bmp",
        "output": OUTPUT_DIR / "20x_mixed_raw.bmp",
        "crop_xywh": [176, 496, 512, 512],
        "selection_basis": "fixed junction of coarse squares, dense dots, and lines",
    },
    {
        "name": "50x_array",
        "source": R78_LOCKED_RAW / "50x_0p5um" / "frame_0000.bmp",
        "output": OUTPUT_DIR / "50x_array_raw.bmp",
        "crop_xywh": [1088, 112, 512, 512],
        "selection_basis": "single-polarity circular array with real optical blur",
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"Cannot read live-validation source: {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(f"Cannot write live-validation image: {path}")
    encoded.tofile(path)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    for spec in CROPS:
        source_path = Path(spec["source"])
        output_path = Path(spec["output"])
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        source = read_gray(source_path)
        x, y, width, height = (int(value) for value in spec["crop_xywh"])
        x1, y1 = x + width, y + height
        if x < 0 or y < 0 or x1 > source.shape[1] or y1 > source.shape[0]:
            raise ValueError(
                f"Crop exceeds source for {spec['name']}: source={source.shape}, "
                f"crop={(x, y, width, height)}"
            )
        crop = source[y:y1, x:x1].copy()
        if crop.shape != (512, 512):
            raise RuntimeError(f"Unexpected crop shape for {spec['name']}: {crop.shape}")
        write_bmp(output_path, crop)
        records.append(
            {
                "name": spec["name"],
                "role": "observation_only_no_loss_no_selection_no_training_control",
                "source_image": str(source_path),
                "source_sha256": sha256(source_path),
                "source_shape_hw": list(source.shape),
                "crop_xywh": [x, y, width, height],
                "crop_shape_hw": list(crop.shape),
                "output_image": str(output_path),
                "output_sha256": sha256(output_path),
                "selection_basis": spec["selection_basis"],
            }
        )
    metadata = {
        "experiment_id": "R79_R75v3_DenseMicroscopyScratchGeneralization",
        "role": "observation_only_no_loss_no_selection_no_training_control",
        "locked_before_training": True,
        "training_pixels_used": False,
        "labels_available": False,
        "checkpoint_selection_allowed": False,
        "early_stopping_allowed": False,
        "records": records,
    }
    metadata_path = OUTPUT_DIR / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
