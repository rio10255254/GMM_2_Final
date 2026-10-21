from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA_ROOT = Path(CONFIG["dataset"]["root"])


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(f"Cannot encode {path}")
    encoded.tofile(path)


def rotate_mask(mask: np.ndarray, angle_deg: float) -> np.ndarray:
    h, w = mask.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)


def assert_single_component(mask: np.ndarray, family: str) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    count, _, _, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        raise RuntimeError("Generated mask is empty")
    if count != 2:
        raise RuntimeError(f"{family}: expected one connected object, found {count - 1}")
    return binary


def fill_holes(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    flood = binary.copy()
    flood_mask = np.zeros((binary.shape[0] + 2, binary.shape[1] + 2), np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 1)
    holes = 1 - flood
    return np.maximum(binary, holes).astype(np.uint8)


def radial_polygon(
    size: int,
    rng: np.random.Generator,
    *,
    base_a: float,
    base_b: float,
    harmonics: list[tuple[int, float]],
    samples: int = 1440,
) -> np.ndarray:
    theta = np.linspace(0, 2 * np.pi, samples, endpoint=False)
    radial = np.ones_like(theta)
    for harmonic, amplitude in harmonics:
        radial += amplitude * np.cos(harmonic * theta + rng.uniform(0, 2 * np.pi))
    radial = np.clip(radial, 0.58, 1.35)
    x = base_a * radial * np.cos(theta)
    y = base_b * radial * np.sin(theta)
    angle = rng.uniform(-np.pi, np.pi)
    xr = x * np.cos(angle) - y * np.sin(angle)
    yr = x * np.sin(angle) + y * np.cos(angle)
    cx = size / 2 + rng.uniform(-14, 14)
    cy = size / 2 + rng.uniform(-14, 14)
    points = np.stack([cx + xr, cy + yr], axis=1).round().astype(np.int32)
    mask = np.zeros((size, size), np.uint8)
    cv2.fillPoly(mask, [points], 1)
    return mask


def generate_mask(family: str, size: int, rng: np.random.Generator) -> np.ndarray:
    if family == "fourier_lobed":
        mask = radial_polygon(
            size,
            rng,
            base_a=rng.uniform(150, 174),
            base_b=rng.uniform(118, 148),
            harmonics=[(3, rng.uniform(0.08, 0.15)), (5, rng.uniform(0.035, 0.08))],
        )
    elif family == "rough_boundaries":
        mask = radial_polygon(
            size,
            rng,
            base_a=rng.uniform(150, 172),
            base_b=rng.uniform(120, 148),
            harmonics=[
                (2, rng.uniform(0.02, 0.05)),
                (7, rng.uniform(0.025, 0.055)),
                (11, rng.uniform(0.018, 0.045)),
                (17, rng.uniform(0.010, 0.025)),
            ],
        )
    elif family == "deep_notches":
        mask = radial_polygon(
            size,
            rng,
            base_a=rng.uniform(158, 180),
            base_b=rng.uniform(126, 150),
            harmonics=[(3, rng.uniform(0.02, 0.06))],
        )
        notch_count = int(rng.integers(1, 4))
        for _ in range(notch_count):
            angle = rng.uniform(0, 2 * np.pi)
            cx = size / 2 + rng.uniform(145, 174) * np.cos(angle)
            cy = size / 2 + rng.uniform(115, 146) * np.sin(angle)
            axes = (int(rng.uniform(26, 48)), int(rng.uniform(20, 42)))
            cv2.ellipse(mask, (int(cx), int(cy)), axes, math.degrees(angle), 0, 360, 0, -1)
    elif family == "thin_necks":
        mask = np.zeros((size, size), np.uint8)
        separation = int(rng.uniform(145, 185))
        left = (size // 2 - separation // 2, size // 2 + int(rng.uniform(-16, 17)))
        right = (size // 2 + separation // 2, size // 2 + int(rng.uniform(-16, 17)))
        axes_left = (int(rng.uniform(78, 100)), int(rng.uniform(92, 122)))
        axes_right = (int(rng.uniform(78, 100)), int(rng.uniform(92, 122)))
        cv2.ellipse(mask, left, axes_left, 0, 0, 360, 1, -1)
        cv2.ellipse(mask, right, axes_right, 0, 0, 360, 1, -1)
        neck_half = int(rng.uniform(10, 22))
        cv2.rectangle(mask, (left[0], size // 2 - neck_half), (right[0], size // 2 + neck_half), 1, -1)
        mask = rotate_mask(mask, rng.uniform(-32, 32))
    elif family == "crescent_bodies":
        mask = np.zeros((size, size), np.uint8)
        outer_axes = (int(rng.uniform(168, 188)), int(rng.uniform(132, 158)))
        center = (size // 2 + int(rng.uniform(-10, 11)), size // 2 + int(rng.uniform(-10, 11)))
        cv2.ellipse(mask, center, outer_axes, 0, 0, 360, 1, -1)
        cut_axes = (int(outer_axes[0] * rng.uniform(0.68, 0.82)), int(outer_axes[1] * rng.uniform(0.66, 0.82)))
        offset = int(rng.uniform(62, 92))
        cut_center = (center[0] + offset, center[1] + int(rng.uniform(-18, 19)))
        cv2.ellipse(mask, cut_center, cut_axes, 0, 0, 360, 0, -1)
        mask = rotate_mask(mask, rng.uniform(-180, 180))
    else:
        raise KeyError(family)

    mask = fill_holes(assert_single_component(mask, family))
    mask = assert_single_component(mask, family)
    area_fraction = float(mask.mean())
    if not 0.10 <= area_fraction <= 0.58:
        raise RuntimeError(f"{family}: implausible area fraction {area_fraction:.4f}")
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if len(contours) != 1:
        raise RuntimeError(f"{family}: expected one outer contour, found {len(contours)}")
    return mask


def motion_kernel(length: int, angle_deg: float) -> np.ndarray:
    length = max(1, int(length) | 1)
    kernel = np.zeros((length, length), np.float32)
    kernel[length // 2, :] = 1.0
    matrix = cv2.getRotationMatrix2D((length / 2 - 0.5, length / 2 - 0.5), angle_deg, 1.0)
    kernel = cv2.warpAffine(kernel, matrix, (length, length), flags=cv2.INTER_LINEAR)
    total = float(kernel.sum())
    return kernel / total if total > 0 else kernel


def render_pair(mask: np.ndarray, rng: np.random.Generator, family: str, polarity: str) -> tuple[np.ndarray, np.ndarray, dict]:
    size = mask.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xn = (xx - size / 2) / (size / 2)
    yn = (yy - size / 2) / (size / 2)
    if polarity == "bright":
        background = rng.uniform(38, 92)
        contrast = rng.uniform(62, 118)
    else:
        background = rng.uniform(158, 218)
        contrast = -rng.uniform(62, 118)
    gradient = rng.uniform(-11, 11) * xn + rng.uniform(-11, 11) * yn
    low_field = rng.normal(0, 1, (size, size)).astype(np.float32)
    low_field = cv2.GaussianBlur(low_field, (0, 0), rng.uniform(22, 42))
    low_field /= max(float(low_field.std()), 1e-6)
    truth = background + gradient + rng.uniform(1.0, 3.5) * low_field + contrast * mask.astype(np.float32)

    fine = rng.normal(0, rng.uniform(0.6, 1.5), (size, size)).astype(np.float32)
    truth += fine
    spot_count = int(rng.integers(6, 15))
    spot_field = np.zeros_like(truth, dtype=np.float32)
    for _ in range(spot_count):
        center = (int(rng.integers(45, size - 45)), int(rng.integers(45, size - 45)))
        radius = int(rng.integers(2, 8))
        delta = float(rng.choice([-1, 1]) * rng.uniform(5, 16))
        cv2.circle(spot_field, center, radius, delta, -1)
    truth += cv2.GaussianBlur(spot_field, (0, 0), 0.8)

    blur_sigma = float(rng.uniform(1.35, 2.85))
    raw = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
    motion_length = int(rng.choice([1, 3, 5, 7, 9]))
    motion_angle = float(rng.uniform(-180, 180))
    if motion_length > 1:
        raw = cv2.filter2D(raw, -1, motion_kernel(motion_length, motion_angle), borderType=cv2.BORDER_REFLECT)
    contrast_scale = float(rng.uniform(0.52, 0.82))
    raw_mean = float(raw.mean())
    raw = raw_mean + contrast_scale * (raw - raw_mean)
    raw += rng.uniform(-8, 8) * xn + rng.uniform(-8, 8) * yn
    noise_sigma = float(rng.uniform(2.0, 6.0))
    raw += rng.normal(0, noise_sigma, raw.shape).astype(np.float32)
    if family in {"thin_necks", "rough_boundaries"}:
        raw = cv2.GaussianBlur(raw, (0, 0), rng.uniform(0.25, 0.7))

    truth_u8 = np.clip(np.rint(truth), 0, 255).astype(np.uint8)
    raw_u8 = np.clip(np.rint(raw), 0, 255).astype(np.uint8)
    metadata = {
        "polarity": polarity,
        "background_level": float(background),
        "contrast_signed": float(contrast),
        "contrast_abs": float(abs(contrast)),
        "blur_sigma_px": blur_sigma,
        "motion_length_px": motion_length,
        "motion_angle_deg": motion_angle,
        "noise_sigma": noise_sigma,
        "contrast_scale": contrast_scale,
    }
    return truth_u8, raw_u8, metadata


def generate(force: bool) -> dict:
    manifest_path = DATA_ROOT / "manifest.json"
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("total_images", -1)) == int(CONFIG["dataset"]["total_images"]):
            print(f"Reusing frozen dataset: {manifest_path}")
            return manifest

    master_seed = int(CONFIG["dataset"]["generator_seed"])
    per_family = int(CONFIG["dataset"]["images_per_family"])
    size = int(CONFIG["dataset"]["image_size"])
    records: list[dict] = []
    for family_index, family_cfg in enumerate(CONFIG["dataset"]["families"]):
        family = family_cfg["name"]
        stage = family_cfg["stage"]
        for image_index in range(per_family):
            seed = master_seed + family_index * 1000 + image_index
            generation_attempt = 0
            while True:
                rng = np.random.default_rng(seed + generation_attempt * 100_000)
                try:
                    mask = generate_mask(family, size, rng)
                    break
                except RuntimeError:
                    generation_attempt += 1
                    if generation_attempt >= 100:
                        raise
            polarity = "bright" if image_index % 2 == 0 else "dark"
            truth, raw, rendering = render_pair(mask, rng, family, polarity)
            filename = f"{image_index:04d}.bmp"
            truth_path = DATA_ROOT / "lbl" / stage / filename
            raw_path = DATA_ROOT / "src" / stage / filename
            mask_path = DATA_ROOT / "mask" / stage / filename
            write_bmp(truth_path, truth)
            write_bmp(raw_path, raw)
            write_bmp(mask_path, mask * 255)
            ys, xs = np.nonzero(mask)
            records.append({
                "image_id": f"{family}/{image_index:04d}",
                "family": family,
                "family_label_tw": family_cfg["label_tw"],
                "stage": stage,
                "filename": filename,
                "seed": seed,
                "generation_attempt": generation_attempt,
                "src": str(raw_path),
                "lbl": str(truth_path),
                "mask": str(mask_path),
                "area_fraction": float(mask.mean()),
                "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                **rendering,
            })
        print(f"Generated {family}: {per_family} images")

    manifest = {
        "profile": "r73_synthetic_acm_val",
        "generator_version": CONFIG["dataset"]["generator_version"],
        "generator_seed": master_seed,
        "created_date": CONFIG["created_date"],
        "created_after_checkpoint": True,
        "image_size": [size, size],
        "images_per_family": per_family,
        "total_images": len(records),
        "families": CONFIG["dataset"]["families"],
        "mask_semantics": CONFIG["dataset"]["mask_semantics"],
        "records": records,
    }
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "records"}, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the frozen R73 closed-contour microscopy test set")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
