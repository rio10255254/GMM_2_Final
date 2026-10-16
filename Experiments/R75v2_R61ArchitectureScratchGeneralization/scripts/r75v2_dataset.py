"""Build the R75-v2 scratch-training package from procedural geometry only.

The generator intentionally has no loader for legacy training data, microscope
images, extracted contours, model checkpoints, or teacher outputs.  Every
training pixel and every target contour is generated here from recorded seeds.
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
PROVENANCE_KIND = str(CONFIG["source_isolation"]["required_provenance_kind"])
GENERATOR_NAME = str(CONFIG["source_isolation"]["required_generator"])
STAGE_NAME = str(CONFIG["dataset"]["stage_name"])
ROLE_ORDER = tuple(str(name) for name in CONFIG["dataset"]["roles"])
FORBIDDEN_VALUE_TOKENS = tuple(
    str(token).lower() for token in CONFIG["source_isolation"]["forbidden_value_tokens"]
)
FORBIDDEN_RECORD_KEYS = {
    str(key).lower() for key in CONFIG["source_isolation"]["forbidden_record_keys"]
}

BASIC_FAMILIES = (
    "disk",
    "ellipse",
    "rectangle",
    "rounded_rectangle",
    "trapezoid",
    "regular_polygon",
    "annulus",
    "capsule",
    "cross",
    "l_shape",
    "t_shape",
    "sector",
    "diamond",
    "chevron",
)
FINE_FAMILIES = (
    "fourier_lobed",
    "deep_notches",
    "thin_neck",
    "crescent",
    "star",
    "gear",
    "teardrop",
    "asymmetric_blob",
    "concave_polygon",
    "hollow_polygon",
    "broken_ring",
    "serpentine",
)
LAYOUT_FAMILIES = (
    "random_array",
    "sparse_cluster",
    "dense_cluster",
    "multi_scale",
    "edge_truncated",
    "staggered_array",
    "mixed_holes",
    "nested_layout",
)
EXPOSURE_FAMILIES = (
    "disk",
    "ellipse",
    "rounded_rectangle",
    "trapezoid",
    "annulus",
    "capsule",
    "cross",
    "l_shape",
    "sector",
    "fourier_lobed",
    "thin_neck",
    "crescent",
    "star",
    "teardrop",
    "asymmetric_blob",
    "broken_ring",
)
BOUNDARY_FAMILIES = (
    "ellipse",
    "rounded_rectangle",
    "trapezoid",
    "annulus",
    "fourier_lobed",
    "deep_notches",
    "thin_neck",
    "crescent",
    "star",
    "gear",
    "teardrop",
    "asymmetric_blob",
    "concave_polygon",
    "hollow_polygon",
    "broken_ring",
    "serpentine",
)
IDENTITY_FAMILIES = EXPOSURE_FAMILIES
ROLE_FAMILIES = {
    "basic_geometry": BASIC_FAMILIES,
    "fine_noncircular": FINE_FAMILIES,
    "multi_object_layout": LAYOUT_FAMILIES,
    "exposure_sequence": EXPOSURE_FAMILIES,
    "boundary_fade_mixed": BOUNDARY_FAMILIES,
    "identity_guard": IDENTITY_FAMILIES,
}
COMPOSITE_RECIPES = (
    "blur_read_noise",
    "anisotropic_illumination",
    "motion_gamma_noise",
    "defocus_vignette_quantization",
    "asymmetric_halo_banding",
    "ghost_shadow_noise",
    "blur_saturation_texture",
    "mixed_microscopy",
)
EXPOSURE_LEVELS = ("very_dark", "dark", "mid", "bright", "very_bright")


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
        raise KeyError(f"Unknown R75-v2 profile: {profile}")
    return dict(profiles[profile])


def build_plan(profile: str) -> dict:
    profile_cfg = _profile_config(profile)
    role_geometry_counts = {
        str(role): int(count)
        for role, count in profile_cfg["role_geometry_counts"].items()
    }
    role_split_geometry_counts = {
        str(role): {str(split): int(count) for split, count in counts.items()}
        for role, counts in profile_cfg["role_split_geometry_counts"].items()
    }
    if tuple(role_geometry_counts) != ROLE_ORDER:
        raise RuntimeError(f"Profile {profile} role ordering/configuration changed")

    role_pair_counts: dict[str, int] = {}
    role_split_pair_counts: dict[str, dict[str, int]] = {}
    pair_split_counts = Counter()
    geometry_count = 0
    expected_pairs = 0
    for role in ROLE_ORDER:
        geometries = int(role_geometry_counts[role])
        renderings = int(CONFIG["dataset"]["roles"][role]["renderings_per_geometry"])
        split_counts = role_split_geometry_counts[role]
        if sum(split_counts.values()) != geometries:
            raise RuntimeError(f"{profile}/{role}: split geometry counts do not sum to {geometries}")
        if set(split_counts) != {"train", "validation", "internal_test"}:
            raise RuntimeError(f"{profile}/{role}: split names are incomplete")
        role_pairs = geometries * renderings
        role_pair_counts[role] = role_pairs
        role_split_pair_counts[role] = {
            split: count * renderings for split, count in split_counts.items()
        }
        for split, count in role_split_pair_counts[role].items():
            pair_split_counts[split] += count
        geometry_count += geometries
        expected_pairs += role_pairs

    if expected_pairs != int(profile_cfg["expected_pairs"]):
        raise RuntimeError(
            f"Profile {profile} expected {profile_cfg['expected_pairs']} pairs, planned {expected_pairs}"
        )
    return {
        "profile": profile,
        "image_size": int(CONFIG["dataset"]["image_size"]),
        "label_supersample_factor": int(CONFIG["dataset"]["label_supersample_factor"]),
        "drawing_size": int(CONFIG["dataset"]["image_size"])
        * int(CONFIG["dataset"]["label_supersample_factor"]),
        "geometry_count": geometry_count,
        "role_geometry_counts": role_geometry_counts,
        "role_pair_counts": role_pair_counts,
        "role_split_geometry_counts": role_split_geometry_counts,
        "role_split_pair_counts": role_split_pair_counts,
        "pair_split_counts": dict(pair_split_counts),
        "expected_pairs": expected_pairs,
        "estimated_payload_gib": round(
            expected_pairs * int(CONFIG["dataset"]["image_size"]) ** 2 * 11 / (1024**3),
            2,
        ),
        "generator": GENERATOR_NAME,
        "contains_real_pixels": False,
        "contains_measured_shapes": False,
        "contains_checkpoint_data": False,
        "contains_pseudo_labels": False,
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


def _analytic_gaussian_kernel(
    size: int,
    sigma_x: float,
    sigma_y: float,
    theta_deg: float,
) -> np.ndarray:
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


def _rotated_rectangle(
    mask: np.ndarray,
    center: tuple[float, float],
    size: tuple[float, float],
    angle: float,
    value: int = 1,
) -> None:
    points = cv2.boxPoints((center, size, angle)).round().astype(np.int32)
    cv2.fillPoly(mask, [points], int(value))


def _regular_polygon(
    mask: np.ndarray,
    center: tuple[float, float],
    radius: float,
    sides: int,
    angle: float,
    value: int = 1,
) -> None:
    theta = angle + np.arange(sides, dtype=np.float32) * (2.0 * np.pi / sides)
    points = np.stack(
        [center[0] + radius * np.cos(theta), center[1] + radius * np.sin(theta)],
        axis=1,
    ).round().astype(np.int32)
    cv2.fillPoly(mask, [points], int(value))


def _rotate_binary_mask(
    mask: np.ndarray,
    center: tuple[float, float],
    angle_deg: float,
) -> np.ndarray:
    matrix = cv2.getRotationMatrix2D(center, float(angle_deg), 1.0)
    return cv2.warpAffine(
        mask,
        matrix,
        (mask.shape[1], mask.shape[0]),
        flags=cv2.INTER_NEAREST,
        borderValue=0,
    )


def _rounded_rectangle(
    mask: np.ndarray,
    center: tuple[float, float],
    width: int,
    height: int,
    radius: int,
    angle: float,
    value: int = 1,
) -> None:
    cx, cy = int(round(center[0])), int(round(center[1]))
    width, height = max(4, int(width)), max(4, int(height))
    radius = max(2, min(int(radius), width // 2, height // 2))
    x0, x1 = cx - width // 2, cx + width // 2
    y0, y1 = cy - height // 2, cy + height // 2
    local = np.zeros_like(mask)
    cv2.rectangle(local, (x0 + radius, y0), (x1 - radius, y1), int(value), -1)
    cv2.rectangle(local, (x0, y0 + radius), (x1, y1 - radius), int(value), -1)
    for point in (
        (x0 + radius, y0 + radius),
        (x1 - radius, y0 + radius),
        (x0 + radius, y1 - radius),
        (x1 - radius, y1 - radius),
    ):
        cv2.circle(local, point, radius, int(value), -1)
    rotated = _rotate_binary_mask(local, (center[0], center[1]), angle)
    if value:
        mask[:] = np.maximum(mask, rotated)
    else:
        mask[rotated > 0] = 0


def _polar_polygon(
    mask: np.ndarray,
    center: tuple[float, float],
    radii: np.ndarray,
    angles: np.ndarray,
    value: int = 1,
) -> None:
    points = np.stack(
        [
            center[0] + radii * np.cos(angles),
            center[1] + radii * np.sin(angles),
        ],
        axis=1,
    ).round().astype(np.int32)
    cv2.fillPoly(mask, [points], int(value))


def _draw_capsule(
    mask: np.ndarray,
    center: tuple[float, float],
    length: float,
    radius: int,
    theta: float,
    value: int = 1,
) -> None:
    dx, dy = 0.5 * length * math.cos(theta), 0.5 * length * math.sin(theta)
    p1 = (round(center[0] - dx), round(center[1] - dy))
    p2 = (round(center[0] + dx), round(center[1] + dy))
    cv2.line(mask, p1, p2, int(value), thickness=max(1, 2 * int(radius)))
    cv2.circle(mask, p1, int(radius), int(value), -1)
    cv2.circle(mask, p2, int(radius), int(value), -1)


def _draw_basic_mask(
    family: str,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    mask = np.zeros((size, size), dtype=np.uint8)
    cx = float(size / 2 + rng.uniform(-0.10, 0.10) * size)
    cy = float(size / 2 + rng.uniform(-0.10, 0.10) * size)
    if family == "disk":
        cv2.circle(mask, (round(cx), round(cy)), int(rng.uniform(0.13, 0.28) * size), 1, -1)
    elif family == "ellipse":
        axes = (
            int(rng.uniform(0.13, 0.29) * size),
            int(rng.uniform(0.09, 0.23) * size),
        )
        cv2.ellipse(
            mask,
            (round(cx), round(cy)),
            axes,
            float(rng.uniform(-180, 180)),
            0,
            360,
            1,
            -1,
        )
    elif family == "rectangle":
        _rotated_rectangle(
            mask,
            (cx, cy),
            (
                float(rng.uniform(0.24, 0.55) * size),
                float(rng.uniform(0.18, 0.42) * size),
            ),
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
        half_top = half_bottom * float(rng.uniform(0.35, 0.82))
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
        rotation = np.asarray(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]],
            dtype=np.float32,
        )
        points = (points @ rotation.T + np.asarray([cx, cy])).round().astype(np.int32)
        cv2.fillPoly(mask, [points], 1)
    elif family == "regular_polygon":
        _regular_polygon(
            mask,
            (cx, cy),
            float(rng.uniform(0.18, 0.31) * size),
            int(rng.integers(3, 10)),
            float(rng.uniform(-np.pi, np.pi)),
        )
    elif family == "annulus":
        outer = int(rng.uniform(0.18, 0.30) * size)
        inner = int(outer * rng.uniform(0.32, 0.68))
        cv2.circle(mask, (round(cx), round(cy)), outer, 1, -1)
        cv2.circle(mask, (round(cx), round(cy)), inner, 0, -1)
    elif family == "capsule":
        _draw_capsule(
            mask,
            (cx, cy),
            float(rng.uniform(0.20, 0.43) * size),
            int(rng.uniform(0.05, 0.12) * size),
            float(rng.uniform(-np.pi, np.pi)),
        )
    elif family == "cross":
        arm_length = float(rng.uniform(0.34, 0.55) * size)
        arm_width = float(rng.uniform(0.06, 0.15) * size)
        angle = float(rng.uniform(-180, 180))
        _rotated_rectangle(mask, (cx, cy), (arm_length, arm_width), angle)
        _rotated_rectangle(mask, (cx, cy), (arm_length, arm_width), angle + 90.0)
    elif family in {"l_shape", "t_shape"}:
        local = np.zeros_like(mask)
        long_side = int(rng.uniform(0.34, 0.52) * size)
        short_side = int(rng.uniform(0.06, 0.14) * size)
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
    elif family == "sector":
        radius = int(rng.uniform(0.24, 0.34) * size)
        start = float(rng.uniform(-180, 180))
        span = float(rng.uniform(65, 205))
        cv2.ellipse(
            mask,
            (round(cx), round(cy)),
            (radius, radius),
            0.0,
            start,
            start + span,
            1,
            -1,
        )
    elif family == "diamond":
        axes = (
            float(rng.uniform(0.18, 0.30) * size),
            float(rng.uniform(0.13, 0.25) * size),
        )
        points = np.asarray(
            [[0, -axes[1]], [axes[0], 0], [0, axes[1]], [-axes[0], 0]],
            dtype=np.float32,
        )
        angle = float(rng.uniform(-np.pi, np.pi))
        rotation = np.asarray(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]],
            dtype=np.float32,
        )
        points = (points @ rotation.T + np.asarray([cx, cy])).round().astype(np.int32)
        cv2.fillPoly(mask, [points], 1)
    elif family == "chevron":
        length = float(rng.uniform(0.32, 0.48) * size)
        width = float(rng.uniform(0.06, 0.11) * size)
        opening = float(rng.uniform(40, 75))
        angle = float(rng.uniform(-180, 180))
        theta = math.radians(angle)
        offset = 0.10 * size
        p1 = (cx - offset * math.cos(theta), cy - offset * math.sin(theta))
        p2 = (cx + offset * math.cos(theta), cy + offset * math.sin(theta))
        _rotated_rectangle(mask, p1, (length, width), angle - opening / 2.0)
        _rotated_rectangle(mask, p2, (length, width), angle + opening / 2.0)
    else:
        raise KeyError(family)
    return mask


def _draw_fine_mask(
    family: str,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    mask = np.zeros((size, size), dtype=np.uint8)
    cx = float(size / 2 + rng.uniform(-0.07, 0.07) * size)
    cy = float(size / 2 + rng.uniform(-0.07, 0.07) * size)
    base = float(rng.uniform(0.18, 0.27) * size)
    angle0 = float(rng.uniform(-np.pi, np.pi))
    if family == "fourier_lobed":
        angles = np.linspace(0.0, 2.0 * np.pi, 240, endpoint=False, dtype=np.float32)
        radii = np.ones_like(angles) * base
        for harmonic in range(2, 7):
            amplitude = float(rng.uniform(-0.10, 0.10))
            phase = float(rng.uniform(-np.pi, np.pi))
            radii *= 1.0 + amplitude * np.cos(harmonic * angles + phase)
        radii = np.clip(radii, 0.58 * base, 1.38 * base)
        _polar_polygon(mask, (cx, cy), radii, angles + angle0)
    elif family == "deep_notches":
        cv2.circle(mask, (round(cx), round(cy)), round(base * 1.10), 1, -1)
        notch_count = int(rng.integers(2, 6))
        for index in range(notch_count):
            theta = angle0 + index * 2.0 * np.pi / notch_count + float(rng.uniform(-0.25, 0.25))
            radius = float(base * rng.uniform(0.95, 1.10))
            notch_radius = int(base * rng.uniform(0.24, 0.43))
            point = (
                round(cx + radius * math.cos(theta)),
                round(cy + radius * math.sin(theta)),
            )
            cv2.circle(mask, point, notch_radius, 0, -1)
    elif family == "thin_neck":
        theta = float(rng.uniform(-np.pi, np.pi))
        separation = float(rng.uniform(0.22, 0.34) * size)
        r1 = int(rng.uniform(0.105, 0.17) * size)
        r2 = int(rng.uniform(0.095, 0.16) * size)
        p1 = (
            round(cx - 0.5 * separation * math.cos(theta)),
            round(cy - 0.5 * separation * math.sin(theta)),
        )
        p2 = (
            round(cx + 0.5 * separation * math.cos(theta)),
            round(cy + 0.5 * separation * math.sin(theta)),
        )
        cv2.circle(mask, p1, r1, 1, -1)
        cv2.circle(mask, p2, r2, 1, -1)
        cv2.line(mask, p1, p2, 1, max(3, int(rng.uniform(0.018, 0.048) * size)))
    elif family == "crescent":
        outer = int(rng.uniform(0.20, 0.29) * size)
        cv2.circle(mask, (round(cx), round(cy)), outer, 1, -1)
        theta = float(rng.uniform(-np.pi, np.pi))
        shift = float(outer * rng.uniform(0.35, 0.68))
        inner = int(outer * rng.uniform(0.72, 0.92))
        cv2.circle(
            mask,
            (
                round(cx + shift * math.cos(theta)),
                round(cy + shift * math.sin(theta)),
            ),
            inner,
            0,
            -1,
        )
    elif family in {"star", "gear", "concave_polygon"}:
        if family == "star":
            teeth = int(rng.integers(5, 10))
            inner_ratio = float(rng.uniform(0.35, 0.62))
        elif family == "gear":
            teeth = int(rng.integers(9, 17))
            inner_ratio = float(rng.uniform(0.72, 0.88))
        else:
            teeth = int(rng.integers(4, 8))
            inner_ratio = float(rng.uniform(0.42, 0.70))
        angles = angle0 + np.arange(teeth * 2, dtype=np.float32) * np.pi / teeth
        radii = np.where(np.arange(teeth * 2) % 2 == 0, base * 1.18, base * inner_ratio)
        radii = radii.astype(np.float32) * rng.uniform(0.92, 1.08, size=teeth * 2)
        _polar_polygon(mask, (cx, cy), radii, angles)
    elif family == "teardrop":
        local = np.zeros_like(mask)
        center = (round(cx), round(cy + 0.22 * base))
        radius = round(base * 0.92)
        cv2.circle(local, center, radius, 1, -1)
        triangle = np.asarray(
            [
                [cx, cy - 1.35 * base],
                [cx - 0.76 * base, cy + 0.18 * base],
                [cx + 0.76 * base, cy + 0.18 * base],
            ],
            dtype=np.float32,
        ).round().astype(np.int32)
        cv2.fillPoly(local, [triangle], 1)
        mask[:] = _rotate_binary_mask(local, (cx, cy), math.degrees(angle0))
    elif family == "asymmetric_blob":
        angles = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False, dtype=np.float32)
        radii = np.ones_like(angles) * base
        for harmonic in (1, 2, 3, 5, 7):
            amplitude = float(rng.uniform(-0.12, 0.12))
            phase = float(rng.uniform(-np.pi, np.pi))
            radii += base * amplitude * np.cos(harmonic * angles + phase)
        radii = np.clip(radii, 0.52 * base, 1.42 * base)
        _polar_polygon(mask, (cx, cy), radii, angles + angle0)
    elif family == "hollow_polygon":
        sides = int(rng.integers(4, 9))
        outer = float(rng.uniform(0.21, 0.30) * size)
        _regular_polygon(mask, (cx, cy), outer, sides, angle0, 1)
        offset_theta = float(rng.uniform(-np.pi, np.pi))
        offset = float(outer * rng.uniform(0.02, 0.12))
        _regular_polygon(
            mask,
            (
                cx + offset * math.cos(offset_theta),
                cy + offset * math.sin(offset_theta),
            ),
            outer * float(rng.uniform(0.42, 0.68)),
            sides,
            angle0 + float(rng.uniform(-0.18, 0.18)),
            0,
        )
    elif family == "broken_ring":
        outer = int(rng.uniform(0.20, 0.30) * size)
        inner = int(outer * rng.uniform(0.48, 0.70))
        cv2.circle(mask, (round(cx), round(cy)), outer, 1, -1)
        cv2.circle(mask, (round(cx), round(cy)), inner, 0, -1)
        span = float(rng.uniform(20, 75))
        start = math.degrees(angle0) - span / 2.0
        wedge = np.zeros_like(mask)
        cv2.ellipse(
            wedge,
            (round(cx), round(cy)),
            (round(outer * 1.4), round(outer * 1.4)),
            0,
            start,
            start + span,
            1,
            -1,
        )
        mask[wedge > 0] = 0
    elif family == "serpentine":
        count = int(rng.integers(5, 9))
        length = float(rng.uniform(0.34, 0.55) * size)
        amplitude = float(rng.uniform(0.06, 0.14) * size)
        xs = np.linspace(-length / 2.0, length / 2.0, count)
        ys = amplitude * np.sin(
            np.linspace(0.0, float(rng.uniform(1.2, 2.4)) * np.pi, count)
            + float(rng.uniform(-np.pi, np.pi))
        )
        points = np.stack([xs, ys], axis=1)
        theta = angle0
        rotation = np.asarray(
            [[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]],
            dtype=np.float32,
        )
        points = (points @ rotation.T + np.asarray([cx, cy])).round().astype(np.int32)
        cv2.polylines(
            mask,
            [points],
            False,
            1,
            thickness=max(3, int(rng.uniform(0.035, 0.075) * size)),
            lineType=cv2.LINE_AA,
        )
        mask[:] = (mask > 0).astype(np.uint8)
    else:
        raise KeyError(family)
    return mask


def _draw_small_object(
    mask: np.ndarray,
    center: tuple[float, float],
    radius: float,
    rng: np.random.Generator,
    *,
    allow_hole: bool = False,
) -> None:
    kind = int(rng.integers(0, 4))
    if kind == 0:
        cv2.circle(mask, (round(center[0]), round(center[1])), round(radius), 1, -1)
    elif kind == 1:
        cv2.ellipse(
            mask,
            (round(center[0]), round(center[1])),
            (round(radius * rng.uniform(0.75, 1.25)), round(radius * rng.uniform(0.55, 0.95))),
            float(rng.uniform(-180, 180)),
            0,
            360,
            1,
            -1,
        )
    elif kind == 2:
        _rotated_rectangle(
            mask,
            center,
            (2.0 * radius * rng.uniform(1.0, 1.5), 2.0 * radius * rng.uniform(0.55, 1.0)),
            float(rng.uniform(-180, 180)),
        )
    else:
        _regular_polygon(
            mask,
            center,
            radius * rng.uniform(1.0, 1.35),
            int(rng.integers(3, 8)),
            float(rng.uniform(-np.pi, np.pi)),
        )
    if allow_hole and rng.random() < 0.45:
        cv2.circle(
            mask,
            (round(center[0]), round(center[1])),
            max(2, round(radius * rng.uniform(0.25, 0.48))),
            0,
            -1,
        )


def _draw_layout_mask(
    family: str,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    mask = np.zeros((size, size), dtype=np.uint8)
    margin = 0.08 * size
    if family == "random_array":
        rows = int(rng.integers(2, 5))
        cols = int(rng.integers(2, 5))
        pitch_x = float(rng.uniform(0.12, 0.22) * size)
        pitch_y = float(rng.uniform(0.12, 0.22) * size)
        radius = float(min(pitch_x, pitch_y) * rng.uniform(0.18, 0.34))
        origin_x = size / 2.0 - (cols - 1) * pitch_x / 2.0
        origin_y = size / 2.0 - (rows - 1) * pitch_y / 2.0
        for row in range(rows):
            for col in range(cols):
                center = (
                    origin_x + col * pitch_x + rng.uniform(-0.10, 0.10) * pitch_x,
                    origin_y + row * pitch_y + rng.uniform(-0.10, 0.10) * pitch_y,
                )
                _draw_small_object(mask, center, radius, rng)
    elif family in {"sparse_cluster", "dense_cluster"}:
        count = int(rng.integers(3, 8)) if family == "sparse_cluster" else int(rng.integers(10, 21))
        radius_range = (0.035, 0.075) if family == "sparse_cluster" else (0.018, 0.045)
        for _ in range(count):
            center = (
                float(rng.uniform(margin, size - margin)),
                float(rng.uniform(margin, size - margin)),
            )
            _draw_small_object(mask, center, float(rng.uniform(*radius_range) * size), rng)
    elif family == "multi_scale":
        center = (
            float(rng.uniform(0.35, 0.65) * size),
            float(rng.uniform(0.35, 0.65) * size),
        )
        _draw_small_object(mask, center, float(rng.uniform(0.13, 0.22) * size), rng, allow_hole=True)
        for _ in range(int(rng.integers(4, 10))):
            small_center = (
                float(rng.uniform(margin, size - margin)),
                float(rng.uniform(margin, size - margin)),
            )
            _draw_small_object(mask, small_center, float(rng.uniform(0.018, 0.055) * size), rng)
    elif family == "edge_truncated":
        side = int(rng.integers(0, 4))
        radius = float(rng.uniform(0.12, 0.24) * size)
        if side == 0:
            center = (-radius * rng.uniform(0.05, 0.55), rng.uniform(0.25, 0.75) * size)
        elif side == 1:
            center = (size + radius * rng.uniform(0.05, 0.55), rng.uniform(0.25, 0.75) * size)
        elif side == 2:
            center = (rng.uniform(0.25, 0.75) * size, -radius * rng.uniform(0.05, 0.55))
        else:
            center = (rng.uniform(0.25, 0.75) * size, size + radius * rng.uniform(0.05, 0.55))
        _draw_small_object(mask, center, radius, rng, allow_hole=True)
        for _ in range(int(rng.integers(2, 6))):
            inside = (
                float(rng.uniform(margin, size - margin)),
                float(rng.uniform(margin, size - margin)),
            )
            _draw_small_object(mask, inside, float(rng.uniform(0.025, 0.070) * size), rng)
    elif family == "staggered_array":
        rows = int(rng.integers(3, 6))
        cols = int(rng.integers(3, 6))
        pitch = float(rng.uniform(0.105, 0.16) * size)
        radius = pitch * float(rng.uniform(0.18, 0.30))
        origin_x = size / 2.0 - (cols - 1) * pitch / 2.0
        origin_y = size / 2.0 - (rows - 1) * pitch / 2.0
        for row in range(rows):
            for col in range(cols):
                center = (
                    origin_x + col * pitch + (0.45 * pitch if row % 2 else 0.0),
                    origin_y + row * pitch,
                )
                if margin <= center[0] <= size - margin:
                    _draw_small_object(mask, center, radius, rng)
    elif family == "mixed_holes":
        for _ in range(int(rng.integers(4, 10))):
            center = (
                float(rng.uniform(margin, size - margin)),
                float(rng.uniform(margin, size - margin)),
            )
            _draw_small_object(
                mask,
                center,
                float(rng.uniform(0.035, 0.085) * size),
                rng,
                allow_hole=True,
            )
    elif family == "nested_layout":
        cx, cy = float(size / 2), float(size / 2)
        outer = int(rng.uniform(0.20, 0.28) * size)
        cv2.circle(mask, (round(cx), round(cy)), outer, 1, -1)
        cv2.circle(mask, (round(cx), round(cy)), int(outer * rng.uniform(0.62, 0.78)), 0, -1)
        for index in range(int(rng.integers(4, 9))):
            theta = float(index * 2.0 * np.pi / 8.0 + rng.uniform(-0.18, 0.18))
            distance = float(rng.uniform(0.07, 0.16) * size)
            center = (
                cx + distance * math.cos(theta),
                cy + distance * math.sin(theta),
            )
            _draw_small_object(mask, center, float(rng.uniform(0.018, 0.045) * size), rng)
    else:
        raise KeyError(family)
    return mask


def generate_procedural_mask(
    role: str,
    family: str,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if family in BASIC_FAMILIES:
        mask = _draw_basic_mask(family, size, rng)
    elif family in FINE_FAMILIES:
        mask = _draw_fine_mask(family, size, rng)
    elif family in LAYOUT_FAMILIES:
        mask = _draw_layout_mask(family, size, rng)
    else:
        raise KeyError(f"{role}/{family}")
    mask = (mask > 0).astype(np.uint8)
    area_fraction = float(mask.mean())
    lower = 0.004 if role == "multi_object_layout" else 0.012
    upper = 0.72 if role == "multi_object_layout" else 0.58
    if not lower <= area_fraction <= upper:
        raise RuntimeError(f"{role}/{family}: implausible area fraction {area_fraction:.6f}")
    touches_border = bool(
        np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1])
    )
    if touches_border and family != "edge_truncated":
        raise RuntimeError(f"{role}/{family}: unexpectedly touches the image border")
    if family == "edge_truncated" and not touches_border:
        raise RuntimeError("edge_truncated geometry failed to touch the crop boundary")
    return mask


def _edge_sigma_for_role(role: str, rng: np.random.Generator) -> float:
    ranges = {
        "basic_geometry": (0.12, 0.28),
        "fine_noncircular": (0.18, 0.38),
        "multi_object_layout": (0.12, 0.32),
        "exposure_sequence": (0.15, 0.30),
        "boundary_fade_mixed": (0.18, 0.40),
        "identity_guard": (0.15, 0.30),
    }
    return float(rng.uniform(*ranges[role]))


def prepare_coverages(
    mask_highres: np.ndarray,
    *,
    final_size: int,
    supersample_factor: int,
    label_edge_sigma_px: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    expected = int(final_size) * int(supersample_factor)
    if mask_highres.shape != (expected, expected):
        raise ValueError(f"Expected {expected}x{expected} mask, got {mask_highres.shape}")
    exact = cv2.resize(
        mask_highres.astype(np.float32),
        (final_size, final_size),
        interpolation=cv2.INTER_AREA,
    )
    sigma_high = float(label_edge_sigma_px) * float(supersample_factor)
    soft_high = cv2.GaussianBlur(
        mask_highres.astype(np.float32),
        (0, 0),
        sigmaX=max(0.01, sigma_high),
        sigmaY=max(0.01, sigma_high),
        borderType=cv2.BORDER_REFLECT,
    )
    soft = cv2.resize(
        soft_high,
        (final_size, final_size),
        interpolation=cv2.INTER_AREA,
    )
    exact = np.clip(exact, 0.0, 1.0).astype(np.float32)
    soft = np.clip(soft, 0.0, 1.0).astype(np.float32)
    binary = (exact >= 0.5).astype(np.uint8)
    return exact, soft, binary


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
    matrix = cv2.getRotationMatrix2D(
        ((length - 1) / 2.0, (length - 1) / 2.0),
        angle_deg,
        1.0,
    )
    kernel = cv2.warpAffine(kernel, matrix, (length, length), flags=cv2.INTER_LINEAR)
    return kernel / max(float(kernel.sum()), 1e-12)


def _disk_kernel(diameter: int) -> np.ndarray:
    diameter = max(3, int(diameter) | 1)
    kernel = np.zeros((diameter, diameter), dtype=np.float32)
    cv2.circle(
        kernel,
        (diameter // 2, diameter // 2),
        max(1, diameter // 3),
        1.0,
        -1,
    )
    return kernel / max(float(kernel.sum()), 1e-12)


def _scene_parameters(
    role: str,
    geometry_index: int,
    rendering_index: int,
    rng: np.random.Generator,
) -> dict:
    if role == "exposure_sequence":
        level_index = rendering_index // 2
        polarity = "bright" if rendering_index % 2 == 0 else "dark"
        centers = (28.0, 50.0, 90.0, 150.0, 208.0)
        base_contrasts = (14.0, 24.0, 48.0, 70.0, 34.0)
        background = centers[level_index] + float(rng.uniform(-4.0, 4.0))
        magnitude = base_contrasts[level_index] * float(rng.uniform(0.78, 1.22))
        contrast_class = ("very_low", "low", "medium", "high", "low")[level_index]
    else:
        polarity = "bright" if rendering_index % 2 == 0 else "dark"
        level_index = (geometry_index * 3 + rendering_index) % len(EXPOSURE_LEVELS)
        ranges = (
            (18.0, 42.0),
            (42.0, 78.0),
            (78.0, 142.0),
            (142.0, 198.0),
            (198.0, 238.0),
        )
        background = float(rng.uniform(*ranges[level_index]))
        contrast_index = (geometry_index + 2 * rendering_index) % 4
        contrast_ranges = ((6.0, 18.0), (18.0, 38.0), (38.0, 80.0), (80.0, 145.0))
        contrast_class = ("very_low", "low", "medium", "high")[contrast_index]
        magnitude = float(rng.uniform(*contrast_ranges[contrast_index]))

    if polarity == "bright":
        maximum = max(4.0, 251.0 - background)
        magnitude = min(magnitude, maximum)
        signed_contrast = magnitude
    else:
        maximum = max(4.0, background - 4.0)
        magnitude = min(magnitude, maximum)
        signed_contrast = -magnitude
    return {
        "polarity": polarity,
        "exposure_level": EXPOSURE_LEVELS[level_index],
        "exposure_level_index": int(level_index),
        "background_level": float(background),
        "target_contrast": float(signed_contrast),
        "contrast_class": contrast_class,
    }


def _apply_gaussian(
    image: np.ndarray,
    rng: np.random.Generator,
    sigma_range: tuple[float, float],
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    sigma = float(rng.uniform(*sigma_range))
    meta["gaussian_sigma_px"] = sigma
    effects.append("gaussian_blur")
    return cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)


def _apply_anisotropic(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    sigma = float(rng.uniform(0.50, 1.90))
    ratio = float(rng.uniform(1.3, 2.8))
    angle = float(rng.uniform(-180, 180))
    kernel = _analytic_gaussian_kernel(19, sigma * ratio, sigma, angle)
    meta.update(
        {
            "anisotropic_sigma_px": sigma,
            "anisotropic_ratio": ratio,
            "anisotropic_angle_deg": angle,
        }
    )
    effects.append("anisotropic_blur")
    return cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REFLECT)


def _apply_read_noise(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
    sigma_range: tuple[float, float] = (0.5, 4.5),
) -> np.ndarray:
    sigma = float(rng.uniform(*sigma_range))
    meta["read_noise_sigma"] = sigma
    effects.append("read_noise")
    return image + rng.normal(0.0, sigma, image.shape).astype(np.float32)


def _apply_shot_read_noise(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    peak = float(rng.uniform(35.0, 180.0))
    read_sigma = float(rng.uniform(0.4, 3.0))
    normalized = np.clip(image / 255.0, 0.0, 1.0)
    noisy = rng.poisson(normalized * peak).astype(np.float32) * (255.0 / peak)
    noisy += rng.normal(0.0, read_sigma, image.shape).astype(np.float32)
    meta.update({"poisson_peak": peak, "read_noise_sigma": read_sigma})
    effects.append("shot_read_noise")
    return noisy


def _apply_illumination(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    size = image.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xn = (xx - size / 2.0) / (size / 2.0)
    yn = (yy - size / 2.0) / (size / 2.0)
    gx = float(rng.uniform(-18.0, 18.0))
    gy = float(rng.uniform(-18.0, 18.0))
    low = _low_frequency_field(size, rng) * float(rng.uniform(1.0, 5.0))
    meta["illumination_gradient_xy"] = [gx, gy]
    effects.append("uneven_illumination")
    return image + gx * xn + gy * yn + low


def _apply_gamma(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    gamma = float(rng.uniform(0.78, 1.28))
    meta["gamma"] = gamma
    effects.append("gamma")
    return np.power(np.clip(image / 255.0, 0.0, 1.0), gamma).astype(np.float32) * 255.0


def _apply_vignette(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    size = image.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xn = (xx - size / 2.0) / (size / 2.0)
    yn = (yy - size / 2.0) / (size / 2.0)
    strength = float(rng.uniform(0.04, 0.22))
    offset = float(rng.uniform(-0.22, 0.22))
    radius2 = (xn - offset) ** 2 + (yn + 0.5 * offset) ** 2
    factor = np.clip(1.0 - strength * radius2, 0.62, 1.08)
    meta["vignette_strength"] = strength
    effects.append("vignette")
    return image * factor


def _apply_quantization(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    step = int(rng.integers(2, 9))
    meta["quantization_step"] = step
    effects.append("quantization")
    return np.rint(image / step) * step


def _apply_asymmetric_halo(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    broad_sigma = float(rng.uniform(2.0, 5.0))
    broad = cv2.GaussianBlur(image, (0, 0), broad_sigma, borderType=cv2.BORDER_REFLECT)
    dx, dy = (float(value) for value in rng.uniform(-2.2, 2.2, size=2))
    shifted = cv2.warpAffine(
        broad,
        np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32),
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )
    strength = float(rng.uniform(0.20, 0.65))
    meta.update(
        {
            "asymmetric_halo_sigma_px": broad_sigma,
            "asymmetric_halo_shift_xy": [dx, dy],
            "asymmetric_halo_strength": strength,
        }
    )
    effects.append("asymmetric_halo")
    return image + strength * (shifted - broad)


def _apply_banding_texture(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    size = image.shape[0]
    axis = np.arange(size, dtype=np.float32)
    amplitude = float(rng.uniform(0.5, 3.5))
    period = float(rng.uniform(14.0, 80.0))
    phase = float(rng.uniform(-np.pi, np.pi))
    horizontal = bool(rng.integers(0, 2))
    band = amplitude * np.sin(2.0 * np.pi * axis / period + phase)
    texture = band[:, None] if horizontal else band[None, :]
    meta.update(
        {
            "banding_amplitude": amplitude,
            "banding_period_px": period,
            "banding_orientation": "horizontal" if horizontal else "vertical",
        }
    )
    effects.append("banding")
    return image + texture


def _apply_ghost(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    dx, dy = (float(value) for value in rng.uniform(-1.8, 1.8, size=2))
    alpha = float(rng.uniform(0.05, 0.20))
    ghost = cv2.warpAffine(
        image,
        np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32),
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )
    meta.update({"ghost_alpha": alpha, "ghost_shift_xy": [dx, dy]})
    effects.append("subpixel_ghost")
    return (1.0 - alpha) * image + alpha * ghost


def _apply_local_shadow(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    size = image.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx, cy = (float(value) for value in rng.uniform(0.15 * size, 0.85 * size, size=2))
    sigma = float(rng.uniform(18.0, 55.0))
    amplitude = float(rng.uniform(-15.0, 12.0))
    blob = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma**2)).astype(np.float32)
    meta.update(
        {
            "local_shadow_center_xy": [cx, cy],
            "local_shadow_sigma_px": sigma,
            "local_shadow_amplitude": amplitude,
        }
    )
    effects.append("local_shadow")
    return image + amplitude * blob


def _apply_saturation_texture(
    image: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    gain = float(rng.uniform(0.90, 1.15))
    offset = float(rng.uniform(-8.0, 8.0))
    texture_amplitude = float(rng.uniform(0.6, 3.0))
    texture = _low_frequency_field(image.shape[0], rng) * texture_amplitude
    meta.update(
        {
            "sensor_gain": gain,
            "sensor_offset": offset,
            "fixed_texture_amplitude": texture_amplitude,
        }
    )
    effects.extend(["gain_saturation", "fixed_pattern_texture"])
    return gain * image + offset + texture


def _apply_local_boundary_fade(
    image: np.ndarray,
    coverage_exact: np.ndarray,
    rng: np.random.Generator,
    effects: list[str],
    meta: dict,
) -> np.ndarray:
    binary = (coverage_exact >= 0.5).astype(np.uint8)
    edge = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, np.ones((3, 3), dtype=np.uint8))
    ys, xs = np.nonzero(edge)
    if len(xs) == 0:
        raise RuntimeError("Local boundary fade requires a non-empty contour")
    size = image.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    zone = np.zeros_like(image, dtype=np.float32)
    centers: list[list[float]] = []
    zone_count = int(rng.integers(1, 4))
    for _ in range(zone_count):
        chosen = int(rng.integers(0, len(xs)))
        cx, cy = float(xs[chosen]), float(ys[chosen])
        sigma = float(rng.uniform(7.0, 24.0))
        strength = float(rng.uniform(0.42, 0.88))
        blob = strength * np.exp(
            -((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma**2)
        ).astype(np.float32)
        zone = np.maximum(zone, blob)
        centers.append([cx, cy, sigma, strength])
    background_proxy = cv2.GaussianBlur(
        image,
        (0, 0),
        float(rng.uniform(4.0, 9.0)),
        borderType=cv2.BORDER_REFLECT,
    )
    meta["local_boundary_fade_zones"] = centers
    effects.append("local_boundary_fade")
    return (1.0 - zone) * image + zone * background_proxy


def apply_degradation(
    label_u8: np.ndarray,
    coverage_exact: np.ndarray,
    role: str,
    geometry_index: int,
    rendering_index: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict]:
    image = label_u8.astype(np.float32)
    effects: list[str] = []
    meta: dict = {}
    if role == "identity_guard":
        if rendering_index % 2 == 0:
            return label_u8.copy(), {
                "degradation_family": "identity_exact",
                "degradation_components": ["identity"],
                "identity_mode": "exact",
                "degradation_component_count": 1,
            }
        image = _apply_gaussian(image, rng, (0.10, 0.38), effects, meta)
        image = _apply_read_noise(image, rng, effects, meta, (0.20, 0.85))
        family = "identity_near"
        identity_mode = "near"
    elif role == "boundary_fade_mixed":
        image = _apply_local_boundary_fade(image, coverage_exact, rng, effects, meta)
        variant = rendering_index % 4
        if variant == 0:
            image = _apply_gaussian(image, rng, (0.55, 1.85), effects, meta)
            image = _apply_read_noise(image, rng, effects, meta, (0.8, 4.8))
            family = "local_fade_blur_noise"
        elif variant == 1:
            image = _apply_gaussian(image, rng, (0.40, 1.25), effects, meta)
            image = _apply_asymmetric_halo(image, rng, effects, meta)
            image = _apply_banding_texture(image, rng, effects, meta)
            family = "local_fade_halo_banding"
        elif variant == 2:
            image = _apply_anisotropic(image, rng, effects, meta)
            image = _apply_local_shadow(image, rng, effects, meta)
            image = _apply_read_noise(image, rng, effects, meta, (0.8, 4.5))
            family = "local_fade_shadow_noise"
        else:
            image = _apply_gaussian(image, rng, (0.45, 1.55), effects, meta)
            image = _apply_illumination(image, rng, effects, meta)
            image = _apply_asymmetric_halo(image, rng, effects, meta)
            image = _apply_shot_read_noise(image, rng, effects, meta)
            family = "local_fade_mixed_hard"
        identity_mode = "none"
    else:
        family = COMPOSITE_RECIPES[(geometry_index + rendering_index) % len(COMPOSITE_RECIPES)]
        if family == "blur_read_noise":
            image = _apply_gaussian(image, rng, (0.45, 2.35), effects, meta)
            image = _apply_read_noise(image, rng, effects, meta)
        elif family == "anisotropic_illumination":
            image = _apply_anisotropic(image, rng, effects, meta)
            image = _apply_illumination(image, rng, effects, meta)
            image = _apply_read_noise(image, rng, effects, meta, (0.5, 3.5))
        elif family == "motion_gamma_noise":
            image = _apply_gaussian(image, rng, (0.25, 0.90), effects, meta)
            length = int(rng.choice([3, 5, 7, 9]))
            angle = float(rng.uniform(-180, 180))
            image = cv2.filter2D(
                image,
                -1,
                _motion_kernel(length, angle),
                borderType=cv2.BORDER_REFLECT,
            )
            meta.update({"motion_length_px": length, "motion_angle_deg": angle})
            effects.append("short_motion_blur")
            image = _apply_gamma(image, rng, effects, meta)
            image = _apply_shot_read_noise(image, rng, effects, meta)
        elif family == "defocus_vignette_quantization":
            diameter = int(rng.choice([3, 5, 7, 9, 11]))
            image = cv2.filter2D(
                image,
                -1,
                _disk_kernel(diameter),
                borderType=cv2.BORDER_REFLECT,
            )
            meta["defocus_diameter_px"] = diameter
            effects.append("defocus")
            image = _apply_vignette(image, rng, effects, meta)
            image = _apply_read_noise(image, rng, effects, meta, (0.4, 2.8))
            image = _apply_quantization(image, rng, effects, meta)
        elif family == "asymmetric_halo_banding":
            image = _apply_gaussian(image, rng, (0.40, 1.40), effects, meta)
            image = _apply_asymmetric_halo(image, rng, effects, meta)
            image = _apply_banding_texture(image, rng, effects, meta)
            image = _apply_read_noise(image, rng, effects, meta, (0.4, 3.2))
        elif family == "ghost_shadow_noise":
            image = _apply_gaussian(image, rng, (0.35, 1.20), effects, meta)
            image = _apply_ghost(image, rng, effects, meta)
            image = _apply_local_shadow(image, rng, effects, meta)
            image = _apply_read_noise(image, rng, effects, meta, (0.5, 3.8))
        elif family == "blur_saturation_texture":
            image = _apply_gaussian(image, rng, (0.30, 1.40), effects, meta)
            image = _apply_saturation_texture(image, rng, effects, meta)
            image = _apply_quantization(image, rng, effects, meta)
        elif family == "mixed_microscopy":
            image = _apply_anisotropic(image, rng, effects, meta)
            image = _apply_local_shadow(image, rng, effects, meta)
            image = _apply_asymmetric_halo(image, rng, effects, meta)
            image = _apply_shot_read_noise(image, rng, effects, meta)
        else:
            raise KeyError(family)
        identity_mode = "none"

    mean_before_guard = float(np.mean(image))
    exposure_guard_shift = 0.0
    if mean_before_guard > 242.0:
        exposure_guard_shift = 242.0 - mean_before_guard
    elif mean_before_guard < 13.0:
        exposure_guard_shift = 13.0 - mean_before_guard
    image = image + exposure_guard_shift
    meta["exposure_guard_shift"] = exposure_guard_shift
    source = np.clip(np.rint(image), 0, 255).astype(np.uint8)
    if identity_mode == "near" and np.array_equal(source, label_u8):
        y = int(rng.integers(0, source.shape[0]))
        x = int(rng.integers(0, source.shape[1]))
        source[y, x] = np.uint8(1 if source[y, x] == 0 else source[y, x] - 1)
    return source, {
        "degradation_family": family,
        "degradation_components": effects,
        "identity_mode": identity_mode,
        "degradation_component_count": len(effects),
        **meta,
    }


def render_pair(
    coverage_exact: np.ndarray,
    coverage_soft: np.ndarray,
    rng: np.random.Generator,
    role: str,
    geometry_index: int,
    rendering_index: int,
) -> tuple[np.ndarray, np.ndarray, dict]:
    size = int(coverage_exact.shape[0])
    scene = _scene_parameters(role, geometry_index, rendering_index, rng)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xn = (xx - size / 2.0) / (size / 2.0)
    yn = (yy - size / 2.0) / (size / 2.0)
    background_texture = _low_frequency_field(size, rng) * float(rng.uniform(0.0, 2.4))
    plane_x = float(rng.uniform(-3.5, 3.5))
    plane_y = float(rng.uniform(-3.5, 3.5))
    truth = (
        float(scene["background_level"])
        + background_texture
        + plane_x * xn
        + plane_y * yn
        + float(scene["target_contrast"]) * coverage_soft
    )
    label = np.clip(np.rint(truth), 0, 255).astype(np.uint8)
    source, degradation = apply_degradation(
        label,
        coverage_exact,
        role,
        geometry_index,
        rendering_index,
        rng,
    )
    mask = coverage_exact >= 0.5
    foreground_count = int(np.count_nonzero(mask))
    background_count = int(mask.size - foreground_count)
    if foreground_count == 0 or background_count == 0:
        raise RuntimeError("Rendered geometry has no foreground or no background")
    target_measured_contrast = float(label[mask].mean() - label[~mask].mean())
    source_measured_contrast = float(source[mask].mean() - source[~mask].mean())
    difference = np.abs(source.astype(np.int16) - label.astype(np.int16))
    return source, label, {
        **scene,
        **degradation,
        "target_plane_gradient_xy": [plane_x, plane_y],
        "target_mean": float(label.mean()),
        "source_mean": float(source.mean()),
        "target_std": float(label.std()),
        "source_std": float(source.std()),
        "source_black_fraction": float(np.mean(source <= 1)),
        "source_white_fraction": float(np.mean(source >= 254)),
        "source_clipped_fraction": float(np.mean((source <= 1) | (source >= 254))),
        "target_p01_p99": [
            float(np.percentile(label, 1)),
            float(np.percentile(label, 99)),
        ],
        "source_p01_p99": [
            float(np.percentile(source, 1)),
            float(np.percentile(source, 99)),
        ],
        "target_measured_contrast": target_measured_contrast,
        "source_measured_contrast": source_measured_contrast,
        "source_target_mae": float(difference.mean()),
        "source_target_max_abs": int(difference.max()),
    }


def compute_geometry(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask_u8 = (mask > 0).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    centerline = cv2.morphologyEx(mask_u8, cv2.MORPH_GRADIENT, kernel)
    centerline = (centerline > 0).astype(np.uint8) * 255
    boundary = cv2.dilate(centerline, kernel, iterations=1)
    distance = cv2.distanceTransform(
        (boundary == 0).astype(np.uint8),
        cv2.DIST_L2,
        3,
    ).astype(np.float32)
    return boundary, centerline, distance


def _write_geometry(
    package_dir: Path,
    relative_stem: Path,
    geometry_arrays: tuple[np.ndarray, np.ndarray, np.ndarray],
    binary_mask: np.ndarray,
    coverage_exact: np.ndarray,
    coverage_soft: np.ndarray,
) -> dict[str, str]:
    boundary, centerline, distance = geometry_arrays
    boundary_rel = Path("geom") / "boundary" / relative_stem.with_suffix(".bmp")
    centerline_rel = Path("geom") / "centerline" / relative_stem.with_suffix(".bmp")
    distance_rel = Path("geom") / "distance" / relative_stem.with_suffix(".npy")
    mask_rel = Path("mask") / relative_stem.with_suffix(".bmp")
    mask_aa_rel = Path("mask_aa") / relative_stem.with_suffix(".bmp")
    mask_soft_rel = Path("mask_soft") / relative_stem.with_suffix(".bmp")
    _write_image(package_dir / boundary_rel, boundary)
    _write_image(package_dir / centerline_rel, centerline)
    _write_image(package_dir / mask_rel, binary_mask * 255)
    _write_image(package_dir / mask_aa_rel, np.rint(coverage_exact * 255.0))
    _write_image(package_dir / mask_soft_rel, np.rint(coverage_soft * 255.0))
    distance_path = package_dir / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance, allow_pickle=False)
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
        "geometry_mask": mask_rel.as_posix(),
        "geometry_mask_aa": mask_aa_rel.as_posix(),
        "geometry_mask_soft": mask_soft_rel.as_posix(),
    }


def _assign_splits(profile: str) -> dict[tuple[str, int], str]:
    plan = build_plan(profile)
    result: dict[tuple[str, int], str] = {}
    base_seed = int(CONFIG["dataset"]["split_seed"])
    for role_index, role in enumerate(ROLE_ORDER):
        geometry_count = int(plan["role_geometry_counts"][role])
        counts = plan["role_split_geometry_counts"][role]
        rng = np.random.default_rng(base_seed + role_index * 1009)
        order = rng.permutation(geometry_count).tolist()
        n_val = int(counts["validation"])
        n_test = int(counts["internal_test"])
        val_set = set(order[:n_val])
        test_set = set(order[n_val : n_val + n_test])
        for geometry_index in range(geometry_count):
            split = (
                "validation"
                if geometry_index in val_set
                else "internal_test"
                if geometry_index in test_set
                else "train"
            )
            result[(role, geometry_index)] = split
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
        raise RuntimeError(f"External or parent path is forbidden in R75-v2: {value}")
    if not path.parts or path.parts[0].lower() != expected_prefix.lower():
        raise RuntimeError(f"Expected {expected_prefix}/ relative path, got: {value}")


def assert_record_provenance(records: list[dict]) -> None:
    approved_paths = {
        "package_src": "src",
        "package_lbl": "lbl",
        "geometry_boundary": "geom",
        "geometry_centerline": "geom",
        "geometry_distance": "geom",
        "geometry_mask": "mask",
        "geometry_mask_aa": "mask_aa",
        "geometry_mask_soft": "mask_soft",
    }
    for row_index, record in enumerate(records):
        for dotted_key, value in _flatten_keys(record):
            leaf = dotted_key.rsplit(".", 1)[-1].split("[", 1)[0].lower()
            if leaf in FORBIDDEN_RECORD_KEYS:
                raise RuntimeError(f"Forbidden source key in record {row_index}: {dotted_key}")
            if leaf in approved_paths:
                continue
            if isinstance(value, str):
                lowered = value.lower()
                hit = next((token for token in FORBIDDEN_VALUE_TOKENS if token in lowered), None)
                if hit is not None:
                    raise RuntimeError(
                        f"Forbidden source token '{hit}' in record {row_index}: {dotted_key}"
                    )
        provenance = record.get("provenance", {})
        if (
            provenance.get("kind") != PROVENANCE_KIND
            or provenance.get("generator") != GENERATOR_NAME
        ):
            raise RuntimeError(f"Record {row_index} has unapproved provenance: {provenance}")
        for key, prefix in approved_paths.items():
            _assert_safe_relative_path(record[key], prefix)


def audit_package(
    package_dir: Path,
    manifest: dict,
    *,
    verify_files: bool = True,
) -> dict:
    package_dir = Path(package_dir).resolve()
    records = list(manifest.get("pairs", []))
    assert_record_provenance(records)
    plan = build_plan(str(manifest.get("profile")))
    if int(manifest.get("total_pairs", -1)) != len(records):
        raise RuntimeError("Manifest total_pairs does not match pair records")
    if len(records) != int(plan["expected_pairs"]):
        raise RuntimeError(f"Expected {plan['expected_pairs']} records, found {len(records)}")

    geometry_splits: dict[str, set[str]] = defaultdict(set)
    split_counts = Counter()
    role_counts = Counter()
    role_split_counts: dict[str, Counter] = defaultdict(Counter)
    polarity_counts = Counter()
    family_counts = Counter()
    degradation_counts = Counter()
    exposure_counts = Counter()
    identity_counts = Counter()
    component_counts: list[int] = []
    anti_alias_edge_counts: list[int] = []
    source_means: list[float] = []
    source_stds: list[float] = []
    source_clipped_fractions: list[float] = []
    target_contrasts: list[float] = []
    source_contrasts: list[float] = []
    missing: list[str] = []
    exact_identity_records: list[dict] = []

    required_file_keys = (
        "package_src",
        "package_lbl",
        "geometry_boundary",
        "geometry_centerline",
        "geometry_distance",
        "geometry_mask",
        "geometry_mask_aa",
        "geometry_mask_soft",
    )
    for record in records:
        geometry_splits[str(record["geometry_id"])].add(str(record["split"]))
        split_counts[str(record["split"])] += 1
        role_counts[str(record["training_role"])] += 1
        role_split_counts[str(record["training_role"])][str(record["split"])] += 1
        polarity_counts[str(record["polarity"])] += 1
        family_counts[str(record["shape_family"])] += 1
        degradation_counts[str(record["degradation_family"])] += 1
        exposure_counts[str(record["exposure_level"])] += 1
        identity_counts[str(record["identity_mode"])] += 1
        component_counts.append(int(record["degradation_component_count"]))
        anti_alias_edge_counts.append(int(record["anti_alias_edge_pixel_count"]))
        source_means.append(float(record["source_mean"]))
        source_stds.append(float(record["source_std"]))
        source_clipped_fractions.append(float(record["source_clipped_fraction"]))
        target_contrasts.append(float(record["target_measured_contrast"]))
        source_contrasts.append(float(record["source_measured_contrast"]))
        if record["identity_mode"] == "exact":
            exact_identity_records.append(record)
        if verify_files:
            for key in required_file_keys:
                if not (package_dir / record[key]).is_file():
                    missing.append(record[key])

    leaked = sorted(group for group, splits in geometry_splits.items() if len(splits) != 1)
    if leaked:
        raise RuntimeError(f"Geometry leakage across splits: {leaked[:5]}")
    if missing:
        raise RuntimeError(f"Missing {len(missing)} generated files; first={missing[0]}")
    if dict(split_counts) != plan["pair_split_counts"]:
        raise RuntimeError(f"Split counts changed: {dict(split_counts)} vs {plan['pair_split_counts']}")
    if dict(role_counts) != plan["role_pair_counts"]:
        raise RuntimeError(f"Role counts changed: {dict(role_counts)} vs {plan['role_pair_counts']}")
    for role in ROLE_ORDER:
        if dict(role_split_counts[role]) != plan["role_split_pair_counts"][role]:
            raise RuntimeError(f"Role/split counts changed for {role}: {dict(role_split_counts[role])}")
    if set(exposure_counts) != set(EXPOSURE_LEVELS):
        raise RuntimeError(f"Exposure coverage is incomplete: {dict(exposure_counts)}")
    expected_factor = int(CONFIG["dataset"]["label_supersample_factor"])
    if any(int(row.get("label_supersample_factor", 0)) != expected_factor for row in records):
        raise RuntimeError("Label supersampling factor is missing or inconsistent")
    if not anti_alias_edge_counts or min(anti_alias_edge_counts) <= 0:
        raise RuntimeError("At least one exact geometry lacks anti-aliased edge pixels")

    expected_identity_pairs = int(plan["role_pair_counts"]["identity_guard"])
    if identity_counts["exact"] != expected_identity_pairs // 2:
        raise RuntimeError(f"Unexpected exact identity count: {dict(identity_counts)}")
    if identity_counts["near"] != expected_identity_pairs // 2:
        raise RuntimeError(f"Unexpected near-identity count: {dict(identity_counts)}")
    non_identity_components = [
        int(row["degradation_component_count"])
        for row in records
        if row["identity_mode"] == "none"
    ]
    if min(non_identity_components) < 2 or max(non_identity_components) > 5:
        raise RuntimeError(
            f"Composite degradation count out of range: {min(non_identity_components)}..{max(non_identity_components)}"
        )
    boundary_rows = [row for row in records if row["training_role"] == "boundary_fade_mixed"]
    if not all("local_boundary_fade" in row["degradation_components"] for row in boundary_rows):
        raise RuntimeError("Boundary-fade role contains a row without local boundary fade")

    dark_on_dark_count = sum(
        1
        for row in records
        if row["polarity"] == "dark" and float(row["background_level"]) < 70.0
    )
    very_low_contrast_count = sum(
        1 for value in target_contrasts if abs(float(value)) <= 20.0
    )
    if dark_on_dark_count <= 0:
        raise RuntimeError("No dark-object/dark-background examples were generated")
    if very_low_contrast_count <= 0:
        raise RuntimeError("No very-low-contrast examples were generated")
    if min(source_means) >= 50.0 or max(source_means) <= 185.0:
        raise RuntimeError(
            f"Exposure span is too narrow: source mean {min(source_means):.2f}..{max(source_means):.2f}"
        )
    if min(source_stds) <= 0.25:
        raise RuntimeError(f"At least one source image is effectively flat: std={min(source_stds):.6f}")
    if max(source_clipped_fractions) >= 0.90:
        raise RuntimeError(
            "At least one source image lost nearly all information to clipping: "
            f"fraction={max(source_clipped_fractions):.6f}"
        )

    exact_identity_max_abs = 0
    if verify_files:
        for record in exact_identity_records:
            source = _read_gray(package_dir / record["package_src"])
            label = _read_gray(package_dir / record["package_lbl"])
            exact_identity_max_abs = max(
                exact_identity_max_abs,
                int(np.abs(source.astype(np.int16) - label.astype(np.int16)).max()),
            )
        if exact_identity_max_abs != 0:
            raise RuntimeError(f"Exact identity pairs drift by {exact_identity_max_abs} gray levels")

    psf = manifest.get("analytic_psf", {})
    if (
        psf.get("source_kind") != "analytic_gaussian_only"
        or psf.get("measured_data_used") is not False
    ):
        raise RuntimeError("R75-v2 requires a fully analytic PSF bank")
    if verify_files:
        psf_path = package_dir / str(psf.get("relative_path", ""))
        if not psf_path.is_file() or _sha256(psf_path) != psf.get("sha256"):
            raise RuntimeError("Analytic PSF bank is missing or changed")

    def _quantiles(values: list[float]) -> dict:
        return {
            "min": float(np.min(values)),
            "p01": float(np.percentile(values, 1)),
            "p10": float(np.percentile(values, 10)),
            "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90)),
            "p99": float(np.percentile(values, 99)),
            "max": float(np.max(values)),
        }

    return {
        "passed": True,
        "experiment_id": CONFIG["experiment_id"],
        "profile": manifest.get("profile"),
        "total_pairs": len(records),
        "geometry_count": len(geometry_splits),
        "split_counts": dict(sorted(split_counts.items())),
        "training_role_counts": dict(sorted(role_counts.items())),
        "training_role_split_counts": {
            role: dict(sorted(counts.items())) for role, counts in sorted(role_split_counts.items())
        },
        "polarity_counts": dict(sorted(polarity_counts.items())),
        "shape_family_counts": dict(sorted(family_counts.items())),
        "degradation_family_counts": dict(sorted(degradation_counts.items())),
        "exposure_level_counts": dict(sorted(exposure_counts.items())),
        "identity_mode_counts": dict(sorted(identity_counts.items())),
        "exact_identity_max_abs_difference": exact_identity_max_abs,
        "dark_object_dark_background_count": dark_on_dark_count,
        "very_low_contrast_count": very_low_contrast_count,
        "composite_component_count_min_non_identity": min(non_identity_components),
        "composite_component_count_max_non_identity": max(non_identity_components),
        "source_mean_distribution": _quantiles(source_means),
        "source_std_distribution": _quantiles(source_stds),
        "source_clipped_fraction_distribution": _quantiles(source_clipped_fractions),
        "target_measured_contrast_distribution": _quantiles(target_contrasts),
        "source_measured_contrast_distribution": _quantiles(source_contrasts),
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
        "pseudo_labels_used": False,
        "fitted_or_measured_psf_used": False,
        "required_provenance_kind": PROVENANCE_KIND,
        "required_generator": GENERATOR_NAME,
    }


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
        "split_type": "r75v2_geometry_grouped_train_validation_internal_test",
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


def _tile(
    image: np.ndarray,
    size: int,
) -> np.ndarray:
    return cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)


def _write_overview(package_dir: Path, records: list[dict], profile: str) -> Path:
    selected = [
        next(
            row
            for row in records
            if row["training_role"] == role
            and row["split"] == "train"
            and row["polarity"] == "bright"
        )
        for role in ROLE_ORDER
    ]
    tile_size = 176
    caption_height = 32
    rows = (
        ("package_src", "Raw"),
        ("package_lbl", "Truth"),
        ("geometry_mask", "Exact contour"),
        ("difference", "|Raw-Truth| x4"),
    )
    canvas = np.full(
        (len(rows) * (tile_size + caption_height), len(selected) * tile_size),
        245,
        dtype=np.uint8,
    )
    for column, record in enumerate(selected):
        source = _read_gray(package_dir / record["package_src"])
        label = _read_gray(package_dir / record["package_lbl"])
        for row_index, (key, row_label) in enumerate(rows):
            if key == "difference":
                image = np.clip(
                    np.abs(source.astype(np.int16) - label.astype(np.int16)) * 4,
                    0,
                    255,
                ).astype(np.uint8)
            else:
                image = _read_gray(package_dir / record[key])
            y0 = row_index * (tile_size + caption_height)
            x0 = column * tile_size
            canvas[y0 : y0 + tile_size, x0 : x0 + tile_size] = _tile(image, tile_size)
            caption = (
                f"{record['training_role']}"
                if row_index == 0
                else row_label
            )
            cv2.putText(
                canvas,
                caption[:25],
                (x0 + 4, y0 + tile_size + 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.43,
                25,
                1,
                cv2.LINE_AA,
            )
    path = package_dir / "preview_roles.png"
    _write_image(path, canvas)
    if profile in {"pilot", "formal"}:
        _write_image(REPORT_ROOT / "figures" / f"r75v2_{profile}_role_preview.png", canvas)
    return path


def _write_exposure_preview(package_dir: Path, records: list[dict], profile: str) -> Path:
    chosen_geometry = next(
        row["geometry_id"]
        for row in records
        if row["training_role"] == "exposure_sequence" and row["split"] == "train"
    )
    selected = sorted(
        [row for row in records if row["geometry_id"] == chosen_geometry],
        key=lambda row: int(row["rendering_index"]),
    )
    by_key = {
        (int(row["exposure_level_index"]), str(row["polarity"])): row for row in selected
    }
    tile_size = 164
    caption_height = 28
    row_specs = (
        ("bright", "package_src", "Bright raw"),
        ("bright", "package_lbl", "Bright truth"),
        ("dark", "package_src", "Dark raw"),
        ("dark", "package_lbl", "Dark truth"),
    )
    canvas = np.full(
        (len(row_specs) * (tile_size + caption_height), 5 * tile_size),
        245,
        dtype=np.uint8,
    )
    for column, level in enumerate(range(5)):
        for row_index, (polarity, key, row_label) in enumerate(row_specs):
            record = by_key[(level, polarity)]
            image = _read_gray(package_dir / record[key])
            y0 = row_index * (tile_size + caption_height)
            x0 = column * tile_size
            canvas[y0 : y0 + tile_size, x0 : x0 + tile_size] = _tile(image, tile_size)
            caption = EXPOSURE_LEVELS[level] if row_index == 0 else row_label
            cv2.putText(
                canvas,
                caption,
                (x0 + 4, y0 + tile_size + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.44,
                25,
                1,
                cv2.LINE_AA,
            )
    path = package_dir / "preview_exposure_sequence.png"
    _write_image(path, canvas)
    if profile in {"pilot", "formal"}:
        _write_image(REPORT_ROOT / "figures" / f"r75v2_{profile}_exposure_preview.png", canvas)
    return path


def _write_identity_preview(package_dir: Path, records: list[dict], profile: str) -> Path:
    exact = next(
        row
        for row in records
        if row["training_role"] == "identity_guard"
        and row["identity_mode"] == "exact"
        and row["split"] == "train"
    )
    near = next(
        row
        for row in records
        if row["training_role"] == "identity_guard"
        and row["identity_mode"] == "near"
        and row["split"] == "train"
    )
    selected = [exact, near]
    tile_size = 220
    caption_height = 30
    canvas = np.full((3 * (tile_size + caption_height), 2 * tile_size), 245, dtype=np.uint8)
    for column, record in enumerate(selected):
        source = _read_gray(package_dir / record["package_src"])
        label = _read_gray(package_dir / record["package_lbl"])
        images = (
            (source, f"{record['identity_mode']} raw"),
            (label, "truth"),
            (
                np.clip(
                    np.abs(source.astype(np.int16) - label.astype(np.int16)) * 16,
                    0,
                    255,
                ).astype(np.uint8),
                "|difference| x16",
            ),
        )
        for row_index, (image, caption) in enumerate(images):
            y0 = row_index * (tile_size + caption_height)
            x0 = column * tile_size
            canvas[y0 : y0 + tile_size, x0 : x0 + tile_size] = _tile(image, tile_size)
            cv2.putText(
                canvas,
                caption,
                (x0 + 5, y0 + tile_size + 21),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                25,
                1,
                cv2.LINE_AA,
            )
    path = package_dir / "preview_identity_guard.png"
    _write_image(path, canvas)
    if profile in {"pilot", "formal"}:
        _write_image(REPORT_ROOT / "figures" / f"r75v2_{profile}_identity_preview.png", canvas)
    return path


def _write_shape_atlas(package_dir: Path, records: list[dict], profile: str) -> Path:
    family_order = []
    for family in BASIC_FAMILIES + FINE_FAMILIES + LAYOUT_FAMILIES:
        if family not in family_order and any(row["shape_family"] == family for row in records):
            family_order.append(family)
    columns = 7
    rows = int(math.ceil(len(family_order) / columns))
    tile_size = 132
    caption_height = 28
    canvas = np.full(
        (rows * (tile_size + caption_height), columns * tile_size),
        245,
        dtype=np.uint8,
    )
    for index, family in enumerate(family_order):
        record = next(row for row in records if row["shape_family"] == family)
        image = _read_gray(package_dir / record["geometry_mask"])
        row_index, column = divmod(index, columns)
        y0 = row_index * (tile_size + caption_height)
        x0 = column * tile_size
        canvas[y0 : y0 + tile_size, x0 : x0 + tile_size] = _tile(image, tile_size)
        cv2.putText(
            canvas,
            family[:20],
            (x0 + 4, y0 + tile_size + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            25,
            1,
            cv2.LINE_AA,
        )
    path = package_dir / "preview_shape_atlas.png"
    _write_image(path, canvas)
    if profile in {"pilot", "formal"}:
        _write_image(REPORT_ROOT / "figures" / f"r75v2_{profile}_shape_atlas.png", canvas)
    return path


def _write_antialias_zoom(package_dir: Path, records: list[dict], profile: str) -> Path:
    preferred_families = (
        "fourier_lobed",
        "deep_notches",
        "thin_neck",
        "crescent",
        "ellipse",
        "rounded_rectangle",
    )
    selected = []
    for family in preferred_families:
        match = next(
            (
                row
                for row in records
                if row["shape_family"] == family and row["polarity"] == "bright"
            ),
            None,
        )
        if match is not None:
            selected.append(match)
        if len(selected) == 4:
            break
    if len(selected) < 4:
        raise RuntimeError("Need at least four distinct generated shapes for anti-alias QA")
    crop_size = 24
    zoom = 10
    tile_size = crop_size * zoom
    caption_height = 36
    row_keys = (
        ("geometry_mask", "Binary contour"),
        ("geometry_mask_aa", "8x area coverage"),
        ("geometry_mask_soft", "8x mild band-limit"),
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
            crop = image[y0 : y0 + crop_size, x0 : x0 + crop_size]
            enlarged = cv2.resize(crop, (tile_size, tile_size), interpolation=cv2.INTER_NEAREST)
            target_y = row_index * (tile_size + caption_height)
            target_x = column * tile_size
            canvas[target_y : target_y + tile_size, target_x : target_x + tile_size] = enlarged
            caption = record["shape_family"] if row_index == 0 else row_label
            cv2.putText(
                canvas,
                caption,
                (target_x + 5, target_y + tile_size + 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.44,
                25,
                1,
                cv2.LINE_AA,
            )
    path = package_dir / "antialias_edge_zoom.png"
    _write_image(path, canvas)
    if profile in {"pilot", "formal"}:
        _write_image(REPORT_ROOT / "figures" / f"r75v2_{profile}_antialias_zoom.png", canvas)
    return path


def build_package(
    profile: str,
    output_root: Path = DATA_ROOT,
    *,
    force: bool = False,
) -> tuple[Path, dict, dict]:
    output_root = Path(output_root).resolve()
    package_dir = output_root / f"r75v2_{profile}_diverse_primitives"
    manifest_path = package_dir / "manifest.json"
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("profile") != profile
            or manifest.get("generator_version") != GENERATOR_NAME
        ):
            raise RuntimeError(f"Profile/generator mismatch in existing package: {manifest_path}")
        audit = audit_package(package_dir, manifest)
        _json_dump(package_dir / "source_audit.json", audit)
        return package_dir, manifest, audit
    if force:
        _safe_clean_package(package_dir, output_root)

    plan = build_plan(profile)
    package_dir.mkdir(parents=True, exist_ok=True)
    _, psf_meta = ensure_analytic_psf(package_dir)
    split_by_geometry = _assign_splits(profile)
    image_size = int(plan["image_size"])
    supersample_factor = int(plan["label_supersample_factor"])
    drawing_size = int(plan["drawing_size"])
    master_seed = int(CONFIG["dataset"]["split_seed"]) + 75_200_000
    records: list[dict] = []
    content_digest = hashlib.sha256()

    for role_index, role in enumerate(ROLE_ORDER):
        families = ROLE_FAMILIES[role]
        geometry_count = int(plan["role_geometry_counts"][role])
        renderings = int(CONFIG["dataset"]["roles"][role]["renderings_per_geometry"])
        for geometry_index in range(geometry_count):
            family = families[geometry_index % len(families)]
            geometry_seed = master_seed + role_index * 10_000_000 + geometry_index * 100
            attempt = 0
            while True:
                geometry_rng = np.random.default_rng(geometry_seed + attempt)
                try:
                    mask_highres = generate_procedural_mask(
                        role,
                        family,
                        drawing_size,
                        geometry_rng,
                    )
                    label_edge_sigma_px = _edge_sigma_for_role(role, geometry_rng)
                    coverage_exact, coverage_soft, binary_mask = prepare_coverages(
                        mask_highres,
                        final_size=image_size,
                        supersample_factor=supersample_factor,
                        label_edge_sigma_px=label_edge_sigma_px,
                    )
                    break
                except RuntimeError:
                    attempt += 1
                    if attempt >= 100:
                        raise
            del mask_highres
            geometry_arrays = compute_geometry(binary_mask)
            geometry_id = (
                f"{role}:{family}:g{geometry_index:05d}:s{geometry_seed + attempt}"
            )
            split = split_by_geometry[(role, geometry_index)]
            anti_alias_edge_pixels = int(
                np.count_nonzero((coverage_exact > 0.0) & (coverage_exact < 1.0))
            )
            if anti_alias_edge_pixels <= 0:
                raise RuntimeError(f"{geometry_id} has no anti-aliased boundary pixels")
            touches_border = bool(
                np.any(binary_mask[0])
                or np.any(binary_mask[-1])
                or np.any(binary_mask[:, 0])
                or np.any(binary_mask[:, -1])
            )

            for rendering_index in range(renderings):
                rendering_seed = geometry_seed + 50_000 + rendering_index
                rng = np.random.default_rng(rendering_seed)
                source, label, rendering = render_pair(
                    coverage_exact,
                    coverage_soft,
                    rng,
                    role,
                    geometry_index,
                    rendering_index,
                )
                polarity = str(rendering["polarity"])
                filename = f"g{geometry_index:05d}_r{rendering_index:02d}.bmp"
                relative_stem = Path(STAGE_NAME) / role / family / polarity / filename
                src_rel = Path("src") / relative_stem
                lbl_rel = Path("lbl") / relative_stem
                _write_image(package_dir / src_rel, source)
                _write_image(package_dir / lbl_rel, label)
                geometry_paths = _write_geometry(
                    package_dir,
                    relative_stem,
                    geometry_arrays,
                    binary_mask,
                    coverage_exact,
                    coverage_soft,
                )
                content_digest.update(source.tobytes())
                content_digest.update(label.tobytes())
                content_digest.update(np.rint(coverage_exact * 255.0).astype(np.uint8).tobytes())
                records.append(
                    {
                        "pair_id": f"{role}/{family}/g{geometry_index:05d}/r{rendering_index:02d}",
                        "training_role": role,
                        "role": "pure_procedural_synthetic",
                        "feature": family,
                        "shape_family": family,
                        "geometry_id": geometry_id,
                        "split": split,
                        "polarity": polarity,
                        "geometry_index": geometry_index,
                        "rendering_index": rendering_index,
                        "bias_px": 0.0,
                        "geometry_seed": geometry_seed + attempt,
                        "rendering_seed": rendering_seed,
                        "generation_attempt": attempt,
                        "geometry_touches_crop_border": touches_border,
                        "label_supersample_factor": supersample_factor,
                        "label_downsample_method": "cv2.INTER_AREA",
                        "label_edge_sigma_px": label_edge_sigma_px,
                        "anti_alias_edge_pixel_count": anti_alias_edge_pixels,
                        "package_src": src_rel.as_posix(),
                        "package_lbl": lbl_rel.as_posix(),
                        "provenance": {
                            "kind": PROVENANCE_KIND,
                            "generator": GENERATOR_NAME,
                            "external_pixels": False,
                            "measured_geometry": False,
                            "pseudo_label": False,
                        },
                        **rendering,
                        **geometry_paths,
                    }
                )

    records.sort(key=lambda row: row["package_src"])
    split_dir, split_meta = _write_fixed_split(package_dir, records)
    overview_path = _write_overview(package_dir, records, profile)
    exposure_path = _write_exposure_preview(package_dir, records, profile)
    identity_path = _write_identity_preview(package_dir, records, profile)
    shape_atlas_path = _write_shape_atlas(package_dir, records, profile)
    antialias_path = _write_antialias_zoom(package_dir, records, profile)
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
        "label_edge_policy": CONFIG["dataset"]["label_edge_policy"],
        "training_roles": list(ROLE_ORDER),
        "role_families": {role: list(ROLE_FAMILIES[role]) for role in ROLE_ORDER},
        "degradation_families": list(COMPOSITE_RECIPES)
        + [
            "local_fade_blur_noise",
            "local_fade_halo_banding",
            "local_fade_shadow_noise",
            "local_fade_mixed_hard",
            "identity_exact",
            "identity_near",
        ],
        "exposure_levels": list(EXPOSURE_LEVELS),
        "total_pairs": len(records),
        "geometry_count": len({row["geometry_id"] for row in records}),
        "plan": plan,
        "training_data_contract": {
            "procedural_pixels_only": True,
            "analytic_and_stochastic_primitives_only": True,
            "legacy_pairs_imported": False,
            "measured_sample_templates_imported": False,
            "radius_lists_imported": False,
            "checkpoint_outputs_imported": False,
            "pseudo_labels_imported": False,
            "target_boundary_bias_px": 0.0,
            "exact_geometry_retained_for_contour_loss": True,
            "label_drawn_at_high_resolution": True,
            "label_supersample_factor": supersample_factor,
            "label_downsample_method": "cv2.INTER_AREA",
            "mild_label_band_limit_recorded_per_geometry": True,
            "polarity_decoupled_from_background_exposure": True,
            "geometry_grouped_split": True,
        },
        "analytic_psf": psf_meta,
        "content_sha256": content_digest.hexdigest(),
        "fixed_split_dir": split_dir.relative_to(package_dir).as_posix(),
        "fixed_split": split_meta,
        "preview_roles": overview_path.relative_to(package_dir).as_posix(),
        "preview_exposure_sequence": exposure_path.relative_to(package_dir).as_posix(),
        "preview_identity_guard": identity_path.relative_to(package_dir).as_posix(),
        "preview_shape_atlas": shape_atlas_path.relative_to(package_dir).as_posix(),
        "antialias_zoom": antialias_path.relative_to(package_dir).as_posix(),
        "pairs": records,
    }
    audit = audit_package(package_dir, manifest)
    _json_dump(manifest_path, manifest)
    _json_dump(package_dir / "source_audit.json", audit)
    return package_dir, manifest, audit


def write_formal_plan() -> Path:
    payload = {
        "experiment_id": CONFIG["experiment_id"],
        "status": "ready_to_generate",
        "formal_dataset": build_plan("formal"),
        "formal_training": CONFIG["training"],
        "source_isolation": CONFIG["source_isolation"],
        "promotion_rule": CONFIG["promotion_rule"],
    }
    path = REPORT_ROOT / "formal_dataset_plan.json"
    _json_dump(path, payload)
    return path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the diverse pure-procedural R75-v2 scratch-training package"
    )
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
        print(
            json.dumps(
                {"formal_plan": str(path), **build_plan("formal")},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    if args.plan_only:
        print(json.dumps(build_plan(args.profile), indent=2, ensure_ascii=False))
        return 0
    package_dir, manifest, audit = build_package(
        args.profile,
        args.output_root,
        force=args.force,
    )
    summary = {
        "package_dir": str(package_dir),
        "profile": args.profile,
        "total_pairs": manifest["total_pairs"],
        "geometry_count": manifest["geometry_count"],
        "split_counts": audit["split_counts"],
        "training_role_counts": audit["training_role_counts"],
        "identity_mode_counts": audit["identity_mode_counts"],
        "source_mean_distribution": audit["source_mean_distribution"],
        "dark_object_dark_background_count": audit["dark_object_dark_background_count"],
        "very_low_contrast_count": audit["very_low_contrast_count"],
        "source_audit_passed": audit["passed"],
        "real_image_pixels_used": audit["real_image_pixels_used"],
        "measured_shape_templates_used": audit["measured_shape_templates_used"],
        "pseudo_labels_used": audit["pseudo_labels_used"],
        "fixed_split_dir": str(package_dir / manifest["fixed_split_dir"]),
        "preview": str(package_dir / manifest["preview_roles"]),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
