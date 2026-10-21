"""Build R75 data from analytic primitives only.

This module deliberately has no importer for legacy training packages, SEM data,
sample crops, or checkpoints.  Every pixel is generated in this file from a
recorded random seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Iterable

import cv2
import numpy as np
import scipy.io


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
DATA_ROOT = ROOT / "data"
REPORT_ROOT = ROOT / "reports"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PROVENANCE_KIND = str(CONFIG["source_isolation"]["required_provenance_kind"])
GENERATOR_NAME = str(CONFIG["source_isolation"]["required_generator"])
FORBIDDEN_VALUE_TOKENS = tuple(
    str(token).lower() for token in CONFIG["source_isolation"]["forbidden_value_tokens"]
)
FORBIDDEN_RECORD_KEYS = {
    str(key).lower() for key in CONFIG["source_isolation"]["forbidden_record_keys"]
}
SHAPE_FAMILIES = tuple(str(name) for name in CONFIG["dataset"]["shape_families"])
DEGRADATION_FAMILIES = (
    "gaussian_blur",
    "anisotropic_blur",
    "short_motion_blur",
    "contrast_illumination",
    "mild_defocus",
    "mild_halo",
    "poisson_gaussian",
    "subpixel_ghost",
)


def _json_dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower() or ".bmp"
    ok, encoded = cv2.imencode(suffix, np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(f"Could not encode image: {path}")
    encoded.tofile(path)


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"Could not read image: {path}")
    return image


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _profile_config(profile: str) -> dict:
    profiles = CONFIG["dataset"]["profiles"]
    if profile not in profiles:
        raise KeyError(f"Unknown R75 profile: {profile}")
    return dict(profiles[profile])


def build_plan(profile: str) -> dict:
    profile_cfg = _profile_config(profile)
    geometry_count = int(profile_cfg["geometry_count_per_family"])
    renderings = int(profile_cfg["renderings_per_geometry"])
    family_count = len(SHAPE_FAMILIES)
    pair_count = family_count * geometry_count * renderings
    if pair_count != int(profile_cfg["expected_pairs"]):
        raise RuntimeError(f"Profile {profile} has inconsistent expected_pairs")
    n_test = max(1, int(round(geometry_count * float(CONFIG["dataset"]["split_ratios"]["internal_test"]))))
    n_val = max(1, int(round(geometry_count * float(CONFIG["dataset"]["split_ratios"]["validation"]))))
    n_train = geometry_count - n_val - n_test
    if n_train < 1:
        raise RuntimeError(f"Profile {profile} needs at least one train geometry per family")
    return {
        "profile": profile,
        "image_size": int(CONFIG["dataset"]["image_size"]),
        "shape_family_count": family_count,
        "shape_families": list(SHAPE_FAMILIES),
        "geometry_count_per_family": geometry_count,
        "renderings_per_geometry": renderings,
        "expected_pairs": pair_count,
        "geometry_split_per_family": {
            "train": n_train,
            "validation": n_val,
            "internal_test": n_test,
        },
        "pair_split_counts": {
            "train": family_count * n_train * renderings,
            "validation": family_count * n_val * renderings,
            "internal_test": family_count * n_test * renderings,
        },
        "estimated_payload_gib": round(
            pair_count * int(CONFIG["dataset"]["image_size"]) ** 2 * 10 / (1024**3),
            2,
        ),
        "generator": GENERATOR_NAME,
        "contains_real_pixels": False,
        "contains_measured_shapes": False,
        "contains_checkpoint_data": False,
    }


def _safe_clean_package(package_dir: Path, output_root: Path) -> None:
    package_resolved = package_dir.resolve()
    output_resolved = output_root.resolve()
    try:
        inside = package_resolved.is_relative_to(output_resolved)
    except AttributeError:
        inside = str(package_resolved).lower().startswith(str(output_resolved).lower() + "\\")
    if not inside or package_resolved == output_resolved:
        raise RuntimeError(f"Refusing to clean outside the selected output root: {package_resolved}")
    if package_dir.exists():
        shutil.rmtree(package_dir)


def _analytic_gaussian_kernel(size: int, sigma_x: float, sigma_y: float, theta_deg: float) -> np.ndarray:
    axis = np.arange(size, dtype=np.float32) - (size - 1) / 2.0
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    theta = math.radians(theta_deg)
    xr = xx * math.cos(theta) + yy * math.sin(theta)
    yr = -xx * math.sin(theta) + yy * math.cos(theta)
    kernel = np.exp(-0.5 * ((xr / sigma_x) ** 2 + (yr / sigma_y) ** 2)).astype(np.float32)
    return kernel / max(float(kernel.sum()), 1e-12)


def ensure_analytic_psf(package_dir: Path) -> tuple[Path, dict]:
    path = package_dir / "analytic_psf_bank.mat"
    params = (
        (0.85, 0.85, 0.0),
        (1.00, 1.25, 0.0),
        (1.25, 1.00, 90.0),
        (1.10, 1.65, 25.0),
        (1.35, 1.35, 0.0),
        (1.10, 1.65, -25.0),
        (1.25, 1.90, 55.0),
        (1.65, 1.20, -55.0),
        (1.90, 1.90, 0.0),
    )
    stack = np.empty((21, 21, 3, 3), dtype=np.float32)
    for index, values in enumerate(params):
        row, col = divmod(index, 3)
        stack[:, :, row, col] = _analytic_gaussian_kernel(21, *values)
    package_dir.mkdir(parents=True, exist_ok=True)
    scipy.io.savemat(
        path,
        {
            "psf_grid": stack,
            "generator": np.asarray([GENERATOR_NAME], dtype=object),
            "source_kind": np.asarray(["analytic_gaussian_only"], dtype=object),
        },
        do_compression=True,
    )
    return path, {
        "relative_path": path.relative_to(package_dir).as_posix(),
        "sha256": _sha256(path),
        "grid_shape": [21, 21, 3, 3],
        "kernel_count": 9,
        "source_kind": "analytic_gaussian_only",
        "measured_data_used": False,
    }


def _rotated_rectangle(mask: np.ndarray, center: tuple[float, float], size: tuple[float, float], angle: float, value: int = 1) -> None:
    points = cv2.boxPoints((center, size, angle)).round().astype(np.int32)
    cv2.fillPoly(mask, [points], int(value))


def _regular_polygon(mask: np.ndarray, center: tuple[float, float], radius: float, sides: int, angle: float) -> None:
    theta = angle + np.arange(sides, dtype=np.float32) * (2.0 * np.pi / sides)
    points = np.stack(
        [center[0] + radius * np.cos(theta), center[1] + radius * np.sin(theta)], axis=1
    ).round().astype(np.int32)
    cv2.fillPoly(mask, [points], 1)


def _rotate_binary_mask(mask: np.ndarray, center: tuple[float, float], angle_deg: float) -> np.ndarray:
    matrix = cv2.getRotationMatrix2D(center, float(angle_deg), 1.0)
    return cv2.warpAffine(mask, matrix, (mask.shape[1], mask.shape[0]), flags=cv2.INTER_NEAREST, borderValue=0)


def _rounded_rectangle(mask: np.ndarray, center: tuple[float, float], width: int, height: int, radius: int, angle: float) -> None:
    cx, cy = int(round(center[0])), int(round(center[1]))
    width, height = max(4, int(width)), max(4, int(height))
    radius = max(2, min(int(radius), width // 2, height // 2))
    x0, x1 = cx - width // 2, cx + width // 2
    y0, y1 = cy - height // 2, cy + height // 2
    local = np.zeros_like(mask)
    cv2.rectangle(local, (x0 + radius, y0), (x1 - radius, y1), 1, -1)
    cv2.rectangle(local, (x0, y0 + radius), (x1, y1 - radius), 1, -1)
    for point in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius), (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
        cv2.circle(local, point, radius, 1, -1)
    mask[:] = np.maximum(mask, _rotate_binary_mask(local, (center[0], center[1]), angle))


def generate_primitive_mask(family: str, size: int, rng: np.random.Generator) -> np.ndarray:
    mask = np.zeros((size, size), dtype=np.uint8)
    cx = float(size / 2 + rng.uniform(-0.12, 0.12) * size)
    cy = float(size / 2 + rng.uniform(-0.12, 0.12) * size)
    if family == "disk":
        radius = int(rng.uniform(0.13, 0.28) * size)
        cv2.circle(mask, (round(cx), round(cy)), radius, 1, -1)
    elif family == "ellipse":
        axes = (int(rng.uniform(0.13, 0.29) * size), int(rng.uniform(0.10, 0.23) * size))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, float(rng.uniform(-180, 180)), 0, 360, 1, -1)
    elif family == "rectangle":
        _rotated_rectangle(
            mask,
            (cx, cy),
            (float(rng.uniform(0.24, 0.55) * size), float(rng.uniform(0.18, 0.42) * size)),
            float(rng.uniform(-180, 180)),
        )
    elif family == "rounded_rectangle":
        width = int(rng.uniform(0.28, 0.52) * size)
        height = int(rng.uniform(0.18, 0.38) * size)
        _rounded_rectangle(
            mask,
            (cx, cy),
            width,
            height,
            int(min(width, height) * rng.uniform(0.12, 0.38)),
            float(rng.uniform(-180, 180)),
        )
    elif family == "trapezoid":
        half_bottom = float(rng.uniform(0.15, 0.28) * size)
        half_top = half_bottom * float(rng.uniform(0.38, 0.82))
        half_height = float(rng.uniform(0.10, 0.21) * size)
        points = np.asarray(
            [
                [-half_bottom, half_height],
                [half_bottom, half_height],
                [half_top, -half_height],
                [-half_top, -half_height],
            ],
            dtype=np.float32,
        )
        angle = float(rng.uniform(-np.pi, np.pi))
        rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        points = (points @ rotation.T + np.asarray([cx, cy])).round().astype(np.int32)
        cv2.fillPoly(mask, [points], 1)
    elif family == "regular_polygon":
        _regular_polygon(
            mask,
            (cx, cy),
            float(rng.uniform(0.18, 0.31) * size),
            int(rng.integers(3, 9)),
            float(rng.uniform(-np.pi, np.pi)),
        )
    elif family == "annulus":
        outer = int(rng.uniform(0.18, 0.30) * size)
        inner = int(outer * rng.uniform(0.35, 0.66))
        cv2.circle(mask, (round(cx), round(cy)), outer, 1, -1)
        cv2.circle(mask, (round(cx), round(cy)), inner, 0, -1)
    elif family == "capsule":
        length = float(rng.uniform(0.20, 0.43) * size)
        radius = int(rng.uniform(0.055, 0.12) * size)
        theta = float(rng.uniform(-np.pi, np.pi))
        dx, dy = 0.5 * length * math.cos(theta), 0.5 * length * math.sin(theta)
        p1 = (round(cx - dx), round(cy - dy))
        p2 = (round(cx + dx), round(cy + dy))
        cv2.line(mask, p1, p2, 1, thickness=2 * radius)
        cv2.circle(mask, p1, radius, 1, -1)
        cv2.circle(mask, p2, radius, 1, -1)
    elif family == "cross":
        arm_length = float(rng.uniform(0.34, 0.55) * size)
        arm_width = float(rng.uniform(0.07, 0.15) * size)
        angle = float(rng.uniform(-180, 180))
        _rotated_rectangle(mask, (cx, cy), (arm_length, arm_width), angle)
        _rotated_rectangle(mask, (cx, cy), (arm_length, arm_width), angle + 90.0)
    elif family in {"l_shape", "t_shape"}:
        local = np.zeros_like(mask)
        long_side = int(rng.uniform(0.34, 0.52) * size)
        short_side = int(rng.uniform(0.07, 0.14) * size)
        cx_i, cy_i = int(round(cx)), int(round(cy))
        if family == "l_shape":
            cv2.rectangle(
                local,
                (cx_i - long_side // 2, cy_i - long_side // 2),
                (cx_i - long_side // 2 + short_side, cy_i + long_side // 2),
                1,
                -1,
            )
            cv2.rectangle(
                local,
                (cx_i - long_side // 2, cy_i + long_side // 2 - short_side),
                (cx_i + long_side // 2, cy_i + long_side // 2),
                1,
                -1,
            )
        else:
            cv2.rectangle(
                local,
                (cx_i - long_side // 2, cy_i - long_side // 2),
                (cx_i + long_side // 2, cy_i - long_side // 2 + short_side),
                1,
                -1,
            )
            cv2.rectangle(
                local,
                (cx_i - short_side // 2, cy_i - long_side // 2),
                (cx_i + short_side // 2, cy_i + long_side // 2),
                1,
                -1,
            )
        mask[:] = _rotate_binary_mask(local, (cx, cy), float(rng.uniform(-180, 180)))
    elif family == "paired_disks":
        radius_a = int(rng.uniform(0.09, 0.17) * size)
        radius_b = int(rng.uniform(0.09, 0.17) * size)
        separation = float(rng.uniform(0.24, 0.40) * size)
        theta = float(rng.uniform(-np.pi, np.pi))
        dx, dy = 0.5 * separation * math.cos(theta), 0.5 * separation * math.sin(theta)
        cv2.circle(mask, (round(cx - dx), round(cy - dy)), radius_a, 1, -1)
        cv2.circle(mask, (round(cx + dx), round(cy + dy)), radius_b, 1, -1)
    elif family == "three_disks":
        base_radius = float(rng.uniform(0.065, 0.115) * size)
        layout_radius = float(rng.uniform(0.15, 0.25) * size)
        angle0 = float(rng.uniform(-np.pi, np.pi))
        for index in range(3):
            theta = angle0 + index * 2.0 * np.pi / 3.0
            radius = int(base_radius * rng.uniform(0.82, 1.18))
            cv2.circle(
                mask,
                (round(cx + layout_radius * math.cos(theta)), round(cy + layout_radius * math.sin(theta))),
                radius,
                1,
                -1,
            )
    elif family == "parallel_bars":
        length = float(rng.uniform(0.34, 0.55) * size)
        width = float(rng.uniform(0.045, 0.095) * size)
        separation = float(rng.uniform(0.13, 0.24) * size)
        angle = float(rng.uniform(-180, 180))
        theta = math.radians(angle + 90.0)
        offset = (0.5 * separation * math.cos(theta), 0.5 * separation * math.sin(theta))
        _rotated_rectangle(mask, (cx - offset[0], cy - offset[1]), (length, width), angle)
        _rotated_rectangle(mask, (cx + offset[0], cy + offset[1]), (length, width), angle)
    elif family == "ring_with_disk":
        ring_radius = int(rng.uniform(0.13, 0.21) * size)
        ring_inner = int(ring_radius * rng.uniform(0.42, 0.64))
        angle = float(rng.uniform(-np.pi, np.pi))
        separation = float(rng.uniform(0.26, 0.37) * size)
        ring_center = (round(cx - 0.35 * separation * math.cos(angle)), round(cy - 0.35 * separation * math.sin(angle)))
        disk_center = (round(cx + 0.65 * separation * math.cos(angle)), round(cy + 0.65 * separation * math.sin(angle)))
        cv2.circle(mask, ring_center, ring_radius, 1, -1)
        cv2.circle(mask, ring_center, ring_inner, 0, -1)
        cv2.circle(mask, disk_center, int(rng.uniform(0.07, 0.13) * size), 1, -1)
    elif family == "sector":
        radius = int(rng.uniform(0.24, 0.34) * size)
        start = float(rng.uniform(-180, 180))
        span = float(rng.uniform(80, 180))
        cv2.ellipse(mask, (round(cx), round(cy)), (radius, radius), 0.0, start, start + span, 1, -1)
    else:
        raise KeyError(family)

    area_fraction = float(mask.mean())
    if not 0.018 <= area_fraction <= 0.55:
        raise RuntimeError(f"{family}: implausible area fraction {area_fraction:.5f}")
    if np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
        raise RuntimeError(f"{family}: shape touches the image border")
    return mask


def _low_frequency_field(size: int, rng: np.random.Generator) -> np.ndarray:
    coarse = rng.normal(0.0, 1.0, (7, 7)).astype(np.float32)
    field = cv2.resize(coarse, (size, size), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), 12.0)
    field -= float(field.mean())
    return field / max(float(field.std()), 1e-6)


def _motion_kernel(length: int, angle_deg: float) -> np.ndarray:
    length = max(1, int(length) | 1)
    kernel = np.zeros((length, length), dtype=np.float32)
    kernel[length // 2, :] = 1.0
    matrix = cv2.getRotationMatrix2D(((length - 1) / 2.0, (length - 1) / 2.0), angle_deg, 1.0)
    kernel = cv2.warpAffine(kernel, matrix, (length, length), flags=cv2.INTER_LINEAR)
    return kernel / max(float(kernel.sum()), 1e-12)


def render_pair(
    mask_highres: np.ndarray,
    rng: np.random.Generator,
    polarity: str,
    degradation_family: str,
    *,
    final_size: int,
    supersample_factor: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    high_size = int(mask_highres.shape[0])
    expected_high_size = int(final_size) * int(supersample_factor)
    if high_size != expected_high_size or mask_highres.shape[1] != expected_high_size:
        raise ValueError(
            f"High-resolution mask must be {expected_high_size}x{expected_high_size}, "
            f"got {mask_highres.shape}"
        )
    size = int(final_size)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xn = (xx - size / 2.0) / (size / 2.0)
    yn = (yy - size / 2.0) / (size / 2.0)
    if polarity == "bright":
        background = float(rng.uniform(36, 92))
        contrast = float(rng.uniform(78, 132))
    elif polarity == "dark":
        background = float(rng.uniform(166, 222))
        contrast = -float(rng.uniform(78, 132))
    else:
        raise ValueError(polarity)

    # The clean target is genuinely rendered at 4x and then area-averaged.
    # This makes subpixel boundary coverage part of the label instead of
    # relying on a post-hoc blur of a jagged low-resolution drawing.
    field_low = _low_frequency_field(size, rng)
    field_high = cv2.resize(field_low, (high_size, high_size), interpolation=cv2.INTER_CUBIC)
    x_high = np.linspace(-1.0, 1.0, high_size, dtype=np.float32)[None, :]
    y_high = np.linspace(-1.0, 1.0, high_size, dtype=np.float32)[:, None]
    truth_high = (
        background
        + float(rng.uniform(0.0, 3.0)) * field_high
        + float(rng.uniform(-5, 5)) * x_high
        + float(rng.uniform(-5, 5)) * y_high
        + contrast * mask_highres.astype(np.float32)
    )
    truth = cv2.resize(truth_high, (size, size), interpolation=cv2.INTER_AREA)
    coverage = cv2.resize(
        mask_highres.astype(np.float32) * 255.0,
        (size, size),
        interpolation=cv2.INTER_AREA,
    )

    blur_sigma = float(rng.uniform(0.75, 2.75))
    anisotropy = 1.0
    motion_length = 1
    motion_angle = 0.0
    halo_strength = 0.0
    ghost_alpha = 0.0
    ghost_shift_xy = [0.0, 0.0]
    poisson_peak = 0.0
    if degradation_family == "gaussian_blur":
        source = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
    elif degradation_family == "anisotropic_blur":
        anisotropy = float(rng.uniform(1.3, 2.2))
        kernel = _analytic_gaussian_kernel(17, blur_sigma * anisotropy, blur_sigma, float(rng.uniform(-180, 180)))
        source = cv2.filter2D(truth, -1, kernel, borderType=cv2.BORDER_REFLECT)
    elif degradation_family == "short_motion_blur":
        source = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
        motion_length = int(rng.choice([3, 5, 7]))
        motion_angle = float(rng.uniform(-180, 180))
        source = cv2.filter2D(source, -1, _motion_kernel(motion_length, motion_angle), borderType=cv2.BORDER_REFLECT)
    elif degradation_family == "contrast_illumination":
        source = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
    elif degradation_family == "mild_defocus":
        diameter = int(rng.choice([7, 9, 11, 13]))
        kernel = np.zeros((diameter, diameter), dtype=np.float32)
        cv2.circle(kernel, (diameter // 2, diameter // 2), max(1, diameter // 3), 1.0, -1)
        kernel /= max(float(kernel.sum()), 1e-12)
        source = cv2.filter2D(truth, -1, kernel, borderType=cv2.BORDER_REFLECT)
    elif degradation_family == "mild_halo":
        source = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
        broad = cv2.GaussianBlur(source, (0, 0), float(rng.uniform(3.0, 5.5)))
        halo_strength = float(rng.uniform(0.12, 0.35))
        source = source + halo_strength * (broad - source)
    elif degradation_family == "poisson_gaussian":
        source = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
        poisson_peak = float(rng.uniform(30.0, 90.0))
        normalized = np.clip(source / 255.0, 0.0, 1.0)
        source = rng.poisson(normalized * poisson_peak).astype(np.float32) * (255.0 / poisson_peak)
    elif degradation_family == "subpixel_ghost":
        source = cv2.GaussianBlur(truth, (0, 0), blur_sigma)
        dx, dy = (float(value) for value in rng.uniform(-1.4, 1.4, size=2))
        ghost_alpha = float(rng.uniform(0.10, 0.28))
        ghost = cv2.warpAffine(
            source,
            np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32),
            (size, size),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        source = (1.0 - ghost_alpha) * source + ghost_alpha * ghost
        ghost_shift_xy = [dx, dy]
    else:
        raise KeyError(degradation_family)

    contrast_scale = float(rng.uniform(0.55, 0.90))
    source_mean = float(source.mean())
    source = source_mean + contrast_scale * (source - source_mean)
    illumination_x = float(rng.uniform(-12, 12))
    illumination_y = float(rng.uniform(-12, 12))
    if degradation_family == "contrast_illumination":
        illumination_x *= 1.8
        illumination_y *= 1.8
    source += illumination_x * xn + illumination_y * yn
    noise_sigma = float(rng.uniform(1.0, 6.0))
    source += rng.normal(0.0, noise_sigma, source.shape).astype(np.float32)

    source_u8 = np.clip(np.rint(source), 0, 255).astype(np.uint8)
    truth_u8 = np.clip(np.rint(truth), 0, 255).astype(np.uint8)
    coverage_u8 = np.clip(np.rint(coverage), 0, 255).astype(np.uint8)
    anti_alias_edge_pixels = int(np.count_nonzero((coverage_u8 > 0) & (coverage_u8 < 255)))
    if anti_alias_edge_pixels <= 0:
        raise RuntimeError("Supersampled geometry produced no anti-aliased boundary pixels")
    if np.array_equal(source_u8, truth_u8):
        raise RuntimeError("Synthetic degradation unexpectedly produced an identity pair")
    return source_u8, truth_u8, coverage_u8, {
        "degradation_family": degradation_family,
        "label_supersample_factor": int(supersample_factor),
        "label_downsample_method": "cv2.INTER_AREA",
        "anti_alias_edge_pixel_count": anti_alias_edge_pixels,
        "blur_sigma_px": blur_sigma,
        "blur_anisotropy": anisotropy,
        "motion_length_px": motion_length,
        "motion_angle_deg": motion_angle,
        "halo_strength": halo_strength,
        "ghost_alpha": ghost_alpha,
        "ghost_shift_xy": ghost_shift_xy,
        "poisson_peak": poisson_peak,
        "contrast_scale": contrast_scale,
        "noise_sigma": noise_sigma,
        "illumination_gradient_xy": [illumination_x, illumination_y],
    }


def compute_geometry(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask_u8 = (mask > 0).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    centerline = cv2.morphologyEx(mask_u8, cv2.MORPH_GRADIENT, kernel)
    centerline = (centerline > 0).astype(np.uint8) * 255
    boundary = cv2.dilate(centerline, kernel, iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary, centerline, distance


def _write_geometry(
    package_dir: Path,
    relative_stem: Path,
    mask: np.ndarray,
    anti_alias_coverage: np.ndarray,
) -> dict[str, str]:
    boundary, centerline, distance = compute_geometry(mask)
    boundary_rel = Path("geom") / "boundary" / relative_stem.with_suffix(".bmp")
    centerline_rel = Path("geom") / "centerline" / relative_stem.with_suffix(".bmp")
    distance_rel = Path("geom") / "distance" / relative_stem.with_suffix(".npy")
    mask_rel = Path("mask") / relative_stem.with_suffix(".bmp")
    mask_aa_rel = Path("mask_aa") / relative_stem.with_suffix(".bmp")
    _write_image(package_dir / boundary_rel, boundary)
    _write_image(package_dir / centerline_rel, centerline)
    _write_image(package_dir / mask_rel, mask * 255)
    _write_image(package_dir / mask_aa_rel, anti_alias_coverage)
    distance_path = package_dir / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance, allow_pickle=False)
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
        "geometry_mask": mask_rel.as_posix(),
        "geometry_mask_aa": mask_aa_rel.as_posix(),
    }


def _assign_splits(profile: str) -> dict[tuple[str, int], str]:
    plan = build_plan(profile)
    geometry_count = int(plan["geometry_count_per_family"])
    counts = plan["geometry_split_per_family"]
    result: dict[tuple[str, int], str] = {}
    base_seed = int(CONFIG["dataset"]["split_seed"])
    for family_index, family in enumerate(SHAPE_FAMILIES):
        rng = np.random.default_rng(base_seed + family_index * 1009)
        order = rng.permutation(geometry_count).tolist()
        n_val = int(counts["validation"])
        n_test = int(counts["internal_test"])
        val_set = set(order[:n_val])
        test_set = set(order[n_val:n_val + n_test])
        for geometry_index in range(geometry_count):
            split = "validation" if geometry_index in val_set else "internal_test" if geometry_index in test_set else "train"
            result[(family, geometry_index)] = split
    return result


def _flatten_keys(value, prefix: str = "") -> Iterable[tuple[str, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield child_prefix, child
            yield from _flatten_keys(child, child_prefix)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _flatten_keys(child, f"{prefix}[{index}]")


def _assert_safe_relative_path(value: str, expected_prefix: str) -> None:
    path = PurePosixPath(str(value).replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"External or parent path is forbidden in R75: {value}")
    if not path.parts or path.parts[0].lower() != expected_prefix.lower():
        raise RuntimeError(f"Expected {expected_prefix}/ relative path, got: {value}")


def assert_record_provenance(records: list[dict]) -> None:
    for row_index, record in enumerate(records):
        for dotted_key, value in _flatten_keys(record):
            leaf = dotted_key.rsplit(".", 1)[-1].split("[", 1)[0].lower()
            if leaf in FORBIDDEN_RECORD_KEYS:
                raise RuntimeError(f"Forbidden source key in record {row_index}: {dotted_key}")
            if leaf in {
                "package_src",
                "package_lbl",
                "geometry_boundary",
                "geometry_centerline",
                "geometry_distance",
                "geometry_mask",
                "geometry_mask_aa",
            }:
                continue
            if isinstance(value, str):
                lowered = value.lower()
                hit = next((token for token in FORBIDDEN_VALUE_TOKENS if token in lowered), None)
                if hit is not None:
                    raise RuntimeError(f"Forbidden source token '{hit}' in record {row_index}: {dotted_key}")
        provenance = record.get("provenance", {})
        if provenance.get("kind") != PROVENANCE_KIND or provenance.get("generator") != GENERATOR_NAME:
            raise RuntimeError(f"Record {row_index} has unapproved provenance: {provenance}")
        _assert_safe_relative_path(record["package_src"], "src")
        _assert_safe_relative_path(record["package_lbl"], "lbl")
        _assert_safe_relative_path(record["geometry_boundary"], "geom")
        _assert_safe_relative_path(record["geometry_centerline"], "geom")
        _assert_safe_relative_path(record["geometry_distance"], "geom")
        _assert_safe_relative_path(record["geometry_mask"], "mask")
        _assert_safe_relative_path(record["geometry_mask_aa"], "mask_aa")


def audit_package(package_dir: Path, manifest: dict, *, verify_files: bool = True) -> dict:
    package_dir = Path(package_dir).resolve()
    records = list(manifest.get("pairs", []))
    assert_record_provenance(records)
    expected = int(manifest.get("total_pairs", -1))
    if expected != len(records):
        raise RuntimeError(f"Manifest count mismatch: expected {expected}, found {len(records)}")
    geometry_splits: dict[str, set[str]] = defaultdict(set)
    split_counts = Counter()
    polarity_counts = Counter()
    family_counts = Counter()
    degradation_counts = Counter()
    anti_alias_edge_counts: list[int] = []
    missing: list[str] = []
    for record in records:
        geometry_splits[str(record["geometry_id"])].add(str(record["split"]))
        split_counts[str(record["split"])] += 1
        polarity_counts[str(record["polarity"])] += 1
        family_counts[str(record["shape_family"])] += 1
        degradation_counts[str(record["degradation_family"])] += 1
        anti_alias_edge_counts.append(int(record.get("anti_alias_edge_pixel_count", 0)))
        if verify_files:
            for key in (
                "package_src",
                "package_lbl",
                "geometry_boundary",
                "geometry_centerline",
                "geometry_distance",
                "geometry_mask",
                "geometry_mask_aa",
            ):
                if not (package_dir / record[key]).is_file():
                    missing.append(record[key])
    leaked = sorted(group for group, splits in geometry_splits.items() if len(splits) != 1)
    if leaked:
        raise RuntimeError(f"Geometry leakage across splits: {leaked[:5]}")
    if missing:
        raise RuntimeError(f"Missing {len(missing)} generated files; first={missing[0]}")
    if set(family_counts) != set(SHAPE_FAMILIES):
        raise RuntimeError(f"Shape family mismatch: {sorted(family_counts)}")
    if abs(polarity_counts["bright"] - polarity_counts["dark"]) > 1:
        raise RuntimeError(f"Polarity imbalance: {dict(polarity_counts)}")
    expected_factor = int(CONFIG["dataset"]["label_supersample_factor"])
    if any(int(record.get("label_supersample_factor", 0)) != expected_factor for record in records):
        raise RuntimeError("Label supersampling factor is missing or inconsistent")
    if not anti_alias_edge_counts or min(anti_alias_edge_counts) <= 0:
        raise RuntimeError("At least one label lacks an anti-aliased boundary")
    psf = manifest.get("analytic_psf", {})
    if psf.get("source_kind") != "analytic_gaussian_only" or psf.get("measured_data_used") is not False:
        raise RuntimeError("R75 requires a fully analytic PSF bank")
    if verify_files:
        psf_path = package_dir / str(psf.get("relative_path", ""))
        if not psf_path.is_file() or _sha256(psf_path) != psf.get("sha256"):
            raise RuntimeError("Analytic PSF bank is missing or changed")
    audit = {
        "passed": True,
        "experiment_id": CONFIG["experiment_id"],
        "profile": manifest.get("profile"),
        "total_pairs": len(records),
        "geometry_count": len(geometry_splits),
        "split_counts": dict(sorted(split_counts.items())),
        "polarity_counts": dict(sorted(polarity_counts.items())),
        "shape_family_counts": dict(sorted(family_counts.items())),
        "degradation_family_counts": dict(sorted(degradation_counts.items())),
        "label_supersample_factor": expected_factor,
        "label_downsample_method": "cv2.INTER_AREA",
        "anti_alias_edge_pixel_count_min": min(anti_alias_edge_counts),
        "anti_alias_edge_pixel_count_mean": float(np.mean(anti_alias_edge_counts)),
        "anti_alias_edge_pixel_count_max": max(anti_alias_edge_counts),
        "geometry_split_overlap_count": len(leaked),
        "real_image_pixels_used": False,
        "measured_shape_templates_used": False,
        "legacy_training_pairs_used": False,
        "checkpoint_data_used": False,
        "fitted_or_measured_psf_used": False,
        "required_provenance_kind": PROVENANCE_KIND,
        "required_generator": GENERATOR_NAME,
    }
    return audit


def _write_fixed_split(package_dir: Path, records: list[dict]) -> tuple[Path, dict]:
    source_paths = sorted(record["package_src"] for record in records)
    pair_by_src = {record["package_src"]: record for record in records}
    train_idx: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []
    index_groups: dict[int, str] = {}
    for index, path in enumerate(source_paths):
        record = pair_by_src[path]
        split = str(record["split"])
        target = train_idx if split == "train" else val_idx if split == "validation" else test_idx
        target.append(index)
        index_groups[index] = str(record["geometry_id"])
    group_sets = {
        "train": {index_groups[index] for index in train_idx},
        "validation": {index_groups[index] for index in val_idx},
        "internal_test": {index_groups[index] for index in test_idx},
    }
    overlaps = {
        "train_validation": sorted(group_sets["train"] & group_sets["validation"]),
        "train_internal_test": sorted(group_sets["train"] & group_sets["internal_test"]),
        "validation_internal_test": sorted(group_sets["validation"] & group_sets["internal_test"]),
    }
    if any(overlaps.values()):
        raise RuntimeError(f"Fixed split geometry leakage: {overlaps}")
    seed = int(CONFIG["dataset"]["split_seed"])
    split_dir = package_dir / "splits" / f"geometry_seed{seed}"
    split_dir.mkdir(parents=True, exist_ok=True)
    np.save(split_dir / "train_idx.npy", np.asarray(train_idx, dtype=np.int64), allow_pickle=False)
    np.save(split_dir / "val_idx.npy", np.asarray(val_idx, dtype=np.int64), allow_pickle=False)
    np.save(split_dir / "test_idx.npy", np.asarray(test_idx, dtype=np.int64), allow_pickle=False)
    metadata = {
        "split_type": "r75_geometry_grouped_train_validation_internal_test",
        "seed": seed,
        "source_path_count": len(source_paths),
        "train_count": len(train_idx),
        "validation_count": len(val_idx),
        "internal_test_count": len(test_idx),
        "train_geometry_count": len(group_sets["train"]),
        "validation_geometry_count": len(group_sets["validation"]),
        "internal_test_geometry_count": len(group_sets["internal_test"]),
        "geometry_overlap_count": sum(len(values) for values in overlaps.values()),
        "geometry_overlap_examples": {key: values[:5] for key, values in overlaps.items()},
        "source_paths_sorted": source_paths,
    }
    _json_dump(split_dir / "split_meta.json", metadata)
    return split_dir, metadata


def _write_preview(package_dir: Path, records: list[dict], profile: str) -> Path:
    selected = []
    for family in SHAPE_FAMILIES:
        selected.append(next(row for row in records if row["shape_family"] == family and row["polarity"] == "bright"))
    tile_size = 192
    label_height = 30
    canvas = np.full((4 * (tile_size + label_height), len(selected) * tile_size), 245, dtype=np.uint8)
    row_keys = (
        ("package_src", "Raw"),
        ("package_lbl", "Truth"),
        ("geometry_mask_aa", "4x area AA"),
        ("geometry_mask", "Binary geometry"),
    )
    for column, record in enumerate(selected):
        for row_index, (key, row_label) in enumerate(row_keys):
            image = _read_gray(package_dir / record[key])
            image = cv2.resize(image, (tile_size, tile_size), interpolation=cv2.INTER_AREA)
            y0 = row_index * (tile_size + label_height)
            x0 = column * tile_size
            canvas[y0:y0 + tile_size, x0:x0 + tile_size] = image
            caption = f"{row_label}: {record['shape_family']}" if row_index == 0 else row_label
            cv2.putText(
                canvas,
                caption,
                (x0 + 5, y0 + tile_size + 21),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                30,
                1,
                cv2.LINE_AA,
            )
    preview_path = package_dir / "preview.png"
    _write_image(preview_path, canvas)
    if profile == "pilot":
        report_preview = REPORT_ROOT / "figures" / "r75_pilot_preview.png"
        _write_image(report_preview, canvas)
    return preview_path


def _write_antialias_zoom(package_dir: Path, records: list[dict], profile: str) -> Path:
    """Write a pixel-level visual proof of the 4x-to-1x label downsampling."""
    selected_families = ("ellipse", "rounded_rectangle", "trapezoid", "sector")
    selected = [
        next(
            row
            for row in records
            if row["shape_family"] == family and row["polarity"] == "bright"
        )
        for family in selected_families
    ]
    crop_size = 24
    zoom = 10
    tile_size = crop_size * zoom
    caption_height = 36
    row_keys = (
        ("geometry_mask", "Binary 1x"),
        ("geometry_mask_aa", "4x -> area average"),
        ("package_lbl", "Final truth label"),
    )
    canvas = np.full(
        (len(row_keys) * (tile_size + caption_height), len(selected) * tile_size),
        245,
        dtype=np.uint8,
    )
    for column, record in enumerate(selected):
        coverage = _read_gray(package_dir / record["geometry_mask_aa"])
        edge_y, edge_x = np.nonzero((coverage > 0) & (coverage < 255))
        if len(edge_y) == 0:
            raise RuntimeError(f"No anti-aliased edge pixels for zoom: {record['pair_id']}")
        center_y = (coverage.shape[0] - 1) / 2.0
        center_x = (coverage.shape[1] - 1) / 2.0
        distances = (edge_y - center_y) ** 2 + (edge_x - center_x) ** 2
        chosen = int(np.argmin(distances))
        y_center, x_center = int(edge_y[chosen]), int(edge_x[chosen])
        half = crop_size // 2
        y0 = min(max(0, y_center - half), coverage.shape[0] - crop_size)
        x0 = min(max(0, x_center - half), coverage.shape[1] - crop_size)
        for row_index, (key, row_label) in enumerate(row_keys):
            image = _read_gray(package_dir / record[key])
            crop = image[y0:y0 + crop_size, x0:x0 + crop_size]
            enlarged = cv2.resize(crop, (tile_size, tile_size), interpolation=cv2.INTER_NEAREST)
            target_y = row_index * (tile_size + caption_height)
            target_x = column * tile_size
            canvas[target_y:target_y + tile_size, target_x:target_x + tile_size] = enlarged
            caption = record["shape_family"] if row_index == 0 else row_label
            cv2.putText(
                canvas,
                caption,
                (target_x + 5, target_y + tile_size + 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                25,
                1,
                cv2.LINE_AA,
            )
    zoom_path = package_dir / "antialias_edge_zoom.png"
    _write_image(zoom_path, canvas)
    if profile == "pilot":
        report_zoom = REPORT_ROOT / "figures" / "r75_antialias_edge_zoom.png"
        _write_image(report_zoom, canvas)
    return zoom_path


def build_package(profile: str, output_root: Path = DATA_ROOT, *, force: bool = False) -> tuple[Path, dict, dict]:
    output_root = Path(output_root).resolve()
    package_dir = output_root / f"r75_{profile}_pure_primitives"
    manifest_path = package_dir / "manifest.json"
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("profile") != profile:
            raise RuntimeError(f"Profile mismatch in existing package: {manifest_path}")
        audit = audit_package(package_dir, manifest)
        _json_dump(package_dir / "source_audit.json", audit)
        return package_dir, manifest, audit
    if force:
        _safe_clean_package(package_dir, output_root)

    plan = build_plan(profile)
    package_dir.mkdir(parents=True, exist_ok=True)
    psf_path, psf_meta = ensure_analytic_psf(package_dir)
    split_by_geometry = _assign_splits(profile)
    geometry_count = int(plan["geometry_count_per_family"])
    renderings = int(plan["renderings_per_geometry"])
    image_size = int(plan["image_size"])
    supersample_factor = int(CONFIG["dataset"]["label_supersample_factor"])
    drawing_size = image_size * supersample_factor
    master_seed = int(CONFIG["dataset"]["split_seed"]) + 75_000_000
    records: list[dict] = []
    content_digest = hashlib.sha256()

    for family_index, family in enumerate(SHAPE_FAMILIES):
        for geometry_index in range(geometry_count):
            geometry_seed = master_seed + family_index * 1_000_000 + geometry_index * 100
            attempt = 0
            while True:
                geometry_rng = np.random.default_rng(geometry_seed + attempt)
                try:
                    mask_highres = generate_primitive_mask(family, drawing_size, geometry_rng)
                    break
                except RuntimeError:
                    attempt += 1
                    if attempt >= 100:
                        raise
            geometry_id = f"{family}:g{geometry_index:05d}:s{geometry_seed + attempt}"
            split = split_by_geometry[(family, geometry_index)]
            for rendering_index in range(renderings):
                rendering_seed = geometry_seed + 50_000 + rendering_index
                rng = np.random.default_rng(rendering_seed)
                polarity = "bright" if rendering_index % 2 == 0 else "dark"
                degradation = DEGRADATION_FAMILIES[(geometry_index + rendering_index) % len(DEGRADATION_FAMILIES)]
                source, label, coverage, rendering = render_pair(
                    mask_highres,
                    rng,
                    polarity,
                    degradation,
                    final_size=image_size,
                    supersample_factor=supersample_factor,
                )
                mask = (coverage >= 128).astype(np.uint8)
                stage = "stage_r75_base_primitives"
                filename = f"g{geometry_index:05d}_r{rendering_index:02d}.bmp"
                relative_stem = Path(stage) / family / polarity / filename
                src_rel = Path("src") / relative_stem
                lbl_rel = Path("lbl") / relative_stem
                _write_image(package_dir / src_rel, source)
                _write_image(package_dir / lbl_rel, label)
                geometry_paths = _write_geometry(package_dir, relative_stem, mask, coverage)
                content_digest.update(source.tobytes())
                content_digest.update(label.tobytes())
                content_digest.update(coverage.tobytes())
                records.append(
                    {
                        "pair_id": f"{family}/g{geometry_index:05d}/r{rendering_index:02d}",
                        "role": "pure_primitive_synthetic",
                        "feature": family,
                        "shape_family": family,
                        "geometry_id": geometry_id,
                        "split": split,
                        "polarity": polarity,
                        "bias_px": 0.0,
                        "geometry_seed": geometry_seed + attempt,
                        "rendering_seed": rendering_seed,
                        "generation_attempt": attempt,
                        "package_src": src_rel.as_posix(),
                        "package_lbl": lbl_rel.as_posix(),
                        "provenance": {
                            "kind": PROVENANCE_KIND,
                            "generator": GENERATOR_NAME,
                            "external_pixels": False,
                            "measured_geometry": False,
                        },
                        **rendering,
                        **geometry_paths,
                    }
                )

    records.sort(key=lambda row: row["package_src"])
    split_dir, split_meta = _write_fixed_split(package_dir, records)
    preview_path = _write_preview(package_dir, records, profile)
    antialias_zoom_path = _write_antialias_zoom(package_dir, records, profile)
    manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "profile": profile,
        "generator_version": GENERATOR_NAME,
        "generator_file": Path(__file__).name,
        "config_file": CONFIG_PATH.name,
        "master_seed": master_seed,
        "image_size": [image_size, image_size],
        "drawing_size": [drawing_size, drawing_size],
        "label_supersample_factor": supersample_factor,
        "label_downsample_method": "cv2.INTER_AREA",
        "shape_families": list(SHAPE_FAMILIES),
        "degradation_families": list(DEGRADATION_FAMILIES),
        "total_pairs": len(records),
        "geometry_count": len({row["geometry_id"] for row in records}),
        "renderings_per_geometry": renderings,
        "training_data_contract": {
            "procedural_pixels_only": True,
            "analytic_primitives_only": True,
            "legacy_pairs_imported": False,
            "measured_sample_templates_imported": False,
            "radius_lists_imported": False,
            "checkpoint_outputs_imported": False,
            "target_boundary_bias_px": 0.0,
            "label_drawn_at_high_resolution": True,
            "label_supersample_factor": supersample_factor,
            "label_downsample_method": "cv2.INTER_AREA",
        },
        "analytic_psf": psf_meta,
        "content_sha256": content_digest.hexdigest(),
        "fixed_split_dir": split_dir.relative_to(package_dir).as_posix(),
        "fixed_split": split_meta,
        "preview": preview_path.relative_to(package_dir).as_posix(),
        "antialias_zoom": antialias_zoom_path.relative_to(package_dir).as_posix(),
        "pairs": records,
    }
    audit = audit_package(package_dir, manifest)
    _json_dump(manifest_path, manifest)
    _json_dump(package_dir / "source_audit.json", audit)
    return package_dir, manifest, audit


def write_formal_plan() -> Path:
    payload = {
        "experiment_id": CONFIG["experiment_id"],
        "status": "ready_to_generate_not_generated_by_this_plan",
        "formal_dataset": build_plan("formal"),
        "formal_training": CONFIG["training"],
        "source_isolation": CONFIG["source_isolation"],
        "promotion_rule": CONFIG["promotion_rule"],
    }
    path = REPORT_ROOT / "formal_dataset_plan.json"
    _json_dump(path, payload)
    return path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the pure-procedural R75 scratch-training package")
    parser.add_argument("--profile", choices=sorted(CONFIG["dataset"]["profiles"]), default="pilot")
    parser.add_argument("--output-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--write-formal-plan", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.write_formal_plan:
        path = write_formal_plan()
        print(json.dumps({"formal_plan": str(path), **build_plan("formal")}, indent=2, ensure_ascii=False))
        return 0
    if args.plan_only:
        print(json.dumps(build_plan(args.profile), indent=2, ensure_ascii=False))
        return 0
    package_dir, manifest, audit = build_package(args.profile, args.output_root, force=args.force)
    summary = {
        "package_dir": str(package_dir),
        "profile": args.profile,
        "total_pairs": manifest["total_pairs"],
        "geometry_count": manifest["geometry_count"],
        "split_counts": audit["split_counts"],
        "source_audit_passed": audit["passed"],
        "real_image_pixels_used": audit["real_image_pixels_used"],
        "measured_shape_templates_used": audit["measured_shape_templates_used"],
        "fitted_or_measured_psf_used": audit["fitted_or_measured_psf_used"],
        "fixed_split_dir": str(package_dir / manifest["fixed_split_dir"]),
        "preview": str(package_dir / manifest["preview"]),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
