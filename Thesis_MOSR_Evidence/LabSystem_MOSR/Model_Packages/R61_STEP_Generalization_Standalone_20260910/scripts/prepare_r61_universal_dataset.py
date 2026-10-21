"""Prepare R61 universal boundary generalization training data."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = PACKAGE_ROOT
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT / "training_data"
DEFAULT_PACKAGE_NAME = "r61_universal_boundary_train"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

DEFAULT_LEGACY_SOURCES = [
    {
        "role": "legacy_shape",
        "package_dir": PACKAGE_ROOT / "upstream_sources" / "r39_shape_mix_strong",
        "limit": 800,
    },
    {
        "role": "sequence_guard",
        "package_dir": PACKAGE_ROOT / "upstream_sources" / "r58_frac050_train",
        "limit": 1200,
    },
    {
        "role": "sem_truth_anchor",
        "package_dir": PACKAGE_ROOT / "upstream_sources" / "r60_sem_truth_realcrop_anchor_train",
        "limit": 1400,
    },
]

ROLE_DIR_BY_ROLE = {
    "legacy_shape": "stage_34_r61_legacy_shape",
    "sequence_guard": "stage_35_r61_sequence_guard",
    "sem_truth_anchor": "stage_36_r61_sem_truth_anchor",
    "universal_synthetic": "stage_37_r61_universal_synthetic",
    "motion_synthetic": "stage_38_r61_motion_synthetic",
    "motion_texture_synthetic": "stage_39_r61_motion_texture_synthetic",
    "step_guard_motion_texture_synthetic": "stage_40_r61_step_guard_motion_texture_synthetic",
}
BIAS_PROFILES = {
    "subpixel_uniform": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
    "hybrid_large_guard": [0.0, 0.5, 1.0, 1.0, 1.5, 1.5, 2.0, 2.0, 2.0, 2.5, 2.5, 2.5],
    "identity_guard_v2": {
        "dark": [0.0, 0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5],
    },
    "small_bias_dark_thin_v3": {
        "dark": [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5, 2.5],
        "bright": [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0],
    },
    "small_bias_guard_v4": {
        "dark": [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5],
        "bright": [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5],
    },
    "small_bias_replay_v5": {
        "dark": [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5, 2.5, 2.5],
        "bright": [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0, 2.0, 2.5, 2.5],
    },
    "failure_balanced_replay_v6": {
        "dark": [0.0, 0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5],
    },
    "failure_balanced_shape_neutral_v7": {
        "dark": [0.0, 0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5],
    },
    "bright_curve_replay_v8": {
        "dark": [0.0, 0.5, 1.0, 1.5, 1.5, 2.0, 2.5, 2.5],
        "bright": [0.0, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5, 2.5],
    },
    "bright_ellipse_guard_v9": {
        "dark": [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.0, 1.5, 2.0, 2.5],
    },
    "rotated_rect_guard_v10": {
        "dark": [0.0, 0.0, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5, 2.5],
    },
    "motion_guard_v11": {
        "dark": [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5],
    },
    "step_guard_v16": {
        "dark": [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5],
        "bright": [0.0, 0.0, 0.0, 0.25, 0.5, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 2.5, 2.5],
    },
    "polarity_adaptive": {
        "dark": [0.0, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0],
        "bright": [0.5, 1.0, 1.5, 2.0, 2.0, 2.5, 2.5],
    },
}

MOTION_STEP_CYCLE = (
    (0.0, 0.25),
    (0.0, 0.5),
    (0.0, 1.0),
    (0.0, 1.5),
    (0.15, 1.0),
    (-0.15, 1.0),
    (0.25, 2.0),
    (-0.25, 2.0),
    (0.12, 5.8),
    (-0.12, 5.8),
)
STEP_GUARD_MOTION_STEP_CYCLE = (
    (0.0, 0.0),
    (0.8, 0.0),
    (-0.8, 0.0),
    (0.0, 0.8),
    (8.0, 0.0),
    (-8.0, 0.0),
    (0.0, 8.0),
    (0.0, -8.0),
    (0.12, 5.8),
    (-0.12, 5.8),
)


@dataclass(frozen=True)
class GeneralizationPair:
    source_image: np.ndarray
    truth_label: np.ndarray
    boundary_mask: np.ndarray
    centerline_mask: np.ndarray
    distance_map: np.ndarray
    polarity: str
    shape_family: str
    geometry_id: str


def bias_cycle_for_profile(profile: str, polarity: str | None = None) -> list[float]:
    key = str(profile).strip()
    if key not in BIAS_PROFILES:
        valid = ", ".join(sorted(BIAS_PROFILES))
        raise ValueError(f"unknown synthetic bias profile '{profile}', valid profiles: {valid}")
    profile_value = BIAS_PROFILES[key]
    if isinstance(profile_value, dict):
        polarity_key = str(polarity or "").strip().lower()
        if polarity_key not in profile_value:
            valid = ", ".join(sorted(profile_value))
            raise ValueError(f"profile '{profile}' requires polarity in: {valid}")
        return list(profile_value[polarity_key])
    return list(profile_value)


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    return img


def _write_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", np.clip(img, 0, 255).astype(np.uint8))
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _load_manifest(package_dir: Path) -> dict:
    path = Path(package_dir) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_clean_package_dir(package_dir: Path, output_root: Path) -> None:
    package_resolved = package_dir.resolve()
    output_resolved = output_root.resolve()
    try:
        within_output = package_resolved.is_relative_to(output_resolved)
    except AttributeError:
        within_output = str(package_resolved).lower().startswith(str(output_resolved).lower() + os.sep)
    if not within_output or package_resolved == output_resolved:
        raise RuntimeError(f"refusing to clean package outside output root: {package_resolved}")
    if package_dir.exists():
        shutil.rmtree(package_dir)


def compute_geometry_from_label(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = img.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    threshold = max(4.0, float(np.percentile(mag, 88)))
    centerline = (mag >= threshold).astype(np.uint8) * 255
    centerline = cv2.morphologyEx(centerline, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(centerline) == 0:
        centerline = cv2.Canny(gray, 40, 120)
    boundary = cv2.dilate(centerline, np.ones((3, 3), np.uint8), iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def compute_geometry_from_mask(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask_u8 = (mask > 0).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    centerline = cv2.morphologyEx(mask_u8, cv2.MORPH_GRADIENT, kernel)
    centerline = (centerline > 0).astype(np.uint8) * 255
    boundary = cv2.dilate(centerline, kernel, iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def _write_geometry_arrays(
    package_dir: Path,
    lbl_rel: Path,
    boundary: np.ndarray,
    centerline: np.ndarray,
    distance: np.ndarray,
) -> dict[str, str]:
    role_rel = lbl_rel.relative_to("lbl")
    boundary_rel = Path("geom") / "boundary" / role_rel
    centerline_rel = Path("geom") / "centerline" / role_rel
    distance_rel = Path("geom") / "distance" / role_rel.with_suffix(".npy")
    _write_image(package_dir / boundary_rel, boundary)
    _write_image(package_dir / centerline_rel, centerline)
    distance_path = package_dir / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
    }


def _write_geometry_for_label(package_dir: Path, lbl_rel: Path) -> dict[str, str]:
    label = _read_gray(package_dir / lbl_rel)
    boundary, centerline, distance = compute_geometry_from_label(label)
    return _write_geometry_arrays(package_dir, lbl_rel, boundary, centerline, distance)


def _draw_truth_mask(size: int, geometry_seed: int, shape_family: str) -> np.ndarray:
    rng = np.random.default_rng(int(geometry_seed))
    mask = np.zeros((int(size), int(size)), np.uint8)
    center = (int(size) // 2, int(size) // 2)
    radius = int(size * rng.uniform(0.16, 0.22))
    cv2.circle(mask, center, radius, 255, -1, lineType=cv2.LINE_AA)
    if shape_family in {"mixed", "ellipse", "all"}:
        axes = (int(size * rng.uniform(0.10, 0.16)), int(size * rng.uniform(0.06, 0.11)))
        cv2.ellipse(
            mask,
            (int(size * 0.30), int(size * 0.30)),
            axes,
            float(rng.uniform(-35, 35)),
            0,
            360,
            255,
            -1,
            lineType=cv2.LINE_AA,
        )
    if shape_family in {"mixed", "rect", "all"}:
        rect = ((int(size * 0.70), int(size * 0.30)), (int(size * 0.24), int(size * 0.10)), float(rng.uniform(-35, 35)))
        box = cv2.boxPoints(rect).astype(np.int32)
        cv2.fillPoly(mask, [box], 255, lineType=cv2.LINE_AA)
    if shape_family in {"mixed", "polygon", "all"}:
        points = np.array(
            [
                [size * 0.62, size * 0.66],
                [size * 0.78, size * 0.58],
                [size * 0.88, size * 0.74],
                [size * 0.74, size * 0.88],
                [size * 0.58, size * 0.80],
            ],
            dtype=np.float32,
        )
        points += rng.normal(0, size * 0.015, size=points.shape)
        cv2.fillPoly(mask, [points.astype(np.int32)], 255, lineType=cv2.LINE_AA)
    if shape_family in {"mixed", "thin_bar", "all"}:
        rect = ((int(size * 0.30), int(size * 0.74)), (int(size * 0.38), int(size * 0.050)), float(rng.uniform(-55, 55)))
        box = cv2.boxPoints(rect).astype(np.int32)
        cv2.fillPoly(mask, [box], 255, lineType=cv2.LINE_AA)
    if shape_family in {"mixed", "annulus", "all"}:
        ring_center = (int(size * 0.72), int(size * 0.74))
        outer = int(size * rng.uniform(0.10, 0.14))
        inner = max(3, int(outer * rng.uniform(0.42, 0.58)))
        cv2.circle(mask, ring_center, outer, 255, -1, lineType=cv2.LINE_AA)
        cv2.circle(mask, ring_center, inner, 0, -1, lineType=cv2.LINE_AA)
    return mask


def _shape_cycle_for_bias_profile(profile: str) -> list[str]:
    if str(profile) == "identity_guard_v2":
        return ["mixed", "circle", "ellipse", "rect", "polygon", "thin_bar", "annulus"]
    if str(profile) == "small_bias_dark_thin_v3":
        return ["thin_bar", "circle", "thin_bar", "ellipse", "rect", "thin_bar", "polygon", "annulus", "thin_bar", "rect"]
    if str(profile) == "small_bias_guard_v4":
        return ["thin_bar", "circle", "ellipse", "rect", "polygon", "annulus", "thin_bar", "mixed"]
    if str(profile) == "small_bias_replay_v5":
        return ["thin_bar", "circle", "ellipse", "rect", "polygon", "annulus", "mixed", "thin_bar", "rect", "annulus"]
    if str(profile) == "failure_balanced_replay_v6":
        return ["ellipse", "circle", "ellipse", "rect", "polygon", "annulus", "thin_bar", "mixed", "ellipse", "thin_bar", "annulus", "rect"]
    if str(profile) == "failure_balanced_shape_neutral_v7":
        return [
            "circle",
            "ellipse",
            "rect",
            "polygon",
            "thin_bar",
            "annulus",
            "mixed",
            "circle",
            "ellipse",
            "rect",
            "polygon",
            "thin_bar",
            "annulus",
            "mixed",
        ]
    if str(profile) == "bright_curve_replay_v8":
        return ["ellipse", "annulus", "rect", "circle", "thin_bar", "polygon", "mixed", "ellipse", "annulus", "rect", "thin_bar", "mixed"]
    if str(profile) == "bright_ellipse_guard_v9":
        return [
            "ellipse",
            "circle",
            "ellipse",
            "rect",
            "polygon",
            "annulus",
            "mixed",
            "ellipse",
            "thin_bar",
            "polygon",
            "rect",
            "circle",
            "ellipse",
            "annulus",
        ]
    if str(profile) == "rotated_rect_guard_v10":
        return [
            "rect",
            "ellipse",
            "rect",
            "annulus",
            "rect",
            "polygon",
            "thin_bar",
            "circle",
            "rect",
            "mixed",
            "ellipse",
            "annulus",
            "rect",
            "polygon",
            "thin_bar",
            "mixed",
        ]
    if str(profile) == "motion_guard_v11":
        return [
            "annulus",
            "ellipse",
            "rect",
            "thin_bar",
            "circle",
            "polygon",
            "mixed",
            "annulus",
            "rect",
            "thin_bar",
            "ellipse",
            "circle",
        ]
    if str(profile) == "step_guard_v16":
        return [
            "annulus",
            "ellipse",
            "annulus",
            "ellipse",
            "circle",
            "rect",
            "annulus",
            "ellipse",
            "thin_bar",
            "polygon",
            "mixed",
            "rect",
        ]
    return ["mixed", "ellipse", "rect", "polygon"]


def _bias_mask(mask: np.ndarray, bias_px: float, polarity: str) -> np.ndarray:
    bias = max(0.0, float(bias_px))
    if bias <= 1e-6:
        return mask.copy()
    lo = int(np.floor(bias))
    hi = lo + 1
    frac = float(bias - lo)

    def morph_radius(radius_px: int) -> np.ndarray:
        radius = max(0, int(radius_px))
        if radius <= 0:
            return mask.astype(np.float32)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        if polarity == "dark":
            return cv2.erode(mask, kernel).astype(np.float32)
        return cv2.dilate(mask, kernel).astype(np.float32)

    lo_img = morph_radius(lo)
    hi_img = morph_radius(hi)
    blended = lo_img * (1.0 - frac) + hi_img * frac
    return np.clip(np.rint(blended), 0, 255).astype(np.uint8)


def _render_from_mask(mask: np.ndarray, *, bg: int, fg: int) -> np.ndarray:
    alpha = (mask.astype(np.float32) / 255.0).clip(0, 1)
    img = np.full(mask.shape, float(bg), np.float32)
    img = img * (1.0 - alpha) + float(fg) * alpha
    return np.clip(img, 0, 255).astype(np.uint8)


def _shift_image(img: np.ndarray, dx: float, dy: float, *, border_value: float, interpolation: int) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = np.array([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
    shifted = cv2.warpAffine(
        img,
        matrix,
        (w, h),
        flags=int(interpolation),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=float(border_value),
    )
    return shifted


def _standardize_field(field: np.ndarray) -> np.ndarray:
    out = field.astype(np.float32, copy=False)
    return (out - float(out.mean())) / (float(out.std()) + 1e-6)


def _apply_camera_like_texture(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    source = img.astype(np.float32, copy=False)
    h, w = source.shape[:2]
    low_h = max(4, h // 24)
    low_w = max(4, w // 24)
    low = rng.normal(0.0, 1.0, size=(low_h, low_w)).astype(np.float32)
    low = cv2.resize(low, (w, h), interpolation=cv2.INTER_CUBIC)
    low = cv2.GaussianBlur(low, (0, 0), sigmaX=max(2.0, min(h, w) / 32.0))
    low = _standardize_field(low)

    fine = rng.normal(0.0, 1.0, size=(h, w)).astype(np.float32)
    fine = cv2.GaussianBlur(fine, (0, 0), sigmaX=0.65)
    fine = _standardize_field(fine)

    xx = np.linspace(0.0, 2.0 * np.pi, w, dtype=np.float32)[None, :]
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    stripe = np.sin(xx * float(rng.uniform(2.0, 5.0)) + phase).astype(np.float32)

    gain = 1.0 + 0.055 * low + 0.018 * stripe
    textured = source * gain + 4.0 * fine + rng.normal(0.0, 1.0, size=source.shape)
    return np.clip(textured, 0, 255).astype(np.uint8)


def _apply_frame_jitter(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    source = img.astype(np.float32, copy=False)
    gain = float(rng.uniform(0.985, 1.015))
    offset = float(rng.uniform(-2.0, 2.0))
    jittered = source * gain + offset + rng.normal(0.0, 0.9, size=source.shape)
    return np.clip(jittered, 0, 255).astype(np.uint8)


def render_generalization_pair(
    *,
    size: int = 256,
    geometry_seed: int = 1,
    appearance_seed: int = 2,
    polarity: str = "dark",
    shape_family: str = "mixed",
    bias_px: float = 2.0,
    blur_sigma: float = 1.2,
    noise_sigma: float = 2.0,
) -> GeneralizationPair:
    polarity = str(polarity).lower()
    if polarity not in {"dark", "bright"}:
        raise ValueError("polarity must be 'dark' or 'bright'")
    rng = np.random.default_rng(int(appearance_seed))
    truth_mask = _draw_truth_mask(int(size), int(geometry_seed), str(shape_family))
    truth_bg = 128
    truth_fg = 32 if polarity == "dark" else 224
    truth_label = _render_from_mask(truth_mask, bg=truth_bg, fg=truth_fg)
    source_mask = _bias_mask(truth_mask, float(bias_px), polarity)
    bg = int(rng.integers(88, 132))
    if polarity == "dark":
        fg = int(rng.integers(20, 58))
    else:
        fg = int(rng.integers(176, 224))
    source = _render_from_mask(source_mask, bg=bg, fg=fg).astype(np.float32)
    source = cv2.GaussianBlur(source, (0, 0), sigmaX=float(blur_sigma), sigmaY=float(blur_sigma))
    h, w = source.shape
    x_grad = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    y_grad = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    source *= 1.0 + float(rng.uniform(-0.08, 0.08)) * x_grad + float(rng.uniform(-0.06, 0.06)) * y_grad
    if float(noise_sigma) > 0:
        source += rng.normal(0.0, float(noise_sigma), size=source.shape)
    boundary, centerline, distance = compute_geometry_from_mask(truth_mask)
    return GeneralizationPair(
        source_image=np.clip(source, 0, 255).astype(np.uint8),
        truth_label=truth_label.astype(np.uint8),
        boundary_mask=boundary.astype(np.uint8),
        centerline_mask=centerline.astype(np.uint8),
        distance_map=distance.astype(np.float32, copy=False),
        polarity=polarity,
        shape_family=str(shape_family),
        geometry_id=f"{shape_family}:{int(geometry_seed)}",
    )


def _copy_or_link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _iter_manifest_pairs(package_dir: Path, limit: int | None = None) -> list[dict]:
    manifest = _load_manifest(package_dir)
    pairs = list(manifest.get("pairs", []))
    if limit is not None:
        pairs = pairs[: max(0, int(limit))]
    return pairs


def _normalize_rel(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _import_legacy_pairs(package_dir: Path, package_out: Path, role: str, limit: int | None) -> list[dict]:
    package_dir = Path(package_dir).resolve()
    imported: list[dict] = []
    for idx, pair in enumerate(_iter_manifest_pairs(package_dir, limit)):
        src_rel_old = Path(_normalize_rel(pair.get("package_src", "")))
        lbl_rel_old = Path(_normalize_rel(pair.get("package_lbl", "")))
        if not src_rel_old.parts or not lbl_rel_old.parts:
            continue
        src_old = package_dir / src_rel_old
        lbl_old = package_dir / lbl_rel_old
        if not src_old.exists() or not lbl_old.exists():
            continue
        suffix = Path(*src_rel_old.parts[1:]) if src_rel_old.parts[0] == "src" else src_rel_old
        role_dir = ROLE_DIR_BY_ROLE.get(str(role), str(role))
        rel = Path(role_dir) / suffix
        src_new_rel = Path("src") / rel
        lbl_new_rel = Path("lbl") / rel
        _copy_or_link(src_old, package_out / src_new_rel)
        _copy_or_link(lbl_old, package_out / lbl_new_rel)
        geom = _write_geometry_for_label(package_out, lbl_new_rel)
        record = {
            **{k: v for k, v in pair.items() if k not in {"package_src", "package_lbl", "geometry_boundary", "geometry_centerline", "geometry_distance"}},
            "package_src": src_new_rel.as_posix(),
            "package_lbl": lbl_new_rel.as_posix(),
            "role": str(role),
            "source_group": str(role),
            "source_package": str(package_dir),
            "source_index": int(idx),
            "polarity": str(pair.get("polarity", "unknown")),
            "label_source": str(pair.get("label_source", "legacy")),
            **geom,
        }
        imported.append(record)
    return imported


def _write_synthetic_pairs(
    package_dir: Path,
    *,
    count: int,
    image_size: int,
    seed: int,
    bias_profile: str,
) -> list[dict]:
    records: list[dict] = []
    shape_cycle = _shape_cycle_for_bias_profile(str(bias_profile))
    for idx in range(max(0, int(count))):
        polarity = "dark" if idx % 2 == 0 else "bright"
        shape_family = shape_cycle[(idx // 2) % len(shape_cycle)]
        geometry_seed = int(seed) + idx // 2
        bias_cycle = bias_cycle_for_profile(bias_profile, polarity=polarity)
        bias_px = float(bias_cycle[(idx // 2) % len(bias_cycle)])
        pair = render_generalization_pair(
            size=int(image_size),
            geometry_seed=geometry_seed,
            appearance_seed=int(seed) * 10 + idx,
            polarity=polarity,
            shape_family=shape_family,
            bias_px=bias_px,
            blur_sigma=1.15 + 0.15 * (idx % 3),
            noise_sigma=2.0 + float(idx % 4),
        )
        stem = f"universal_{shape_family}_{pair.polarity}_{idx:05d}.bmp"
        rel = Path(ROLE_DIR_BY_ROLE["universal_synthetic"]) / pair.polarity / shape_family / stem
        src_rel = Path("src") / rel
        lbl_rel = Path("lbl") / rel
        _write_image(package_dir / src_rel, pair.source_image)
        _write_image(package_dir / lbl_rel, pair.truth_label)
        geom = _write_geometry_arrays(package_dir, lbl_rel, pair.boundary_mask, pair.centerline_mask, pair.distance_map)
        records.append(
            {
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "role": "universal_synthetic",
                "source_group": "universal_synthetic",
                "domain": "synthetic_boundary_generalization",
                "feature": shape_family,
                "shape_family": shape_family,
                "polarity": pair.polarity,
                "geometry_id": pair.geometry_id,
                "label_source": "known_synthetic_truth",
                "bias_px": bias_px,
                "bias_profile": str(bias_profile),
                "anti_answer_leakage": True,
                **geom,
            }
        )
    return records


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_motion_synthetic_pairs(
    package_dir: Path,
    *,
    count: int,
    image_size: int,
    seed: int,
    bias_profile: str,
    role: str = "motion_synthetic",
    texture_domain: str | None = None,
    motion_step_cycle: tuple[tuple[float, float], ...] = MOTION_STEP_CYCLE,
    domain: str | None = None,
    label_source: str = "known_synthetic_motion_truth",
    extra_record_fields: dict | None = None,
    extra_meta_fields: dict | None = None,
) -> list[dict]:
    records: list[dict] = []
    shape_cycle = _shape_cycle_for_bias_profile(str(bias_profile))
    role = str(role)
    role_dir = ROLE_DIR_BY_ROLE[role]
    use_texture = texture_domain is not None
    step_cycle = tuple(motion_step_cycle)
    if not step_cycle:
        raise ValueError("motion_step_cycle must not be empty")
    record_extra = dict(extra_record_fields or {})
    meta_extra = dict(extra_meta_fields or {})
    for idx in range(max(0, int(count))):
        polarity = "dark" if idx % 2 == 0 else "bright"
        shape_family = shape_cycle[idx % len(shape_cycle)]
        geometry_seed = int(seed) + 100000 + idx
        bias_cycle = bias_cycle_for_profile(bias_profile, polarity=polarity)
        bias_px = float(bias_cycle[idx % len(bias_cycle)])
        dx, dy = step_cycle[idx % len(step_cycle)]
        if idx % 4 >= 2:
            dy = -float(dy)
        pair = render_generalization_pair(
            size=int(image_size),
            geometry_seed=geometry_seed,
            appearance_seed=int(seed) * 20 + idx,
            polarity=polarity,
            shape_family=shape_family,
            bias_px=bias_px,
            blur_sigma=1.10 + 0.10 * (idx % 4),
            noise_sigma=1.0 + float(idx % 3),
        )
        source_a = pair.source_image
        texture_rng = np.random.default_rng(int(seed) * 1000 + idx)
        if use_texture:
            source_a = _apply_camera_like_texture(source_a, texture_rng)
        truth_bg = 128.0
        src_bg = float(np.median(source_a[: max(1, image_size // 8), : max(1, image_size // 8)]))
        src_b = _shift_image(source_a, dx, dy, border_value=src_bg, interpolation=cv2.INTER_LINEAR)
        if use_texture:
            src_b = _apply_frame_jitter(src_b, texture_rng)
        lbl_b = _shift_image(pair.truth_label, dx, dy, border_value=truth_bg, interpolation=cv2.INTER_LINEAR)
        boundary_b = _shift_image(pair.boundary_mask, dx, dy, border_value=0, interpolation=cv2.INTER_NEAREST)
        centerline_b = _shift_image(pair.centerline_mask, dx, dy, border_value=0, interpolation=cv2.INTER_NEAREST)
        distance_b = cv2.distanceTransform((boundary_b == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
        frames = [
            {
                "frame": 0,
                "source": source_a,
                "label": pair.truth_label,
                "boundary": pair.boundary_mask,
                "centerline": pair.centerline_mask,
                "distance": pair.distance_map,
                "dx": 0.0,
                "dy": 0.0,
            },
            {
                "frame": 1,
                "source": np.clip(src_b, 0, 255).astype(np.uint8),
                "label": np.clip(lbl_b, 0, 255).astype(np.uint8),
                "boundary": np.clip(boundary_b, 0, 255).astype(np.uint8),
                "centerline": np.clip(centerline_b, 0, 255).astype(np.uint8),
                "distance": distance_b,
                "dx": float(dx),
                "dy": float(dy),
            },
        ]
        for frame in frames:
            stem = f"motion_seq{idx:05d}_f{int(frame['frame']):04d}.bmp"
            rel = Path(role_dir) / polarity / shape_family / f"seq{idx:05d}" / stem
            src_rel = Path("src") / rel
            lbl_rel = Path("lbl") / rel
            _write_image(package_dir / src_rel, frame["source"])
            _write_image(package_dir / lbl_rel, frame["label"])
            geom = _write_geometry_arrays(
                package_dir,
                lbl_rel,
                frame["boundary"],
                frame["centerline"],
                frame["distance"],
            )
            meta_rel = Path("geom") / "meta" / rel.with_suffix(".json")
            meta = {
                "role": role,
                "sequence_id": f"{role}_seq{idx:05d}",
                "frame": int(frame["frame"]),
                "delta_from_prev_px": {"dx": float(frame["dx"]), "dy": float(frame["dy"])},
                "feature_family": shape_family,
                "polarity": polarity,
                "bias_px": bias_px,
                "label_source": str(label_source),
            }
            if use_texture:
                meta["texture_domain"] = str(texture_domain)
                meta["no_real_sample_pixels"] = True
            meta.update(meta_extra)
            _write_json(package_dir / meta_rel, meta)
            record = {
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "role": role,
                "source_group": role,
                "domain": str(domain) if domain is not None else (
                    "synthetic_known_motion_camera_texture_generalization"
                    if use_texture
                    else "synthetic_known_motion_boundary_generalization"
                ),
                "feature": shape_family,
                "shape_family": shape_family,
                "polarity": polarity,
                "geometry_id": f"motion:{role}:{shape_family}:{geometry_seed}",
                "motion_sequence_id": f"{role}_seq{idx:05d}",
                "motion_frame": int(frame["frame"]),
                "motion_dx_px": float(frame["dx"]),
                "motion_dy_px": float(frame["dy"]),
                "motion_meta": meta_rel.as_posix(),
                "label_source": str(label_source),
                "bias_px": bias_px,
                "bias_profile": str(bias_profile),
                "anti_answer_leakage": True,
                **geom,
            }
            if use_texture:
                record["texture_domain"] = str(texture_domain)
                record["no_real_sample_pixels"] = True
            record.update(record_extra)
            records.append(record)
    return records


def _count_by_key(pairs: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for pair in pairs:
        value = str(pair.get(key, "unknown"))
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def prepare_package(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    package_name: str = DEFAULT_PACKAGE_NAME,
    legacy_sources: list[dict] | None = None,
    synthetic_count: int = 4096,
    motion_count: int = 0,
    motion_texture_count: int = 0,
    step_guard_count: int = 0,
    image_size: int = 256,
    seed: int = 6100,
    synthetic_bias_profile: str = "subpixel_uniform",
) -> dict:
    output_root = Path(output_root).resolve()
    package_dir = output_root / str(package_name)
    _safe_clean_package_dir(package_dir, output_root)
    package_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for source in list(legacy_sources if legacy_sources is not None else DEFAULT_LEGACY_SOURCES):
        role = str(source["role"])
        package = Path(source["package_dir"])
        limit = source.get("limit")
        records.extend(_import_legacy_pairs(package, package_dir, role, int(limit) if limit is not None else None))

    bias_profile = str(synthetic_bias_profile)
    records.extend(
        _write_synthetic_pairs(
            package_dir,
            count=int(synthetic_count),
            image_size=int(image_size),
            seed=int(seed),
            bias_profile=bias_profile,
        )
    )
    records.extend(
        _write_motion_synthetic_pairs(
            package_dir,
            count=int(motion_count),
            image_size=int(image_size),
            seed=int(seed),
            bias_profile=bias_profile,
        )
    )
    records.extend(
        _write_motion_synthetic_pairs(
            package_dir,
            count=int(motion_texture_count),
            image_size=int(image_size),
            seed=int(seed) + 17000,
            bias_profile=bias_profile,
            role="motion_texture_synthetic",
            texture_domain="procedural_camera_texture_v1",
        )
    )
    records.extend(
        _write_motion_synthetic_pairs(
            package_dir,
            count=int(step_guard_count),
            image_size=int(image_size),
            seed=int(seed) + 23000,
            bias_profile=bias_profile,
            role="step_guard_motion_texture_synthetic",
            texture_domain="procedural_step_guard_texture_v1",
            motion_step_cycle=STEP_GUARD_MOTION_STEP_CYCLE,
            domain="synthetic_known_step_like_motion_camera_texture_generalization",
            label_source="known_synthetic_step_guard_motion_truth",
            extra_record_fields={
                "real_step_data_used": False,
                "step_guard_type": "procedural_step_like_v16",
            },
            extra_meta_fields={
                "real_step_data_used": False,
                "step_guard_type": "procedural_step_like_v16",
            },
        )
    )
    if not records:
        raise RuntimeError("R61 package has no training pairs")

    total_motion_pairs = int(motion_count) + int(motion_texture_count) + int(step_guard_count)
    manifest = {
        "profile": str(package_name),
        "r61_universal_boundary_training": True,
        "target": "boundary_generalization_without_same_sample_posthoc_correction",
        "anti_answer_leakage_design": True,
        "old_data_reused": True,
        "universal_synthetic_pairing": "same truth boundary rendered with polarity-correct dark and bright targets",
        "total_pairs": len(records),
        "role_counts": _count_by_key(records, "role"),
        "polarity_counts": _count_by_key(records, "polarity"),
        "shape_family_counts": _count_by_key(records, "shape_family"),
        "synthetic_bias_px_counts": _count_by_key(records, "bias_px"),
        "synthetic_bias_profile": bias_profile,
        "motion_pair_count": total_motion_pairs,
        "motion_clean_pair_count": int(motion_count),
        "motion_texture_pair_count": int(motion_texture_count),
        "step_guard_motion_pair_count": int(step_guard_count),
        "geometry_sidecars": True,
        "geometry_count": len(records),
        "pairs": records,
        "generator": "prepare_r61_universal_dataset_v5_step_guard_motion",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "package_dir": str(package_dir),
        "total_pairs": len(records),
        "role_counts": manifest["role_counts"],
        "polarity_counts": manifest["polarity_counts"],
        "synthetic_bias_profile": manifest["synthetic_bias_profile"],
        "manifest": str(package_dir / "manifest.json"),
    }


def _collect_source_paths(package_dir: Path) -> list[str]:
    paths = []
    for path in (Path(package_dir) / "src").rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(_normalize_rel(path.relative_to(package_dir)))
    return sorted(paths)


def group_key_for_pair(pair: dict) -> str:
    role = str(pair.get("role", pair.get("source_group", "unknown"))).strip() or "unknown"
    polarity = str(pair.get("polarity", "unknown")).strip() or "unknown"
    if role == "universal_synthetic":
        return f"synthetic:{pair.get('geometry_id', pair.get('package_src', 'unknown'))}"
    template = pair.get("template_id", pair.get("sem_reference_id", pair.get("geometry_id", None)))
    if template is None:
        template = Path(str(pair.get("package_src", "unknown"))).stem
    return f"{role}:{pair.get('feature', 'unknown')}:{template}:{polarity}"


def _stratum_for_pair(pair: dict) -> str:
    role = str(pair.get("role", pair.get("source_group", "unknown"))).strip() or "unknown"
    polarity = str(pair.get("polarity", "unknown")).strip() or "unknown"
    return f"{role}:{polarity}"


def prepare_grouped_fixed_split(
    *,
    package_dir: Path,
    manifest: dict,
    val_ratio: float = 0.1,
    seed: int = 1337,
) -> dict:
    package_dir = Path(package_dir).resolve()
    source_paths = _collect_source_paths(package_dir)
    pair_by_src = {_normalize_rel(row["package_src"]): row for row in manifest.get("pairs", [])}
    missing = [path for path in source_paths if path not in pair_by_src]
    if missing:
        raise RuntimeError(f"manifest missing {len(missing)} source paths; first={missing[0]}")

    group_to_indices: dict[str, list[int]] = {}
    group_to_strata: dict[str, set[str]] = {}
    for idx, src in enumerate(source_paths):
        pair = pair_by_src[src]
        group = group_key_for_pair(pair)
        group_to_indices.setdefault(group, []).append(idx)
        group_to_strata.setdefault(group, set()).add(_stratum_for_pair(pair))

    rng = np.random.default_rng(int(seed))
    groups = sorted(group_to_indices)
    rng.shuffle(groups)
    ratio = max(0.0, min(0.95, float(val_ratio)))
    target_val = max(1, int(round(len(source_paths) * ratio))) if ratio > 0 else 0
    val_groups: list[str] = []
    strata = sorted({stratum for strata_set in group_to_strata.values() for stratum in strata_set})
    for stratum in strata:
        candidates = [group for group in groups if stratum in group_to_strata[group] and group not in val_groups]
        if candidates:
            val_groups.append(candidates[0])
    val_count = sum(len(group_to_indices[group]) for group in val_groups)
    for group in groups:
        if val_count >= target_val or len(val_groups) >= max(1, len(groups) - 1):
            break
        if group in val_groups:
            continue
        val_groups.append(group)
        val_count += len(group_to_indices[group])

    val_set = set(val_groups)
    train_idx: list[int] = []
    val_idx: list[int] = []
    for group in sorted(group_to_indices):
        target = val_idx if group in val_set else train_idx
        target.extend(group_to_indices[group])
    train_idx = sorted(train_idx)
    val_idx = sorted(val_idx)

    index_to_group = {}
    for group, indices in group_to_indices.items():
        for idx in indices:
            index_to_group[idx] = group
    train_groups = {index_to_group[idx] for idx in train_idx}
    val_groups_set = {index_to_group[idx] for idx in val_idx}
    overlap = sorted(train_groups & val_groups_set)
    val_tag = int(round(ratio * 1000.0))
    split_dir = package_dir / "splits" / f"grouped_seed{int(seed):04d}_val{val_tag:03d}"
    split_dir.mkdir(parents=True, exist_ok=True)
    np.save(split_dir / "train_idx.npy", np.asarray(train_idx, dtype=np.int64))
    np.save(split_dir / "val_idx.npy", np.asarray(val_idx, dtype=np.int64))
    meta = {
        "split_type": "r61_grouped_fixed_split",
        "seed": int(seed),
        "val_ratio": ratio,
        "source_path_count": len(source_paths),
        "train_count": len(train_idx),
        "val_count": len(val_idx),
        "group_count": len(group_to_indices),
        "train_group_count": len(train_groups),
        "val_group_count": len(val_groups_set),
        "group_overlap_count": len(overlap),
        "group_overlap_examples": overlap[:10],
        "train_strata": sorted({stratum for group in train_groups for stratum in group_to_strata[group]}),
        "val_strata": sorted({stratum for group in val_groups_set for stratum in group_to_strata[group]}),
        "source_paths_sorted": source_paths,
    }
    (split_dir / "split_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if overlap:
        raise RuntimeError(f"grouped split leaked {len(overlap)} groups")
    return {"split_dir": str(split_dir), **meta}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare R61 universal boundary generalization data")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--package-name", default=DEFAULT_PACKAGE_NAME)
    parser.add_argument("--synthetic-count", type=int, default=4096)
    parser.add_argument("--motion-count", type=int, default=0)
    parser.add_argument("--motion-texture-count", type=int, default=0)
    parser.add_argument("--step-guard-count", type=int, default=0)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--seed", type=int, default=6100)
    parser.add_argument("--synthetic-bias-profile", choices=sorted(BIAS_PROFILES), default="subpixel_uniform")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    summary = prepare_package(
        output_root=args.output_root,
        package_name=args.package_name,
        synthetic_count=args.synthetic_count,
        motion_count=args.motion_count,
        motion_texture_count=args.motion_texture_count,
        step_guard_count=args.step_guard_count,
        image_size=args.image_size,
        seed=args.seed,
        synthetic_bias_profile=args.synthetic_bias_profile,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
