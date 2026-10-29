"""Extract anonymous aggregate optical statistics for R90.

The output contains only aggregate distributions and a radial spectrum.  It
never stores image pixels, crop coordinates, contours, phases or sample
spacing, so the photographed structures cannot be reconstructed from it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "config" / "optical_statistics.json"
IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def read_gray(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Unable to decode {path}")
    return image


def percentile_summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        raise RuntimeError("Cannot summarize an empty statistic")
    return {
        "p05": float(np.percentile(array, 5)),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "p50": float(np.percentile(array, 50)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "p95": float(np.percentile(array, 95)),
    }


def radial_power(patch: np.ndarray, bins: int = 32) -> np.ndarray:
    patch = patch.astype(np.float32)
    patch = patch - cv2.GaussianBlur(patch, (0, 0), 12.0, borderType=cv2.BORDER_REFLECT_101)
    window_y = np.hanning(patch.shape[0]).astype(np.float32)
    window_x = np.hanning(patch.shape[1]).astype(np.float32)
    spectrum = np.abs(np.fft.rfft2(patch * window_y[:, None] * window_x[None, :])) ** 2
    fy = np.fft.fftfreq(patch.shape[0])[:, None]
    fx = np.fft.rfftfreq(patch.shape[1])[None, :]
    radius = np.sqrt(fx * fx + fy * fy)
    edges = np.linspace(0.0, 0.5, bins + 1)
    output = np.zeros(bins, np.float64)
    for index in range(bins):
        selected = (radius >= edges[index]) & (radius < edges[index + 1])
        if selected.any():
            output[index] = float(np.mean(spectrum[selected]))
    output = np.log1p(output)
    output -= output.min()
    maximum = float(output.max())
    return output / maximum if maximum > 0 else output


def candidate_patches(image: np.ndarray, size: int) -> list[np.ndarray]:
    h, w = image.shape
    ys = np.linspace(0, max(0, h - size), 7, dtype=np.int32)
    xs = np.linspace(0, max(0, w - size), 9, dtype=np.int32)
    patches = [image[int(y):int(y) + size, int(x):int(x) + size] for y in ys for x in xs]
    scored: list[tuple[float, np.ndarray]] = []
    for patch in patches:
        gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3)
        edge = float(np.mean(np.sqrt(gx * gx + gy * gy)))
        saturation = float(np.mean((patch <= 2) | (patch >= 253)))
        scored.append((edge + 200.0 * saturation, patch))
    scored.sort(key=lambda row: row[0])
    return [patch for _score, patch in scored]


def analyse_set(root: Path, maximum_frames: int, patch_size: int, patches_per_frame: int) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        raise FileNotFoundError(f"No microscope images found in {root}")
    if len(files) > maximum_frames:
        chosen = np.linspace(0, len(files) - 1, maximum_frames, dtype=np.int32)
        files = [files[int(index)] for index in chosen]

    inventory = hashlib.sha256()
    noise: list[float] = []
    illumination: list[float] = []
    row_pattern: list[float] = []
    column_pattern: list[float] = []
    patch_means: list[float] = []
    spectra: list[np.ndarray] = []

    for frame_index, path in enumerate(files, start=1):
        stat = path.stat()
        inventory.update(str(path.relative_to(root)).encode("utf-8"))
        inventory.update(str(stat.st_size).encode("ascii"))
        image = read_gray(path)
        reduced = cv2.resize(image, (image.shape[1] // 4, image.shape[0] // 4), interpolation=cv2.INTER_AREA)
        low = cv2.GaussianBlur(reduced.astype(np.float32) / 255.0, (0, 0), 12.0, borderType=cv2.BORDER_REFLECT_101)
        illumination.append(float(np.std(low)))
        selected = candidate_patches(image, patch_size)[:patches_per_frame]
        for patch in selected:
            normalized = patch.astype(np.float32) / 255.0
            smooth = cv2.GaussianBlur(normalized, (0, 0), 2.0, borderType=cv2.BORDER_REFLECT_101)
            residual = normalized - smooth
            median = float(np.median(residual))
            robust_sigma = float(np.median(np.abs(residual - median)) / 0.67448975)
            noise.append(robust_sigma)
            row_pattern.append(float(np.std(np.mean(residual, axis=1))))
            column_pattern.append(float(np.std(np.mean(residual, axis=0))))
            patch_means.append(float(np.mean(normalized)))
            spectra.append(radial_power(normalized))
        if frame_index == 1 or frame_index % 20 == 0 or frame_index == len(files):
            print(json.dumps({"set": root.name, "completed_frames": frame_index, "total_frames": len(files)}), flush=True)

    spectrum = np.median(np.stack(spectra), axis=0)
    frequencies = (np.arange(len(spectrum), dtype=np.float64) + 0.5) / (2.0 * len(spectrum))
    weights = spectrum + 1e-6
    mean_frequency = float(np.sum(frequencies * weights) / np.sum(weights))
    correlation_scale = float(np.clip(1.0 / max(2.0 * np.pi * mean_frequency, 1e-6), 0.75, 12.0))
    return {
        "source_label": root.name,
        "frame_count": len(files),
        "aggregate_patch_count": len(noise),
        "source_inventory_sha256": inventory.hexdigest(),
        "noise_sigma_normalized": percentile_summary(noise),
        "illumination_std_normalized": percentile_summary(illumination),
        "row_pattern_sigma_normalized": percentile_summary(row_pattern),
        "column_pattern_sigma_normalized": percentile_summary(column_pattern),
        "flat_patch_mean_normalized": percentile_summary(patch_means),
        "radial_spectrum_frequency_cycles_per_pixel": [round(float(value), 6) for value in frequencies],
        "radial_spectrum_normalized": [round(float(value), 6) for value in spectrum],
        "estimated_texture_correlation_px": correlation_scale,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if OUTPUT.exists() and not args.force:
        print(json.dumps({"status": "existing", "output": str(OUTPUT)}, ensure_ascii=False))
        return 0
    config = DESIGN["optical_statistics"]
    sets = [
        analyse_set(
            Path(PROJECT_ROOT / path),
            int(config["maximum_frames_per_set"]),
            int(config["flat_patch_size"]),
            int(config["flat_patches_per_frame"]),
        )
        for path in config["source_sets"]
    ]
    scalar_fields = (
        "noise_sigma_normalized",
        "illumination_std_normalized",
        "row_pattern_sigma_normalized",
        "column_pattern_sigma_normalized",
        "flat_patch_mean_normalized",
    )
    aggregate: dict[str, Any] = {}
    for field in scalar_fields:
        aggregate[field] = {
            key: float(np.median([row[field][key] for row in sets]))
            for key in ("p05", "p10", "p25", "p50", "p75", "p90", "p95")
        }
    aggregate["radial_spectrum_normalized"] = [
        round(float(value), 6)
        for value in np.median(np.asarray([row["radial_spectrum_normalized"] for row in sets]), axis=0)
    ]
    aggregate["estimated_texture_correlation_px"] = float(
        np.median([row["estimated_texture_correlation_px"] for row in sets])
    )
    payload = {
        "schema_version": 1,
        "experiment_id": DESIGN["experiment_id"],
        "generated_at": datetime.now().isoformat(),
        "privacy_contract": {
            "image_pixels_stored": False,
            "crop_coordinates_stored": False,
            "contours_or_sample_structure_stored": False,
            "phase_or_position_stored": False,
            "only_aggregate_statistics": True
        },
        "sets": sets,
        "aggregate": aggregate,
    }
    json_dump(OUTPUT, payload)
    print(json.dumps({"status": "complete", "output": str(OUTPUT), "sets": len(sets), "frames": sum(row["frame_count"] for row in sets)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
