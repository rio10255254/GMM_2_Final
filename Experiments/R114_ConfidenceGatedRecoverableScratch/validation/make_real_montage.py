"""Create a source/output/change montage from completed real representatives."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation" / "manifests" / "real_representatives.json"
IMAGES = ROOT / "results" / "geometry_probe" / "E020" / "real_representatives" / "images"
OUTPUT = ROOT / "results" / "geometry_probe" / "E020" / "real_representatives" / "representative_montage.png"


def read(path: str | Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def tile(image: np.ndarray, side: int = 512) -> np.ndarray:
    height, width = image.shape
    scale = min(side / height, side / width)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((side, side), np.uint8)
    y = (side - resized.shape[0]) // 2
    x = (side - resized.shape[1]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


def main() -> int:
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))["records"]
    selected = []
    for family in ("real_5x", "real_20x", "real_50x", "junhua"):
        selected.append(next(row for row in records if row["family"] == family))
    rows = []
    for record in selected:
        source = read(record["source"])
        output = read(IMAGES / f"{record['id']}_output.png")
        change = np.clip(np.abs(output.astype(np.int16) - source.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
        row = np.concatenate([tile(source), tile(output), tile(change)], axis=1)
        cv2.putText(row, f"{record['family']}  source | output | abs change x8", (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2, cv2.LINE_AA)
        rows.append(row)
    montage = np.concatenate(rows, axis=0)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(OUTPUT), montage):
        raise RuntimeError(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
