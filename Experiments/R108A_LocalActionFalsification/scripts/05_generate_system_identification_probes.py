"""Generate controlled single-image probes for frozen-model system identification."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "system_identification_probes"
INPUT = OUT / "input"
INPUT.mkdir(parents=True, exist_ok=True)
SIZE = 512


def save(path: Path, image: np.ndarray) -> str:
    value = np.round(np.clip(image, 0, 255)).astype(np.uint8)
    cv2.imencode(".bmp", value)[1].tofile(str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logistic_edge(center: float, scale: float, background: float, contrast: float, polarity: float = 1.0, illumination: float = 0.0) -> np.ndarray:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    probability = 1.0 / (1.0 + np.exp(-np.clip((xx - center) / scale, -40.0, 40.0)))
    field = illumination * (yy / max(SIZE - 1, 1) - 0.5)
    return background + field + polarity * contrast * probability


def asymmetric_edge(center: float, scale: float, background: float, contrast: float, ghost: float, halo: float) -> np.ndarray:
    base = logistic_edge(center, scale, background, contrast)
    shifted = np.roll(base, 2, axis=1)
    broad = cv2.GaussianBlur(base, (0, 0), 4.0, borderType=cv2.BORDER_REFLECT_101)
    return np.clip((1.0 - ghost) * base + ghost * shifted + halo * (broad - base), 0, 255)


def sinusoid(period: float, amplitude: float, mean: float, angle_deg: float, phase: float) -> np.ndarray:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    angle = math.radians(angle_deg)
    coordinate = xx * math.cos(angle) + yy * math.sin(angle)
    return mean + amplitude * np.sin(2.0 * math.pi * coordinate / period + phase)


def main() -> int:
    rows = []
    index = 0

    def emit(kind: str, image: np.ndarray, **meta) -> None:
        nonlocal index
        filename = f"p{index:04d}_{kind}.bmp"
        path = INPUT / filename
        digest = save(path, image)
        rows.append({"index": index, "filename": filename, "kind": kind, "sha256": digest, **meta})
        index += 1

    for level in (24, 48, 80, 112, 144, 176, 208, 232):
        emit("flat", np.full((SIZE, SIZE), level, np.float32), level=level, noise_sigma=0)
        for noise_sigma in (2.0, 5.0):
            rng = np.random.default_rng(108000 + level * 17 + int(noise_sigma))
            noisy = level + rng.normal(0, noise_sigma, (SIZE, SIZE)).astype(np.float32)
            emit("flat_noise", noisy, level=level, noise_sigma=noise_sigma)

    for background, contrast, polarity in (
        (32.0, 40.0, 1.0), (32.0, 100.0, 1.0), (80.0, 120.0, 1.0),
        (220.0, 40.0, -1.0), (220.0, 100.0, -1.0), (170.0, 120.0, -1.0),
    ):
        for scale in (0.45, 0.75, 1.2, 2.0, 3.2, 5.0):
            for center in (255.0, 255.5):
                image = logistic_edge(center, scale, background, contrast, polarity)
                emit("edge", image, center=center, scale=scale, width_10_90=2*math.log(9)*scale, background=background, contrast=contrast, polarity=polarity, illumination=0.0)

    for illumination in (20.0, 50.0, 90.0):
        for scale in (1.2, 2.5, 4.0):
            image = logistic_edge(255.5, scale, 70.0, 100.0, 1.0, illumination)
            emit("edge_illum", image, center=255.5, scale=scale, width_10_90=2*math.log(9)*scale, background=70.0, contrast=100.0, polarity=1.0, illumination=illumination)

    for ghost in (0.03, 0.08, 0.15):
        for halo in (-0.12, 0.12):
            image = asymmetric_edge(255.5, 1.5, 60.0, 120.0, ghost, halo)
            emit("edge_asym", image, center=255.5, scale=1.5, width_10_90=2*math.log(9)*1.5, background=60.0, contrast=120.0, polarity=1.0, ghost=ghost, halo=halo)

    for period in (4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0):
        for amplitude in (5.0, 15.0, 40.0):
            for angle in (0.0, 45.0, 90.0):
                phase = 0.37
                image = sinusoid(period, amplitude, 128.0, angle, phase)
                emit("sinusoid", image, period=period, amplitude=amplitude, mean=128.0, angle_deg=angle, phase=phase)

    for sigma in (0.0, 0.8, 1.6, 2.8):
        impulse = np.full((SIZE, SIZE), 128.0, np.float32)
        impulse[SIZE//2, SIZE//2] = 208.0
        if sigma > 0:
            impulse = cv2.GaussianBlur(impulse, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
        emit("impulse", impulse, blur_sigma=sigma, level=128.0, impulse_delta=80.0)

    with (OUT / "metadata.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        columns = sorted({key for row in rows for key in row}, key=lambda key: (key not in {"index", "filename", "kind", "sha256"}, key))
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)
    summary = {"status": "complete", "images": len(rows), "size": [SIZE, SIZE], "kind_counts": {kind: sum(row["kind"] == kind for row in rows) for kind in sorted({row["kind"] for row in rows})}, "input": str(INPUT)}
    (OUT / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
