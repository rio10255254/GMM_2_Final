from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA = Path(PROJECT_ROOT / CONFIG["dataset"]["root"])
R73_GENERATOR = Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/scripts/generate_dataset.py'))
spec = importlib.util.spec_from_file_location("r73_shape_generator", R73_GENERATOR)
r73 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(r73)


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise OSError(path)
    encoded.tofile(path)


def low_frequency_field(size: int, rng: np.random.Generator, amplitude: float) -> np.ndarray:
    coarse = rng.normal(0, 1, (9, 9)).astype(np.float32)
    field = cv2.resize(coarse, (size, size), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), 22)
    field -= float(field.mean())
    scale = float(field.std())
    return field * (amplitude / scale) if scale > 1e-6 else field


def illumination_field(size: int, rng: np.random.Generator, amplitude: float) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    angle = float(rng.uniform(-np.pi, np.pi))
    gradient = np.cos(angle) * (xx - size / 2) / (size / 2) + np.sin(angle) * (yy - size / 2) / (size / 2)
    cx, cy = rng.uniform(0.05, 0.95, 2) * size
    sigma = rng.uniform(0.20, 0.42) * size
    spot = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))
    spot -= float(spot.mean())
    return amplitude * (0.55 * gradient + float(rng.choice([-1, 1])) * 0.9 * spot)


def angular_fade(mask: np.ndarray, rng: np.random.Generator, strength: float) -> np.ndarray:
    size = mask.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    ys, xs = np.nonzero(mask)
    cx, cy = float(xs.mean()), float(ys.mean())
    angle = np.arctan2(yy - cy, xx - cx)
    center = float(rng.uniform(-np.pi, np.pi))
    width = float(rng.uniform(0.28, 0.65))
    distance = np.abs(np.angle(np.exp(1j * (angle - center))))
    wedge = np.exp(-(distance**2) / (2 * width**2))
    return 1.0 - strength * wedge


def clean_truth(mask: np.ndarray, rng: np.random.Generator, polarity: str) -> np.ndarray:
    size = mask.shape[0]
    background = float(rng.uniform(55, 155))
    contrast = float(rng.uniform(72, 108)) * (1 if polarity == "bright" else -1)
    field = low_frequency_field(size, rng, rng.uniform(1.5, 4.0))
    image = background + field + mask.astype(np.float32) * contrast
    image += rng.normal(0, rng.uniform(0.6, 1.8), image.shape)
    return np.clip(image, 0, 255).astype(np.uint8)


def render_hard(mask: np.ndarray, rng: np.random.Generator, challenge: str, polarity: str) -> tuple[np.ndarray, dict]:
    size = mask.shape[0]
    sign = 1.0 if polarity == "bright" else -1.0
    background = float(rng.uniform(82, 168))
    contrast_ranges = {
        "low_contrast": (16, 30),
        "uneven_illumination": (32, 55),
        "asymmetric_blur_halo": (35, 60),
        "boundary_fade": (32, 56),
        "mixed_hard": (35, 55),
    }
    contrast = float(rng.uniform(*contrast_ranges[challenge]))
    blur_ranges = {
        "low_contrast": (3.0, 5.0),
        "uneven_illumination": (2.5, 4.5),
        "asymmetric_blur_halo": (4.0, 7.5),
        "boundary_fade": (2.5, 4.5),
        "mixed_hard": (2.8, 4.8),
    }
    noise_ranges = {
        "low_contrast": (5.0, 9.0),
        "uneven_illumination": (4.0, 7.0),
        "asymmetric_blur_halo": (4.0, 7.0),
        "boundary_fade": (4.0, 8.0),
        "mixed_hard": (4.0, 8.0),
    }
    blur_sigma = float(rng.uniform(*blur_ranges[challenge]))
    noise_sigma = float(rng.uniform(*noise_ranges[challenge]))
    texture_amplitude = float(rng.uniform(3, 8 if challenge != "mixed_hard" else 7))
    illumination_amplitude = 0.0
    fade_strength = 0.0
    halo_strength = 0.0
    motion_length = 1

    fade = np.ones_like(mask, dtype=np.float32)
    if challenge in ("low_contrast", "boundary_fade", "mixed_hard"):
        if challenge == "low_contrast":
            fade_strength = float(rng.uniform(0.20, 0.45))
        elif challenge == "boundary_fade":
            fade_strength = float(rng.uniform(0.55, 0.85))
        else:
            fade_strength = float(rng.uniform(0.35, 0.68))
        fade *= angular_fade(mask, rng, fade_strength)
        if challenge == "mixed_hard":
            fade *= angular_fade(mask, rng, float(rng.uniform(0.20, 0.45)))

    image = background + low_frequency_field(size, rng, texture_amplitude)
    if challenge in ("uneven_illumination", "mixed_hard"):
        illumination_amplitude = float(rng.uniform(20, 42)) if challenge == "uneven_illumination" else float(rng.uniform(8, 20))
        image += illumination_field(size, rng, illumination_amplitude)
    image += mask.astype(np.float32) * sign * contrast * fade
    image = cv2.GaussianBlur(image.astype(np.float32), (0, 0), blur_sigma)

    if challenge in ("asymmetric_blur_halo", "mixed_hard"):
        motion_length = int(rng.choice([11, 15, 19, 23, 25])) if challenge == "asymmetric_blur_halo" else int(rng.choice([5, 7, 9, 11, 13]))
        motion_angle = float(rng.uniform(-180, 180))
        image = cv2.filter2D(image, -1, r73.motion_kernel(motion_length, motion_angle), borderType=cv2.BORDER_REFLECT)
        halo_strength = float(rng.uniform(0.40, 0.80)) if challenge == "asymmetric_blur_halo" else float(rng.uniform(0.20, 0.55))
        broad = cv2.GaussianBlur(image, (0, 0), rng.uniform(3.5, 6.5))
        image = image + halo_strength * (broad - image)

    if challenge in ("boundary_fade", "mixed_hard"):
        boundary = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((9, 9), np.uint8)) > 0
        ys, xs = np.nonzero(boundary)
        count = int(rng.integers(6, 14)) if challenge == "boundary_fade" else int(rng.integers(3, 8))
        for _ in range(count):
            pick = int(rng.integers(0, len(xs)))
            radius = int(rng.integers(4, 12)) if challenge == "boundary_fade" else int(rng.integers(3, 8))
            delta = float(rng.uniform(-12, 12)) if challenge == "boundary_fade" else float(rng.uniform(-9, 9))
            cv2.circle(image, (int(xs[pick]), int(ys[pick])), radius, background + delta, -1)

    image += rng.normal(0, noise_sigma, image.shape).astype(np.float32)
    image = np.clip(image, 0, 255).astype(np.uint8)
    metadata = {
        "polarity": polarity,
        "background_level": background,
        "contrast_abs": contrast,
        "blur_sigma_px": blur_sigma,
        "noise_sigma": noise_sigma,
        "texture_amplitude": texture_amplitude,
        "illumination_amplitude": illumination_amplitude,
        "fade_strength": fade_strength,
        "halo_strength": halo_strength,
        "motion_length_px": motion_length,
    }
    return image, metadata


