"""Audit whether the locked R92/R100 labels actually supervise recoverable edge sharpening."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(r"D:\GMM_2_Final\Experiments\R92_PhysicalTransitionBalancedScratch\data\r92_formal")
OUTPUT = ROOT / "results" / "boundary_supervision"
CROP = 320
BORDER = 24


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def boundary_crop(mask: np.ndarray) -> tuple[int, int, int, int]:
    binary = (mask >= 128).astype(np.uint8)
    boundary = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(boundary)
    if len(ys) == 0:
        cy, cx = mask.shape[0] // 2, mask.shape[1] // 2
    else:
        center_y, center_x = (mask.shape[0] - 1) / 2.0, (mask.shape[1] - 1) / 2.0
        index = int(np.argmin((ys - center_y) ** 2 + (xs - center_x) ** 2))
        cy, cx = int(ys[index]), int(xs[index])
    y0 = min(max(cy - CROP // 2, 0), mask.shape[0] - CROP)
    x0 = min(max(cx - CROP // 2, 0), mask.shape[1] - CROP)
    return y0, x0, y0 + CROP, x0 + CROP


def normalize_by_regions(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    binary = mask >= 0.5
    foreground = image[binary]
    background = image[~binary]
    if foreground.size < 64 or background.size < 64:
        return image
    fg = float(np.median(foreground))
    bg = float(np.median(background))
    denominator = fg - bg
    if abs(denominator) < 0.08:
        return image
    return np.clip((image - bg) / denominator, -0.5, 1.5)


def masks_from_binary(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    binary = (mask >= 0.5).astype(np.uint8)
    inside = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 5)
    signed = inside - outside
    valid = np.zeros_like(binary, dtype=bool)
    valid[BORDER:-BORDER, BORDER:-BORDER] = True
    boundary = (np.abs(signed) <= 5.0) & valid
    material = (np.abs(signed) >= 12.0) & valid
    return boundary, material


def band_metrics(source: np.ndarray, target: np.ndarray, support: np.ndarray, sigma: float) -> dict[str, float]:
    source_band = source - cv2.GaussianBlur(source, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    target_band = target - cv2.GaussianBlur(target, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    x = source_band[support].astype(np.float64)
    y = target_band[support].astype(np.float64)
    if x.size < 64:
        return {"correlation": 0.0, "optimal_scale": 0.0, "source_rms": 0.0, "target_rms": 0.0}
    source_rms = float(np.sqrt(np.mean(x * x)))
    target_rms = float(np.sqrt(np.mean(y * y)))
    optimal_scale = float(np.dot(x, y) / max(np.dot(x, x), 1e-12))
    correlation = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 1e-8 and np.std(y) > 1e-8 else 0.0
    return {
        "correlation": correlation,
        "optimal_scale": optimal_scale,
        "source_rms": source_rms,
        "target_rms": target_rms,
    }


def summarize(values: pd.DataFrame, prefix: str) -> dict[str, float]:
    corr = values[f"{prefix}_correlation"].to_numpy(float)
    scale = values[f"{prefix}_optimal_scale"].to_numpy(float)
    coherent = corr >= 0.50
    return {
        "count": int(len(values)),
        "correlation_median": float(np.median(corr)),
        "optimal_scale_median": float(np.median(scale)),
        "coherent_fraction": float(np.mean(coherent)),
        "recoverable_sharpen_fraction": float(np.mean(coherent & (scale > 1.05))),
        "recoverable_denoise_fraction": float(np.mean(coherent & (scale < 0.95))),
        "ambiguous_fraction": float(np.mean(~coherent)),
    }


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    records = [row for row in manifest["records"] if row["split"] == "internal_test"]
    rows: list[dict[str, object]] = []
    for record in records:
        mask_full = np.load(PACKAGE / record["mask"], mmap_mode="r")
        y0, x0, y1, x1 = boundary_crop(mask_full)
        mask = np.asarray(mask_full[y0:y1, x0:x1], dtype=np.float32) / 255.0
        target_u8 = np.load(PACKAGE / record["target"], mmap_mode="r")[y0:y1, x0:x1]
        target = np.asarray(target_u8, dtype=np.float32) / 255.0
        target = normalize_by_regions(target, mask)
        boundary, material = masks_from_binary(mask)
        for observation in record["observations"]:
            source_u8 = np.load(PACKAGE / observation["source"], mmap_mode="r")[y0:y1, x0:x1]
            source = normalize_by_regions(np.asarray(source_u8, dtype=np.float32) / 255.0, mask)
            row: dict[str, object] = {
                "scene_index": int(record["scene_index"]),
                "role": record["role"],
                "observation": int(observation["observation"]),
                "degradation_family": observation["degradation_family"],
            }
            for region_name, support in (("boundary", boundary), ("material", material)):
                for sigma in (1.0, 2.0):
                    metrics = band_metrics(source, target, support, sigma)
                    for name, value in metrics.items():
                        row[f"{region_name}_s{sigma:g}_{name}"] = value
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "per_view.csv", index=False)
    summary = {
        "status": "complete",
        "split": "internal_test",
        "scenes": int(len(records)),
        "views": int(len(table)),
        "definitions": {
            "recoverable_sharpen": "band correlation >= 0.50 and least-squares target/source scale > 1.05",
            "recoverable_denoise": "band correlation >= 0.50 and least-squares target/source scale < 0.95",
            "boundary_support": "within five pixels of exact procedural boundary",
            "material_support": "at least twelve pixels from exact procedural boundary",
        },
        "overall": {},
        "by_role": {},
        "by_degradation": {},
    }
    prefixes = [f"{region}_s{sigma:g}" for region in ("boundary", "material") for sigma in (1.0, 2.0)]
    summary["overall"] = {prefix: summarize(table, prefix) for prefix in prefixes}
    for role, group in table.groupby("role"):
        summary["by_role"][str(role)] = {prefix: summarize(group, prefix) for prefix in prefixes}
    for family, group in table.groupby("degradation_family"):
        summary["by_degradation"][str(family)] = {prefix: summarize(group, prefix) for prefix in prefixes}
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
