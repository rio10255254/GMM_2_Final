"""Generate the procedural-only R88 datasets.

Each scene stores one 8x-antialiased geometry mask, one textured latent target,
one compact signed-distance map, and four independently degraded observations.
No SEM, real microscope image, measured sample contour, measured PSF, model
output, or checkpoint is read by this program.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
AUTH_PATH = ROOT / "config" / "execution_authorization.json"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
AUTH = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
DATA_ROOT = ROOT / "data"

FORMAL_ROLES = DESIGN["dataset"]["roles"]
HOLDOUT_ROLES = {
    "textured_general_geometry": 96,
    "identity_and_detail_guard": 64,
    "hard_photometry": 64,
    "difficult_contour": 64,
    "cross_tile_and_dense": 48,
    "signed_subpixel_motion": 32,
    "clean_contour_anchor": 16,
}
DEGRADATION_WEIGHTS = {
    "textured_general_geometry": {
        "standard_blur_and_noise": 4.0,
        "defocus_and_motion_blur": 3.0,
        "low_contrast_and_uneven_illumination": 2.0,
        "halo_ghost_and_banding": 2.0,
        "local_boundary_fade": 1.0,
        "compound_severe_but_recoverable": 1.0,
    },
    "hard_photometry": {
        "standard_blur_and_noise": 0.5,
        "defocus_and_motion_blur": 1.0,
        "low_contrast_and_uneven_illumination": 6.0,
        "halo_ghost_and_banding": 4.0,
        "local_boundary_fade": 2.0,
        "compound_severe_but_recoverable": 2.0,
    },
    "difficult_contour": {
        "standard_blur_and_noise": 1.5,
        "defocus_and_motion_blur": 2.0,
        "low_contrast_and_uneven_illumination": 1.0,
        "halo_ghost_and_banding": 1.0,
        "local_boundary_fade": 5.0,
        "compound_severe_but_recoverable": 3.0,
    },
    "cross_tile_and_dense": {
        "standard_blur_and_noise": 2.0,
        "defocus_and_motion_blur": 3.0,
        "low_contrast_and_uneven_illumination": 1.0,
        "halo_ghost_and_banding": 3.0,
        "local_boundary_fade": 1.0,
        "compound_severe_but_recoverable": 2.0,
    },
    "signed_subpixel_motion": {
        "standard_blur_and_noise": 3.0,
        "defocus_and_motion_blur": 3.0,
        "low_contrast_and_uneven_illumination": 1.5,
        "halo_ghost_and_banding": 1.0,
        "local_boundary_fade": 0.5,
        "compound_severe_but_recoverable": 1.0,
    },
    "clean_contour_anchor": {
        "standard_blur_and_noise": 5.0,
        "defocus_and_motion_blur": 2.0,
        "low_contrast_and_uneven_illumination": 1.0,
        "halo_ghost_and_banding": 0.5,
        "local_boundary_fade": 1.0,
        "compound_severe_but_recoverable": 0.5,
    },
}


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def save_npy_atomic(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, array, allow_pickle=False)
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(memoryview(np.ascontiguousarray(array)).cast("B")).hexdigest()


def polygon_points(cx: float, cy: float, radius: float, sides: int, angle: float, scale: int) -> np.ndarray:
    theta = angle + np.arange(sides, dtype=np.float64) * (2.0 * np.pi / sides)
    points = np.column_stack([cx + radius * np.cos(theta), cy + radius * np.sin(theta)])
    return np.rint(points * scale).astype(np.int32)


def star_points(cx: float, cy: float, outer: float, inner: float, tips: int, angle: float, scale: int) -> np.ndarray:
    radii = np.empty(tips * 2, dtype=np.float64)
    radii[0::2], radii[1::2] = outer, inner
    theta = angle + np.arange(tips * 2, dtype=np.float64) * (np.pi / tips)
    points = np.column_stack([cx + radii * np.cos(theta), cy + radii * np.sin(theta)])
    return np.rint(points * scale).astype(np.int32)


def draw_rotated_rect(mask: np.ndarray, center: tuple[float, float], size: tuple[float, float], angle: float, scale: int, value: int = 255) -> None:
    box = cv2.boxPoints(((center[0] * scale, center[1] * scale), (size[0] * scale, size[1] * scale), angle))
    cv2.fillPoly(mask, [np.rint(box).astype(np.int32)], value, lineType=cv2.LINE_8)


def draw_capsule(mask: np.ndarray, p0: tuple[float, float], p1: tuple[float, float], radius: float, scale: int, value: int = 255) -> None:
    q0 = tuple(np.rint(np.asarray(p0) * scale).astype(int))
    q1 = tuple(np.rint(np.asarray(p1) * scale).astype(int))
    width = max(1, int(round(2.0 * radius * scale)))
    cv2.line(mask, q0, q1, value, width, lineType=cv2.LINE_8)
    cv2.circle(mask, q0, max(1, width // 2), value, -1, lineType=cv2.LINE_8)
    cv2.circle(mask, q1, max(1, width // 2), value, -1, lineType=cv2.LINE_8)


def draw_basic(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int, count: int, size: tuple[float, float], *, allow_partial: bool = True) -> None:
    kinds = ["ellipse", "rectangle", "polygon", "capsule", "diamond"]
    for _ in range(count):
        lower, upper = (-0.08, 1.08) if allow_partial else (0.05, 0.95)
        cx, cy = rng.uniform(lower, upper, 2) * canvas
        radius = float(rng.uniform(*size))
        kind = str(rng.choice(kinds))
        if kind == "ellipse":
            axes = (max(2, int(radius * scale)), max(2, int(radius * rng.uniform(0.40, 1.25) * scale)))
            cv2.ellipse(mask, (int(cx * scale), int(cy * scale)), axes, float(rng.uniform(0, 180)), 0, 360, 255, -1, cv2.LINE_8)
        elif kind == "rectangle":
            draw_rotated_rect(mask, (float(cx), float(cy)), (2 * radius, 2 * radius * rng.uniform(0.35, 1.20)), float(rng.uniform(0, 180)), scale)
        elif kind == "polygon":
            cv2.fillPoly(mask, [polygon_points(float(cx), float(cy), radius, int(rng.integers(3, 10)), float(rng.uniform(0, np.pi)), scale)], 255, lineType=cv2.LINE_8)
        elif kind == "capsule":
            angle = float(rng.uniform(0, 2 * np.pi))
            length = radius * float(rng.uniform(1.0, 3.5))
            dx, dy = math.cos(angle) * length * 0.5, math.sin(angle) * length * 0.5
            draw_capsule(mask, (float(cx - dx), float(cy - dy)), (float(cx + dx), float(cy + dy)), radius * rng.uniform(0.20, 0.52), scale)
        else:
            cv2.fillPoly(mask, [polygon_points(float(cx), float(cy), radius, 4, np.pi / 4.0, scale)], 255, lineType=cv2.LINE_8)


def draw_noncircular(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int, count: int, *, holdout: bool = False) -> None:
    kinds = ["star", "gear", "lobed", "crescent", "notched", "concave"]
    if holdout:
        kinds += ["rough_lobed", "double_notch"]
    for _ in range(count):
        cx, cy = rng.uniform(0.03, 0.97, 2) * canvas
        radius = float(rng.uniform(22, min(210, canvas * 0.22)))
        kind = str(rng.choice(kinds))
        if kind in {"star", "gear"}:
            tips = int(rng.integers(5, 15))
            ratio = rng.uniform(0.32, 0.60) if kind == "star" else rng.uniform(0.70, 0.88)
            cv2.fillPoly(mask, [star_points(float(cx), float(cy), radius, radius * ratio, tips, float(rng.uniform(0, np.pi)), scale)], 255, lineType=cv2.LINE_8)
        elif kind in {"lobed", "rough_lobed"}:
            n = 128
            theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
            lobes = int(rng.integers(3, 11))
            rr = radius * (1.0 + rng.uniform(0.10, 0.30) * np.cos(lobes * theta + rng.uniform(0, 2 * np.pi)))
            if kind == "rough_lobed":
                rr *= 1.0 + 0.06 * np.sin((lobes * 3 + 1) * theta + rng.uniform(0, 2 * np.pi))
            points = np.column_stack([cx + rr * np.cos(theta), cy + rr * np.sin(theta)])
            cv2.fillPoly(mask, [np.rint(points * scale).astype(np.int32)], 255, lineType=cv2.LINE_8)
        elif kind == "crescent":
            center = (int(cx * scale), int(cy * scale))
            cv2.circle(mask, center, max(3, int(radius * scale)), 255, -1, cv2.LINE_8)
            offset = radius * rng.uniform(0.22, 0.58)
            angle = float(rng.uniform(0, 2 * np.pi))
            hole = (int((cx + offset * math.cos(angle)) * scale), int((cy + offset * math.sin(angle)) * scale))
            cv2.circle(mask, hole, max(2, int(radius * rng.uniform(0.68, 0.96) * scale)), 0, -1, cv2.LINE_8)
        elif kind in {"notched", "double_notch"}:
            cv2.circle(mask, (int(cx * scale), int(cy * scale)), max(3, int(radius * scale)), 255, -1, cv2.LINE_8)
            count_notches = 2 if kind == "double_notch" else int(rng.integers(2, 7))
            base_angle = float(rng.uniform(0, 2 * np.pi))
            for notch in range(count_notches):
                angle = base_angle + notch * (np.pi if kind == "double_notch" else rng.uniform(0.35, 1.35))
                nx, ny = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
                cv2.circle(mask, (int(nx * scale), int(ny * scale)), max(2, int(radius * rng.uniform(0.15, 0.36) * scale)), 0, -1, cv2.LINE_8)
        else:
            sides = int(rng.integers(8, 16))
            theta = np.sort(rng.uniform(0, 2 * np.pi, sides))
            rr = radius * rng.uniform(0.30, 1.0, sides)
            points = np.column_stack([cx + rr * np.cos(theta), cy + rr * np.sin(theta)])
            cv2.fillPoly(mask, [np.rint(points * scale).astype(np.int32)], 255, lineType=cv2.LINE_8)


def draw_thin_and_necks(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int) -> None:
    for _ in range(int(rng.integers(8, 24))):
        point_count = int(rng.integers(2, 7))
        points = np.column_stack([rng.uniform(0.01, 0.99, point_count) * canvas * scale, rng.uniform(0.01, 0.99, point_count) * canvas * scale])
        points = points.astype(np.int32).reshape(-1, 1, 2)
        width = max(2, int(rng.uniform(1.25, 13.0) * scale))
        cv2.polylines(mask, [points], False, 255, width, cv2.LINE_8)
    for _ in range(int(rng.integers(2, 7))):
        cx, cy = rng.uniform(0.10, 0.90, 2) * canvas
        angle = float(rng.uniform(0, 2 * np.pi))
        length = float(rng.uniform(45, 210))
        radius = float(rng.uniform(2.0, 8.0))
        dx, dy = math.cos(angle) * length / 2, math.sin(angle) * length / 2
        draw_capsule(mask, (float(cx - dx), float(cy - dy)), (float(cx + dx), float(cy + dy)), radius, scale)
        cv2.circle(mask, (int((cx - dx) * scale), int((cy - dy) * scale)), int(rng.uniform(15, 55) * scale), 255, -1, cv2.LINE_8)
        cv2.circle(mask, (int((cx + dx) * scale), int((cy + dy) * scale)), int(rng.uniform(15, 55) * scale), 255, -1, cv2.LINE_8)


def draw_dense(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int, *, large_region: bool = True) -> None:
    margin = int(rng.uniform(20, 100 if large_region else 180))
    x0, y0, x1, y1 = margin, margin, canvas - margin, canvas - margin
    pitch = float(rng.uniform(12, 78))
    radius = max(1.5, pitch * rng.uniform(0.14, 0.36))
    kind = str(rng.choice(["dots", "squares", "staggered", "missing", "short_lines"]))
    row = 0
    y = y0 + pitch * 0.5
    while y < y1:
        offset = pitch * 0.5 if kind == "staggered" and row % 2 else 0.0
        x, col = x0 + pitch * 0.5 + offset, 0
        while x < x1:
            missing = kind == "missing" and ((row * 31 + col * 17) % 19 == 0)
            if not missing:
                center = (int(round(x * scale)), int(round(y * scale)))
                if kind == "squares":
                    half = int(radius * scale)
                    cv2.rectangle(mask, (center[0] - half, center[1] - half), (center[0] + half, center[1] + half), 255, -1, cv2.LINE_8)
                elif kind == "short_lines":
                    half = int(radius * 1.8 * scale)
                    cv2.line(mask, (center[0] - half, center[1]), (center[0] + half, center[1]), 255, max(1, int(radius * 0.7 * scale)), cv2.LINE_8)
                else:
                    cv2.circle(mask, center, max(1, int(radius * scale)), 255, -1, cv2.LINE_8)
            x += pitch
            col += 1
        y += pitch
        row += 1


def generate_geometry(role: str, seed: int, canvas: int, scale: int, *, holdout: bool) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    for attempt in range(16):
        rng = np.random.default_rng(seed + attempt * 100003)
        high = np.zeros((canvas * scale, canvas * scale), dtype=np.uint8)
        if role == "textured_general_geometry":
            draw_basic(high, rng, canvas, scale, int(rng.integers(7, 20)), (10, min(150, canvas * 0.18)))
            draw_noncircular(high, rng, canvas, scale, int(rng.integers(2, 7)), holdout=holdout)
            if rng.random() < 0.45:
                draw_dense(high, rng, canvas, scale, large_region=False)
        elif role == "identity_and_detail_guard":
            draw_basic(high, rng, canvas, scale, int(rng.integers(10, 30)), (5, min(95, canvas * 0.12)))
            if rng.random() < 0.55:
                draw_dense(high, rng, canvas, scale)
        elif role == "hard_photometry":
            draw_basic(high, rng, canvas, scale, int(rng.integers(5, 15)), (18, min(180, canvas * 0.20)))
            draw_noncircular(high, rng, canvas, scale, int(rng.integers(3, 10)), holdout=holdout)
        elif role == "difficult_contour":
            draw_noncircular(high, rng, canvas, scale, int(rng.integers(6, 16)), holdout=True)
            draw_thin_and_necks(high, rng, canvas, scale)
        elif role == "cross_tile_and_dense":
            draw_basic(high, rng, canvas, scale, int(rng.integers(2, 6)), (max(80, canvas * 0.18), max(150, canvas * 0.48)))
            draw_dense(high, rng, canvas, scale)
        elif role == "signed_subpixel_motion":
            draw_basic(high, rng, canvas, scale, int(rng.integers(6, 16)), (15, min(150, canvas * 0.18)), allow_partial=False)
            draw_noncircular(high, rng, canvas, scale, int(rng.integers(2, 7)), holdout=holdout)
        elif role == "clean_contour_anchor":
            draw_basic(high, rng, canvas, scale, int(rng.integers(4, 10)), (25, min(200, canvas * 0.22)), allow_partial=False)
        else:
            raise KeyError(role)
        coverage = cv2.resize(high, (canvas, canvas), interpolation=cv2.INTER_AREA)
        area = float(np.mean(coverage > 127))
        fractional = int(np.count_nonzero((coverage > 0) & (coverage < 255)))
        if 0.025 <= area <= 0.80 and fractional > 32:
            binary = (coverage >= 128).astype(np.uint8)
            components, _ = cv2.connectedComponents(binary, connectivity=8)
            contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            holes = int(sum(1 for item in ([] if hierarchy is None else hierarchy[0]) if int(item[3]) >= 0))
            return high, coverage, {
                "attempt": attempt,
                "foreground_area_fraction": area,
                "fractional_coverage_pixels": fractional,
                "component_count": int(max(0, components - 1)),
                "hole_count": holes,
            }
    raise RuntimeError(f"Could not generate geometry: role={role}, seed={seed}")


def random_field(rng: np.random.Generator, canvas: int, family: str) -> np.ndarray:
    def coarse(grid: int, sigma: float = 0.0) -> np.ndarray:
        small = rng.normal(0.0, 1.0, (grid, grid)).astype(np.float32)
        field = cv2.resize(small, (canvas, canvas), interpolation=cv2.INTER_CUBIC)
        if sigma > 0:
            field = cv2.GaussianBlur(field, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
        return field

    if family == "multiscale_gaussian_random_field":
        field = 0.55 * coarse(24) + 0.30 * coarse(64) + 0.15 * coarse(160, 0.6)
    elif family == "anisotropic_grain":
        field = rng.normal(0.0, 1.0, (canvas, canvas)).astype(np.float32)
        sx, sy = (rng.uniform(0.6, 1.4), rng.uniform(2.0, 7.0)) if rng.random() < 0.5 else (rng.uniform(2.0, 7.0), rng.uniform(0.6, 1.4))
        field = cv2.GaussianBlur(field, (0, 0), sigmaX=float(sx), sigmaY=float(sy), borderType=cv2.BORDER_REFLECT_101)
    elif family == "band_limited_particles":
        field = np.zeros((canvas, canvas), np.float32)
        for _ in range(int(rng.integers(100, 500))):
            x, y = rng.integers(0, canvas, 2)
            cv2.circle(field, (int(x), int(y)), int(rng.integers(1, 7)), float(rng.uniform(-1, 1)), -1, cv2.LINE_AA)
        field = cv2.GaussianBlur(field, (0, 0), rng.uniform(0.8, 2.8), borderType=cv2.BORDER_REFLECT_101)
    elif family == "weak_scratches_and_pits":
        field = 0.35 * coarse(48)
        for _ in range(int(rng.integers(8, 30))):
            x0, y0, x1, y1 = rng.integers(0, canvas, 4)
            cv2.line(field, (int(x0), int(y0)), (int(x1), int(y1)), float(rng.uniform(-1.5, 1.5)), int(rng.integers(1, 4)), cv2.LINE_AA)
        for _ in range(int(rng.integers(10, 50))):
            x, y = rng.integers(0, canvas, 2)
            cv2.circle(field, (int(x), int(y)), int(rng.integers(1, 6)), float(rng.uniform(-1.5, 0.2)), -1, cv2.LINE_AA)
        field = cv2.GaussianBlur(field, (0, 0), 0.7, borderType=cv2.BORDER_REFLECT_101)
    elif family == "low_frequency_material_variation":
        field = coarse(10) + 0.2 * coarse(36)
    else:
        yy, xx = np.mgrid[0:canvas, 0:canvas].astype(np.float32)
        p1, p2 = rng.uniform(18, 180, 2)
        field = np.sin(2 * np.pi * xx / p1 + rng.uniform(0, 2 * np.pi))
        field += 0.6 * np.sin(2 * np.pi * yy / p2 + rng.uniform(0, 2 * np.pi))
        field += 0.25 * coarse(96)
    field = field.astype(np.float32)
    field -= float(np.mean(field))
    scale = float(np.std(field))
    if scale > 1e-6:
        field /= scale
    return np.clip(field, -3.0, 3.0) / 3.0


TEXTURE_FAMILIES = [
    "multiscale_gaussian_random_field",
    "anisotropic_grain",
    "band_limited_particles",
    "weak_scratches_and_pits",
    "low_frequency_material_variation",
    "fixed_pattern_sensor_texture",
]


def textured_target(coverage: np.ndarray, role: str, seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    canvas = int(coverage.shape[0])
    bright = bool(rng.integers(0, 2))
    if bright:
        bg_mean, fg_mean = float(rng.uniform(0.05, 0.32)), float(rng.uniform(0.65, 0.96))
    else:
        bg_mean, fg_mean = float(rng.uniform(0.68, 0.96)), float(rng.uniform(0.04, 0.34))
    family_fg = str(rng.choice(TEXTURE_FAMILIES))
    family_bg = str(rng.choice(TEXTURE_FAMILIES))
    family_shared = str(rng.choice(TEXTURE_FAMILIES))
    shared = random_field(rng, canvas, family_shared)
    foreground_texture = random_field(rng, canvas, family_fg)
    background_texture = random_field(rng, canvas, family_bg)
    if role == "clean_contour_anchor":
        amp_fg, amp_bg = float(rng.uniform(0.006, 0.025)), float(rng.uniform(0.004, 0.018))
    elif role == "identity_and_detail_guard":
        amp_fg, amp_bg = float(rng.uniform(0.035, 0.11)), float(rng.uniform(0.025, 0.09))
    else:
        amp_fg, amp_bg = float(rng.uniform(0.018, 0.10)), float(rng.uniform(0.012, 0.075))
    shared_fraction = float(rng.uniform(0.15, 0.65))
    foreground = fg_mean + amp_fg * (shared_fraction * shared + (1.0 - shared_fraction) * foreground_texture)
    background = bg_mean + amp_bg * (shared_fraction * shared + (1.0 - shared_fraction) * background_texture)
    alpha = coverage.astype(np.float32) / 255.0
    target = np.clip(background * (1.0 - alpha) + foreground * alpha, 0.0, 1.0)
    return np.rint(target * 255.0).astype(np.uint8), {
        "bright_foreground": bright,
        "foreground_mean": fg_mean,
        "background_mean": bg_mean,
        "foreground_texture_family": family_fg,
        "background_texture_family": family_bg,
        "shared_texture_family": family_shared,
        "foreground_texture_amplitude": amp_fg,
        "background_texture_amplitude": amp_bg,
        "shared_texture_fraction": shared_fraction,
    }


def compact_sdf(coverage: np.ndarray) -> np.ndarray:
    size = max(8, coverage.shape[0] // 4)
    small = cv2.resize(coverage, (size, size), interpolation=cv2.INTER_AREA)
    inside = (small >= 128).astype(np.uint8)
    outside = 1 - inside
    d_in = cv2.distanceTransform(inside, cv2.DIST_L2, 5)
    d_out = cv2.distanceTransform(outside, cv2.DIST_L2, 5)
    return np.rint(np.clip(d_in - d_out, -31, 31)).astype(np.int8)


def warp_u8(array: np.ndarray, dx: float, dy: float, *, interpolation: int) -> np.ndarray:
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return array
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(array, matrix, (array.shape[1], array.shape[0]), flags=interpolation, borderMode=cv2.BORDER_REFLECT_101)


def motion_kernel(length: int, angle: float) -> np.ndarray:
    length = max(1, int(length) | 1)
    kernel = np.zeros((length, length), dtype=np.float32)
    center = length // 2
    radians = math.radians(angle)
    dx, dy = math.cos(radians) * center, math.sin(radians) * center
    cv2.line(kernel, (int(round(center - dx)), int(round(center - dy))), (int(round(center + dx)), int(round(center + dy))), 1.0, 1, cv2.LINE_AA)
    return kernel / max(float(kernel.sum()), 1e-8)


def illumination_field(shape: tuple[int, int], rng: np.random.Generator, strength: float) -> np.ndarray:
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xx, yy = xx / max(w - 1, 1) * 2 - 1, yy / max(h - 1, 1) * 2 - 1
    angle = float(rng.uniform(0, 2 * np.pi))
    gradient = math.cos(angle) * xx + math.sin(angle) * yy
    cx, cy = rng.uniform(-0.55, 0.55, 2)
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return 1.0 + strength * (0.55 * gradient - 0.45 * radius)


def degrade(target_u8: np.ndarray, mask_u8: np.ndarray, family: str, parameter_seed: int, noise_seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(parameter_seed)
    noise_rng = np.random.default_rng(noise_seed)
    target = target_u8.astype(np.float32) / 255.0
    image = target.copy()
    meta: dict[str, Any] = {"family": family}
    ranges = {
        "identity_and_near_identity": ((0.0, 0.28), (0.0, 0.0025)),
        "standard_blur_and_noise": ((0.35, 1.8), (0.002, 0.018)),
        "defocus_and_motion_blur": ((0.8, 3.0), (0.003, 0.024)),
        "low_contrast_and_uneven_illumination": ((0.45, 2.4), (0.003, 0.026)),
        "halo_ghost_and_banding": ((0.7, 2.7), (0.003, 0.028)),
        "local_boundary_fade": ((0.6, 2.5), (0.003, 0.025)),
        "compound_severe_but_recoverable": ((1.5, 4.0), (0.007, 0.036)),
    }
    (sigma_min, sigma_max), (noise_min, noise_max) = ranges[family]
    sigma, noise = float(rng.uniform(sigma_min, sigma_max)), float(rng.uniform(noise_min, noise_max))
    if sigma > 0.05:
        sigma_y = sigma * float(rng.uniform(0.60, 1.55))
        image = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma_y, borderType=cv2.BORDER_REFLECT_101)
        meta.update(blur_sigma_x=sigma, blur_sigma_y=sigma_y)
    if family in {"defocus_and_motion_blur", "compound_severe_but_recoverable"}:
        length = int(rng.integers(3, 11 if family == "defocus_and_motion_blur" else 15))
        angle = float(rng.uniform(0, 180))
        image = cv2.filter2D(image, -1, motion_kernel(length, angle), borderType=cv2.BORDER_REFLECT_101)
        meta.update(motion_length=length, motion_angle=angle)
    if family in {"low_contrast_and_uneven_illumination", "halo_ghost_and_banding", "local_boundary_fade", "compound_severe_but_recoverable"}:
        strength = float(rng.uniform(0.08, 0.36 if family != "compound_severe_but_recoverable" else 0.44))
        image *= illumination_field(image.shape, rng, strength)
        meta["illumination_strength"] = strength
    if family in {"halo_ghost_and_banding", "compound_severe_but_recoverable"}:
        wide_sigma = float(rng.uniform(3.0, 10.0))
        wide = cv2.GaussianBlur(image, (0, 0), wide_sigma, borderType=cv2.BORDER_REFLECT_101)
        halo_amp = float(rng.uniform(-0.14, 0.20))
        image += halo_amp * (image - wide)
        shift_x, shift_y = rng.integers(-12, 13, 2)
        ghost_amp = float(rng.uniform(0.01, 0.10))
        ghost = np.roll(np.roll(image, int(shift_y), axis=0), int(shift_x), axis=1)
        image = (1.0 - ghost_amp) * image + ghost_amp * ghost
        period = float(rng.uniform(45, 260))
        axis = np.arange(image.shape[1], dtype=np.float32)
        band_amp = float(rng.uniform(0.003, 0.035))
        image += band_amp * np.sin(2 * np.pi * axis / period + rng.uniform(0, 2 * np.pi))[None, :]
        meta.update(halo_sigma=wide_sigma, halo_amplitude=halo_amp, ghost_amplitude=ghost_amp, band_period=period, band_amplitude=band_amp)
    if family in {"local_boundary_fade", "compound_severe_but_recoverable"}:
        mask = mask_u8.astype(np.float32) / 255.0
        boundary = cv2.morphologyEx((mask_u8 >= 128).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8)).astype(np.float32)
        h, w = image.shape
        cx, cy = rng.uniform(0.15, 0.85, 2) * np.asarray([w, h])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        radius = float(rng.uniform(0.12, 0.35) * min(h, w))
        envelope = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / max(2 * radius * radius, 1.0))
        fade = cv2.GaussianBlur(boundary * envelope, (0, 0), rng.uniform(4.0, 14.0), borderType=cv2.BORDER_REFLECT_101)
        fade /= max(float(fade.max()), 1e-6)
        local_base = cv2.GaussianBlur(image, (0, 0), rng.uniform(8.0, 20.0), borderType=cv2.BORDER_REFLECT_101)
        amount = float(rng.uniform(0.35, 0.80))
        image = image * (1.0 - amount * fade) + local_base * (amount * fade)
        meta.update(boundary_fade_amount=amount, boundary_fade_radius=radius)
    if family == "low_contrast_and_uneven_illumination":
        mean = float(np.mean(image))
        contrast_scale = float(rng.uniform(0.42, 0.78))
        image = mean + contrast_scale * (image - mean)
        meta["contrast_scale"] = contrast_scale
    if family == "identity_and_near_identity":
        exposure, gamma = float(rng.uniform(0.985, 1.015)), float(rng.uniform(0.985, 1.015))
    elif family == "compound_severe_but_recoverable":
        exposure, gamma = float(rng.uniform(0.62, 1.38)), float(rng.uniform(0.72, 1.42))
    else:
        exposure, gamma = float(rng.uniform(0.78, 1.25)), float(rng.uniform(0.82, 1.22))
    image = np.power(np.clip(image * exposure, 0.0, 1.0), gamma)
    if family != "identity_and_near_identity":
        peak = float(rng.uniform(90, 800))
        image = noise_rng.poisson(np.clip(image, 0.0, 1.0) * peak).astype(np.float32) / peak
        meta["poisson_peak"] = peak
    if noise > 0:
        image += noise_rng.normal(0.0, noise, image.shape).astype(np.float32)
    column_amp = 0.0 if family == "identity_and_near_identity" else float(rng.uniform(0.0, 0.012))
    if column_amp:
        column = rng.normal(0.0, column_amp, (1, image.shape[1])).astype(np.float32)
        image += cv2.GaussianBlur(column, (0, 0), sigmaX=rng.uniform(0.5, 3.0))
    image = np.clip(image, 0.0, 1.0)
    contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
    repair = 0.0
    if family != "identity_and_near_identity" and contrast < 0.075:
        repair = min(0.30, (0.075 - contrast) / 0.075)
        image = (1.0 - repair) * image + repair * target
        contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
    meta.update(read_noise_sigma=noise, exposure=exposure, gamma=gamma, column_pattern_amplitude=column_amp, p95_p5_contrast=contrast, recoverability_repair_fraction=repair)
    return np.rint(image * 255.0).astype(np.uint8), meta


def split_assignments(role: str, role_cfg: dict[str, int], seed: int) -> dict[int, str]:
    total = int(role_cfg["total"])
    rng = np.random.default_rng(seed + sum(ord(ch) for ch in role) * 1009)
    order = rng.permutation(total).tolist()
    result: dict[int, str] = {}
    cursor = 0
    for split, count_key in (("train", "train"), ("validation", "validation"), ("internal_test", "internal_test")):
        for local_index in order[cursor:cursor + int(role_cfg[count_key])]:
            result[int(local_index)] = split
        cursor += int(role_cfg[count_key])
    return result


def build_degradation_assignment(plan: list[dict[str, Any]], quotas: dict[str, int], seed: int) -> dict[tuple[int, int], str]:
    remaining = Counter({name: int(count) for name, count in quotas.items()})
    assignment: dict[tuple[int, int], str] = {}
    identity_family = "identity_and_near_identity"
    identity_positions = [(scene["scene_index"], obs) for scene in plan if scene["role"] == "identity_and_detail_guard" for obs in range(4)]
    if len(identity_positions) > remaining[identity_family]:
        raise RuntimeError("Identity role exceeds the locked identity degradation quota")
    for position in identity_positions:
        assignment[position] = identity_family
        remaining[identity_family] -= 1
    rng = np.random.default_rng(seed + 4049)
    motion_scenes = [scene for scene in plan if scene["role"] == "signed_subpixel_motion"]
    rng.shuffle(motion_scenes)
    for scene in motion_scenes:
        names = [name for name, count in remaining.items() if count >= 4 and name != identity_family]
        if not names:
            raise RuntimeError("No four-observation quota remains for a signed-motion scene")
        weights = np.asarray([remaining[name] * DEGRADATION_WEIGHTS["signed_subpixel_motion"].get(name, 0.1) for name in names], dtype=np.float64)
        weights /= weights.sum()
        chosen = str(rng.choice(names, p=weights))
        for obs in range(4):
            assignment[(scene["scene_index"], obs)] = chosen
        remaining[chosen] -= 4
    positions = [(scene["scene_index"], obs, scene["role"]) for scene in plan if scene["role"] not in {"identity_and_detail_guard", "signed_subpixel_motion"} for obs in range(4)]
    rng.shuffle(positions)
    for scene_index, obs, role in positions:
        names = [name for name, count in remaining.items() if count > 0 and name != identity_family]
        if not names:
            raise RuntimeError("Degradation quota exhausted too early")
        weights = np.asarray([remaining[name] * DEGRADATION_WEIGHTS[role].get(name, 0.1) for name in names], dtype=np.float64)
        weights /= weights.sum()
        chosen = str(rng.choice(names, p=weights))
        assignment[(scene_index, obs)] = chosen
        remaining[chosen] -= 1
    if any(remaining.values()):
        raise RuntimeError(f"Unassigned degradation quota: {dict(remaining)}")
    return assignment


def motion_offsets(role: str, local_index: int, seed: int) -> list[tuple[float, float]]:
    if role != "signed_subpixel_motion":
        return [(0.0, 0.0)] * 4
    rng = np.random.default_rng(seed + 7001)
    bins = DESIGN["dataset"]["motion"]["magnitude_bins_px"]
    low, high = bins[local_index % len(bins)]
    magnitude = float(rng.uniform(low, high))
    directions = [(1.0, 0.0), (0.0, 1.0), (math.sqrt(0.5), math.sqrt(0.5)), (math.sqrt(0.5), -math.sqrt(0.5)), (0.6, 0.8), (0.8, -0.6)]
    ux, uy = directions[local_index % len(directions)]
    dx, dy = magnitude * ux, magnitude * uy
    return [(0.0, 0.0), (dx, dy), (-dx, -dy), (0.0, 0.0)]


def profile_plan(profile: str) -> tuple[list[dict[str, Any]], int, int, dict[str, int] | None, bool]:
    dataset = DESIGN["dataset"]
    if profile == "formal":
        canvas, scale, seed, holdout = int(dataset["canvas_size"]), int(dataset["label_supersample_factor"]), int(dataset["master_seed"]), False
        plan: list[dict[str, Any]] = []
        scene_index = 0
        for role, role_cfg in FORMAL_ROLES.items():
            assignments = split_assignments(role, role_cfg, seed)
            for local_index in range(int(role_cfg["total"])):
                plan.append({"scene_index": scene_index, "local_index": local_index, "role": role, "split": assignments[local_index]})
                scene_index += 1
        return plan, canvas, scale, dataset["degradation_observation_quotas"], holdout
    if profile == "holdout":
        canvas, scale, seed, holdout = int(dataset["canvas_size"]), int(dataset["label_supersample_factor"]), int(dataset["holdout"]["generator_seed"]), True
        plan = []
        scene_index = 0
        for role, count in HOLDOUT_ROLES.items():
            for local_index in range(count):
                plan.append({"scene_index": scene_index, "local_index": local_index, "role": role, "split": "locked_holdout"})
                scene_index += 1
        return plan, canvas, scale, None, holdout
    canvas, scale, seed, holdout = 512, int(dataset["label_supersample_factor"]), int(dataset["master_seed"]) + 88, False
    plan = []
    scene_index = 0
    for role in FORMAL_ROLES:
        for local_index, split in enumerate(("train", "validation", "internal_test")):
            plan.append({"scene_index": scene_index, "local_index": local_index, "role": role, "split": split})
            scene_index += 1
    return plan, canvas, scale, None, holdout


def package_for(profile: str) -> Path:
    return DATA_ROOT / {"smoke": "r88_smoke", "formal": "r88_formal", "holdout": "r88_locked_holdout"}[profile]


def build(profile: str) -> tuple[Path, dict[str, Any]]:
    if AUTH.get("authorization_status") != "authorized":
        raise RuntimeError("R88 execution is not authorized")
    package = package_for(profile)
    manifest_path = package / "manifest.json"
    if manifest_path.is_file():
        return package, json.loads(manifest_path.read_text(encoding="utf-8"))
    plan, canvas, scale, formal_quotas, holdout = profile_plan(profile)
    generator_sha = sha256_file(Path(__file__).resolve())
    seed = int(DESIGN["dataset"]["holdout"]["generator_seed"] if holdout else DESIGN["dataset"]["master_seed"] + (88 if profile == "smoke" else 0))
    if formal_quotas is not None:
        degradation_assignment = build_degradation_assignment(plan, formal_quotas, seed)
    else:
        families = list(DESIGN["dataset"]["degradation_observation_quotas"])
        degradation_assignment = {}
        rng = np.random.default_rng(seed + 5051)
        for scene in plan:
            shared_motion_family = str(rng.choice([name for name in families if name != "identity_and_near_identity"])) if scene["role"] == "signed_subpixel_motion" else None
            for obs in range(4):
                family = "identity_and_near_identity" if scene["role"] == "identity_and_detail_guard" else (shared_motion_family or str(rng.choice([name for name in families if name != "identity_and_near_identity"])))
                degradation_assignment[(scene["scene_index"], obs)] = family

    arrays_dir = package / "arrays"
    arrays_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    preview: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
    content_digest = hashlib.sha256()
    split_scenes: Counter[str] = Counter()
    split_observations: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    degradation_counts: Counter[str] = Counter()
    total = len(plan)

    for position, scene in enumerate(plan, start=1):
        scene_index, local_index, role, split = int(scene["scene_index"]), int(scene["local_index"]), str(scene["role"]), str(scene["split"])
        scene_seed = seed * 100000 + scene_index * 10007
        scene_id = f"{profile}:{role}:g{local_index:04d}:s{scene_seed}"
        scene_dir = arrays_dir / f"scene_{scene_index:04d}"
        scene_meta_path = scene_dir / "scene.json"
        if scene_meta_path.is_file():
            record = json.loads(scene_meta_path.read_text(encoding="utf-8"))
            if record.get("generator_sha256") != generator_sha:
                raise RuntimeError(f"Refusing to mix generator versions in {scene_meta_path}")
        else:
            high, coverage, geometry_meta = generate_geometry(role, scene_seed, canvas, scale, holdout=holdout)
            target, texture_meta = textured_target(coverage, role, scene_seed + 200003)
            sdf = compact_sdf(coverage)
            scene_dir.mkdir(parents=True, exist_ok=True)
            target_path, mask_path, sdf_path = scene_dir / "target.npy", scene_dir / "mask.npy", scene_dir / "sdf_q4.npy"
            save_npy_atomic(target_path, target)
            save_npy_atomic(mask_path, coverage)
            save_npy_atomic(sdf_path, sdf)
            observations = []
            for obs, (dx, dy) in enumerate(motion_offsets(role, local_index, scene_seed)):
                shifted_target = warp_u8(target, dx, dy, interpolation=cv2.INTER_LANCZOS4)
                shifted_mask = warp_u8(coverage, dx, dy, interpolation=cv2.INTER_LINEAR)
                family = degradation_assignment[(scene_index, obs)]
                noise_seed = scene_seed + 500000 + obs * 1009
                parameter_seed = scene_seed + 600000 if role == "signed_subpixel_motion" else scene_seed + 600000 + obs * 1013
                source, degradation_meta = degrade(shifted_target, shifted_mask, family, parameter_seed, noise_seed)
                source_path = scene_dir / f"source_o{obs}.npy"
                save_npy_atomic(source_path, source)
                observations.append({
                    "observation": obs,
                    "source": source_path.relative_to(package).as_posix(),
                    "source_sha256": array_sha256(source),
                    "degradation_family": family,
                    "degradation": degradation_meta,
                    "motion_dx_px": dx,
                    "motion_dy_px": dy,
                    "degradation_parameter_seed": parameter_seed,
                    "independent_noise_seed": noise_seed,
                })
                if len(preview) < 21 and obs == 0:
                    preview.append((role, source.copy(), target.copy(), coverage.copy()))
            record = {
                "scene_id": scene_id,
                "scene_index": scene_index,
                "local_index": local_index,
                "role": role,
                "split": split,
                "canvas_size": canvas,
                "supersample_factor": scale,
                "target": target_path.relative_to(package).as_posix(),
                "mask": mask_path.relative_to(package).as_posix(),
                "sdf_q4": sdf_path.relative_to(package).as_posix(),
                "target_sha256": array_sha256(target),
                "mask_sha256": array_sha256(coverage),
                "sdf_q4_sha256": array_sha256(sdf),
                "geometry": geometry_meta,
                "texture": texture_meta,
                "observations": observations,
                "procedural_only": True,
                "real_pixels_used": False,
                "sem_or_hs100mg_structure_used": False,
                "checkpoint_or_teacher_output_used": False,
                "generator_sha256": generator_sha,
            }
            json_dump(scene_meta_path, record)
            del high, coverage, target, sdf

        records.append(record)
        split_scenes[split] += 1
        split_observations[split] += len(record["observations"])
        role_counts[role] += 1
        for observation in record["observations"]:
            degradation_counts[observation["degradation_family"]] += 1
        content_digest.update(record["scene_id"].encode("utf-8"))
        for key in ("target_sha256", "mask_sha256", "sdf_q4_sha256"):
            content_digest.update(record[key].encode("ascii"))
        for observation in record["observations"]:
            content_digest.update(observation["source_sha256"].encode("ascii"))
        if position == 1 or position % 10 == 0 or position == total:
            progress = {"status": "building", "profile": profile, "completed_scenes": position, "total_scenes": total, "observations": position * 4}
            json_dump(package / "build_progress.json", progress)
            print(json.dumps(progress), flush=True)

    if profile == "formal":
        if dict(split_scenes) != {"train": 1024, "validation": 128, "internal_test": 128}:
            raise RuntimeError(f"Formal split mismatch: {dict(split_scenes)}")
        if dict(degradation_counts) != {key: int(value) for key, value in formal_quotas.items()}:
            raise RuntimeError(f"Formal degradation mismatch: {dict(degradation_counts)}")
    if profile == "holdout" and len(records) != int(DESIGN["dataset"]["holdout"]["new_locked_scene_count"]):
        raise RuntimeError("Holdout count mismatch")

    manifest = {
        "experiment_id": DESIGN["experiment_id"],
        "profile": profile,
        "generator_version": DESIGN["dataset"]["generator_version"],
        "generator_sha256": generator_sha,
        "generated_at": datetime.now().isoformat(),
        "master_seed": seed,
        "canvas_size": canvas,
        "label_supersample_factor": scale,
        "scene_count": len(records),
        "observations_per_scene": 4,
        "total_observations": len(records) * 4,
        "target_storage": "one_textured_latent_target_per_scene",
        "split_unit": "scene_id_and_texture_seed",
        "split_scene_counts": dict(split_scenes),
        "split_observation_counts": dict(split_observations),
        "role_scene_counts": dict(role_counts),
        "degradation_observation_counts": dict(degradation_counts),
        "content_sha256": content_digest.hexdigest(),
        "source_isolation": {
            "procedural_only": True,
            "real_microscope_pixels": False,
            "sem_pixels_or_structure": False,
            "hs100mg_pixels_or_structure": False,
            "measured_psf": False,
            "legacy_training_pairs": False,
            "checkpoint_or_teacher_output": False,
        },
        "records": records,
    }
    json_dump(manifest_path, manifest)
    json_dump(package / "build_progress.json", {"status": "complete", "profile": profile, "completed_scenes": len(records), "total_scenes": len(records), "observations": len(records) * 4})
    if profile != "holdout" and preview:
        tiles = []
        for role, source, target, mask in preview:
            crop_size = min(384, canvas)
            start = (canvas - crop_size) // 2
            crop = np.concatenate([source[start:start + crop_size, start:start + crop_size], target[start:start + crop_size, start:start + crop_size], mask[start:start + crop_size, start:start + crop_size]], axis=1)
            crop = cv2.resize(crop, (576, 192), interpolation=cv2.INTER_AREA)
            cv2.putText(crop, role[:28], (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, 255, 1, cv2.LINE_AA)
            tiles.append(crop)
        rows, blank = [], np.zeros_like(tiles[0])
        for index in range(0, len(tiles), 3):
            group = tiles[index:index + 3]
            rows.append(np.concatenate(group + [blank] * (3 - len(group)), axis=1))
        preview_dir = package / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(preview_dir / "dataset_preview.png"), np.concatenate(rows, axis=0))
    return package, manifest


def audit(package: Path, manifest: dict[str, Any], *, full_hash: bool) -> dict[str, Any]:
    missing: list[str] = []
    shape_failures: list[str] = []
    hash_failures: list[str] = []
    scene_splits: dict[str, set[str]] = defaultdict(set)
    motion_failures: list[str] = []
    generator_record_failures: list[str] = []
    fractional_samples: list[int] = []
    texture_samples: list[float] = []
    for index, record in enumerate(manifest["records"]):
        scene_splits[record["scene_id"]].add(record["split"])
        if record.get("generator_sha256") != manifest.get("generator_sha256"):
            generator_record_failures.append(record["scene_id"])
        paths = [("target", np.uint8, (manifest["canvas_size"], manifest["canvas_size"])), ("mask", np.uint8, (manifest["canvas_size"], manifest["canvas_size"])), ("sdf_q4", np.int8, (manifest["canvas_size"] // 4, manifest["canvas_size"] // 4))]
        for key, dtype, shape in paths:
            path = package / record[key]
            if not path.is_file():
                missing.append(record[key]); continue
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            if array.dtype != dtype or tuple(array.shape) != tuple(shape):
                shape_failures.append(record[key])
            if full_hash or index < 12 or index >= len(manifest["records"]) - 12:
                if array_sha256(np.asarray(array)) != record[f"{key}_sha256"]:
                    hash_failures.append(record[key])
        for observation in record["observations"]:
            path = package / observation["source"]
            if not path.is_file():
                missing.append(observation["source"]); continue
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            if array.dtype != np.uint8 or tuple(array.shape) != (manifest["canvas_size"], manifest["canvas_size"]):
                shape_failures.append(observation["source"])
            if full_hash or index < 12 or index >= len(manifest["records"]) - 12:
                if array_sha256(np.asarray(array)) != observation["source_sha256"]:
                    hash_failures.append(observation["source"])
        if record["role"] == "signed_subpixel_motion":
            offsets = [(round(float(obs["motion_dx_px"]), 7), round(float(obs["motion_dy_px"]), 7)) for obs in record["observations"]]
            families = {obs["degradation_family"] for obs in record["observations"]}
            parameter_seeds = {int(obs["degradation_parameter_seed"]) for obs in record["observations"]}
            noise_seeds = {int(obs["independent_noise_seed"]) for obs in record["observations"]}
            if offsets[0] != (0.0, 0.0) or offsets[3] != (0.0, 0.0) or offsets[2] != (-offsets[1][0], -offsets[1][1]) or len(families) != 1 or len(parameter_seeds) != 1 or len(noise_seeds) != 4:
                motion_failures.append(record["scene_id"])
        if index < 48 and record["role"] not in {"clean_contour_anchor"}:
            mask = np.asarray(np.load(package / record["mask"], mmap_mode="r", allow_pickle=False))
            target = np.asarray(np.load(package / record["target"], mmap_mode="r", allow_pickle=False))
            fractional_samples.append(int(np.count_nonzero((mask > 0) & (mask < 255))))
            binary = mask >= 128
            values = []
            if np.count_nonzero(binary) > 128:
                values.append(float(np.std(target[binary])))
            if np.count_nonzero(~binary) > 128:
                values.append(float(np.std(target[~binary])))
            if values:
                texture_samples.append(max(values))
    leaked = [scene for scene, splits in scene_splits.items() if len(splits) != 1]
    isolation = manifest.get("source_isolation", {})
    isolation_pass = isolation.get("procedural_only") and not any(value for key, value in isolation.items() if key != "procedural_only")
    generator_hash_pass = manifest.get("generator_sha256") == sha256_file(Path(__file__).resolve())
    report = {
        "passed": not missing and not shape_failures and not hash_failures and not leaked and not motion_failures and not generator_record_failures and isolation_pass and generator_hash_pass and (not fractional_samples or min(fractional_samples) > 0) and (not texture_samples or float(np.median(texture_samples)) >= 1.0),
        "profile": manifest["profile"],
        "scene_count": len(manifest["records"]),
        "total_observations": int(manifest["total_observations"]),
        "missing_count": len(missing),
        "shape_failure_count": len(shape_failures),
        "hash_failure_count": len(hash_failures),
        "scene_split_overlap_count": len(leaked),
        "motion_pair_failure_count": len(motion_failures),
        "generator_record_failure_count": len(generator_record_failures),
        "source_isolation_pass": bool(isolation_pass),
        "generator_hash_pass": bool(generator_hash_pass),
        "sampled_fractional_coverage_min": min(fractional_samples) if fractional_samples else None,
        "sampled_texture_std_median_gray": float(np.median(texture_samples)) if texture_samples else None,
        "full_array_hash_audit": bool(full_hash),
        "content_sha256": manifest["content_sha256"],
    }
    json_dump(package / "audit.json", report)
    if not report["passed"]:
        raise RuntimeError(json.dumps(report, indent=2))
    return report


def seal_holdout(package: Path, manifest: dict[str, Any], audit_report: dict[str, Any]) -> dict[str, Any]:
    manifest_path = package / "manifest.json"
    seal = {
        "experiment_id": DESIGN["experiment_id"],
        "status": "sealed_unread_until_checkpoint_frozen",
        "sealed_at": datetime.now().isoformat(),
        "manifest_sha256": sha256_file(manifest_path),
        "content_sha256": manifest["content_sha256"],
        "scene_count": manifest["scene_count"],
        "total_observations": manifest["total_observations"],
        "audit_passed": bool(audit_report["passed"]),
        "training_access_allowed": False,
        "checkpoint_selection_access_allowed": False,
    }
    json_dump(package / "SEALED.json", seal)
    return seal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("smoke", "formal", "holdout"), default="smoke")
    parser.add_argument("--full-hash-audit", action="store_true")
    args = parser.parse_args()
    if args.profile in {"formal", "holdout"} and not args.full_hash_audit:
        raise RuntimeError("Formal and holdout generation require --full-hash-audit")
    package, manifest = build(args.profile)
    report = audit(package, manifest, full_hash=args.full_hash_audit)
    seal = seal_holdout(package, manifest, report) if args.profile == "holdout" else None
    print(json.dumps({"package": str(package), "manifest": str(package / "manifest.json"), "audit": report, "seal": seal}, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