def generate(force: bool) -> dict:
    inference_manifest = ROOT / "results" / "inference_manifest.json"
    if force and inference_manifest.exists():
        raise RuntimeError("R74 R61 outputs already exist; forced regeneration would invalidate the frozen comparison")
    manifest_path = DATA / "manifest.json"
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("total_images", -1)) == int(CONFIG["dataset"]["total_images"]):
            print(f"Reusing frozen dataset: {manifest_path}")
            return manifest
    if force and DATA.exists():
        shutil.rmtree(DATA)

    master_seed = int(CONFIG["dataset"]["generator_seed"])
    per_group = int(CONFIG["dataset"]["images_per_family"])
    size = int(CONFIG["dataset"]["image_size"])
    shape_families = list(CONFIG["dataset"]["shape_families"])
    records = []
    for group_index, group in enumerate(CONFIG["dataset"]["families"]):
        challenge, stage = group["name"], group["stage"]
        for image_index in range(per_group):
            shape_family = shape_families[image_index % len(shape_families)]
            seed = master_seed + group_index * 10_000 + image_index
            attempt = 0
            while True:
                rng = np.random.default_rng(seed + attempt * 1_000_000)
                try:
                    mask = r73.generate_mask(shape_family, size, rng)
                    break
                except RuntimeError:
                    attempt += 1
                    if attempt >= 100:
                        raise
            polarity = "bright" if image_index % 2 == 0 else "dark"
            truth = clean_truth(mask, rng, polarity)
            raw, rendering = render_hard(mask, rng, challenge, polarity)
            filename = f"{image_index:04d}.bmp"
            paths = {
                "src": DATA / "src" / stage / filename,
                "lbl": DATA / "lbl" / stage / filename,
                "mask": DATA / "mask" / stage / filename,
            }
            write_bmp(paths["src"], raw); write_bmp(paths["lbl"], truth); write_bmp(paths["mask"], mask * 255)
            records.append({
                "image_id": f"{challenge}/{image_index:04d}",
                "family": challenge,
                "family_label_tw": group["label_tw"],
                "shape_family": shape_family,
                "stage": stage,
                "filename": filename,
                "seed": seed,
                "generation_attempt": attempt,
                "src": str(paths["src"]), "lbl": str(paths["lbl"]), "mask": str(paths["mask"]),
                "area_fraction": float(mask.mean()),
                **rendering,
            })
        print(f"Generated {challenge}: {per_group} images")
    manifest = {
        "profile": "r74_hard_acm_val",
        "generator_version": CONFIG["dataset"]["generator_version"],
        "generator_seed": master_seed,
        "created_date": CONFIG["created_date"],
        "created_after_checkpoint": True,
        "difficulty_calibration_uses_r61": False,
        "difficulty_status": "candidate_not_yet_frozen",
        "image_size": [size, size],
        "images_per_family": per_group,
        "total_images": len(records),
        "families": CONFIG["dataset"]["families"],
        "shape_families": shape_families,
        "mask_semantics": CONFIG["dataset"]["mask_semantics"],
        "records": records,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "records"}, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the R74 Raw-calibrated hard microscopy candidate set")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
