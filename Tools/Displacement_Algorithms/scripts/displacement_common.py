from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.as_posix().lower())
    return [int(part) if part.isdigit() else part for part in parts]


def list_images(input_dir: Path, pattern: str = "*") -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a folder: {input_dir}")

    files = [
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    files.sort(key=natural_key)
    if len(files) < 2:
        raise ValueError(f"Need at least 2 images in {input_dir}; found {len(files)}")
    return files


def parse_crop(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None or value.strip() == "":
        return None
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop must be x,y,width,height")
    x, y, width, height = parts
    if width <= 0 or height <= 0:
        raise ValueError("--crop width and height must be positive")
    return x, y, width, height


def apply_crop(image: np.ndarray, crop: tuple[int, int, int, int] | None) -> np.ndarray:
    if crop is None:
        return image
    x, y, width, height = crop
    if x < 0 or y < 0 or x + width > image.shape[1] or y + height > image.shape[0]:
        raise ValueError(
            f"Crop {crop} is outside image size {image.shape[1]}x{image.shape[0]}"
        )
    return image[y : y + height, x : x + width]


def read_gray_u8(path: Path, crop: tuple[int, int, int, int] | None = None) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return apply_crop(image, crop)


def to_float01(image: np.ndarray) -> np.ndarray:
    arr = image.astype(np.float32)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - lo) / (hi - lo)


def read_gray_float(path: Path, crop: tuple[int, int, int, int] | None = None) -> np.ndarray:
    return to_float01(read_gray_u8(path, crop))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def summarize_steps(rows: list[dict[str, object]]) -> dict[str, float | int | None]:
    good = [row for row in rows if row.get("status") == "ok" and row.get("frame_index") != 0]
    if not good:
        return {
            "valid_step_count": 0,
            "mean_dx_px": None,
            "std_dx_px": None,
            "mean_dy_px": None,
            "std_dy_px": None,
            "rms_step_px": None,
        }
    dx = np.array([float(row["dx_px"]) for row in good], dtype=np.float64)
    dy = np.array([float(row["dy_px"]) for row in good], dtype=np.float64)
    mag = np.sqrt(dx * dx + dy * dy)
    return {
        "valid_step_count": int(len(good)),
        "mean_dx_px": float(np.mean(dx)),
        "std_dx_px": float(np.std(dx, ddof=1)) if len(dx) > 1 else 0.0,
        "mean_dy_px": float(np.mean(dy)),
        "std_dy_px": float(np.std(dy, ddof=1)) if len(dy) > 1 else 0.0,
        "rms_step_px": float(np.sqrt(np.mean(mag * mag))),
    }
