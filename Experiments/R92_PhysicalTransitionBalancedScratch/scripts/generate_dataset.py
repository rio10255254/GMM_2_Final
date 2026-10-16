"""Generate the procedural-latent R92 datasets.

Each scene stores one 8x-antialiased geometry mask, one textured latent target,
one compact signed-distance map, and four degraded observations.  The dedicated
exposure-coherent role follows a continuous four-view photometric path while
sharing recoverable texture and optics with independent nuisance noise.
No SEM, measured sample contour, measured PSF, model output, or checkpoint is
read.  Anonymous aggregate optical statistics are loaded, but no real pixels,
positions, phases or structures are copied into a training pair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
AUTH_PATH = ROOT / "config" / "execution_authorization.json"
OPTICAL_PATH = ROOT / "config" / "optical_statistics.json"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
AUTH = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
if not OPTICAL_PATH.is_file():
    raise FileNotFoundError("R92 requires config/optical_statistics.json before dataset generation")
OPTICAL = json.loads(OPTICAL_PATH.read_text(encoding="utf-8"))
OPTICAL_AGGREGATE = OPTICAL["aggregate"]
DATA_ROOT = ROOT / "data"

FORMAL_ROLES = DESIGN["dataset"]["roles"]
HOLDOUT_ROLES = {
    "textured_general_geometry": 64,
    "identity_and_detail_guard": 40,
    "exposure_coherent_bundle": 64,
    "difficult_contour": 40,
    "cross_tile_and_dense": 20,
    "signed_subpixel_motion": 20,
    "clean_contour_anchor": 8,
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
    "exposure_coherent_bundle": {
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
    for attempt in range(100):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 99:
                raise
            time.sleep(0.05)


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
        elif role == "exposure_coherent_bundle":
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
        optical_scale = float(np.clip(OPTICAL_AGGREGATE["estimated_texture_correlation_px"] / 3.0, 0.65, 1.8))
        sx, sy = (rng.uniform(0.6, 1.4) * optical_scale, rng.uniform(2.0, 7.0) * optical_scale) if rng.random() < 0.5 else (rng.uniform(2.0, 7.0) * optical_scale, rng.uniform(0.6, 1.4) * optical_scale)
        field = cv2.GaussianBlur(field, (0, 0), sigmaX=float(sx), sigmaY=float(sy), borderType=cv2.BORDER_REFLECT_101)
    elif family == "band_limited_particles":
        field = np.zeros((canvas, canvas), np.float32)
        for _ in range(int(rng.integers(100, 500))):
            x, y = rng.integers(0, canvas, 2)
            cv2.circle(field, (int(x), int(y)), int(rng.integers(1, 7)), float(rng.uniform(-1, 1)), -1, cv2.LINE_AA)
        optical_scale = float(np.clip(OPTICAL_AGGREGATE["estimated_texture_correlation_px"] / 3.0, 0.65, 1.8))
        field = cv2.GaussianBlur(field, (0, 0), rng.uniform(0.8, 2.8) * optical_scale, borderType=cv2.BORDER_REFLECT_101)
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
    elif family == "directional_fibers":
        field = 0.20 * coarse(72)
        angle = float(rng.uniform(0, np.pi))
        length = int(canvas * 0.16)
        for _ in range(int(rng.integers(45, 130))):
            cx, cy = rng.integers(0, canvas, 2)
            local_angle = angle + float(rng.normal(0.0, 0.14))
            dx, dy = int(round(math.cos(local_angle) * length)), int(round(math.sin(local_angle) * length))
            value = float(rng.uniform(-1.2, 1.2))
            cv2.line(field, (int(cx - dx), int(cy - dy)), (int(cx + dx), int(cy + dy)), value, int(rng.integers(1, 4)), cv2.LINE_AA)
        field = cv2.GaussianBlur(field, (0, 0), sigmaX=float(rng.uniform(0.6, 1.8)), borderType=cv2.BORDER_REFLECT_101)
    elif family == "porous_clusters":
        field = 0.15 * coarse(40)
        for _ in range(int(rng.integers(90, 280))):
            x, y = rng.integers(0, canvas, 2)
            radius = int(rng.integers(1, 10))
            cv2.circle(field, (int(x), int(y)), radius, float(rng.uniform(-1.4, 0.45)), -1, cv2.LINE_AA)
        field = cv2.GaussianBlur(field, (0, 0), sigmaX=float(rng.uniform(0.5, 1.5)), borderType=cv2.BORDER_REFLECT_101)
    elif family == "weak_repeated_lines":
        yy, xx = np.mgrid[0:canvas, 0:canvas].astype(np.float32)
        angle = float(rng.uniform(0, np.pi))
        coordinate = math.cos(angle) * xx + math.sin(angle) * yy
        period = float(rng.uniform(7.0, 42.0))
        phase = float(rng.uniform(0, 2 * np.pi))
        field = np.sin(2 * np.pi * coordinate / period + phase)
        field += 0.35 * np.sin(2 * np.pi * coordinate / (period * rng.uniform(1.7, 2.6)) + rng.uniform(0, 2 * np.pi))
        field *= 0.75 + 0.25 * np.tanh(coarse(18))
    elif family == "granular_microtexture":
        grain = rng.normal(0.0, 1.0, (canvas, canvas)).astype(np.float32)
        broad = cv2.GaussianBlur(grain, (0, 0), sigmaX=float(rng.uniform(1.8, 4.2)), borderType=cv2.BORDER_REFLECT_101)
        field = grain - broad + 0.18 * coarse(90)
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
    "directional_fibers",
    "porous_clusters",
    "weak_repeated_lines",
    "granular_microtexture",
    "fixed_pattern_sensor_texture",
]


def textured_target(coverage: np.ndarray, role: str, seed: int, *, holdout: bool = False) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    canvas = int(coverage.shape[0])
    bright = bool(rng.integers(0, 2))
    if role == "identity_and_detail_guard":
        separation = float(rng.uniform(0.54, 0.78))
    elif role == "exposure_coherent_bundle":
        separation = float(rng.uniform(0.42, 0.60))
    elif role in {"difficult_contour", "cross_tile_and_dense"}:
        separation = float(rng.uniform(0.46, 0.66))
    else:
        separation = float(rng.uniform(0.48, 0.70))
    center = float(rng.uniform(0.43, 0.57))
    low_mean, high_mean = center - 0.5 * separation, center + 0.5 * separation
    if bright:
        bg_mean, fg_mean = low_mean, high_mean
    else:
        bg_mean, fg_mean = high_mean, low_mean
    family_fg = str(rng.choice(TEXTURE_FAMILIES))
    family_bg = str(rng.choice(TEXTURE_FAMILIES))
    family_shared = str(rng.choice(TEXTURE_FAMILIES))
    shared = random_field(rng, canvas, family_shared)
    foreground_texture = random_field(rng, canvas, family_fg)
    background_texture = random_field(rng, canvas, family_bg)
    if role == "clean_contour_anchor":
        amp_fg, amp_bg = float(rng.uniform(0.006, 0.025)), float(rng.uniform(0.004, 0.018))
    elif role == "identity_and_detail_guard":
        amp_fg, amp_bg = float(rng.uniform(0.040, 0.125)), float(rng.uniform(0.030, 0.100))
    elif role == "textured_general_geometry":
        amp_fg, amp_bg = float(rng.uniform(0.038, 0.135)), float(rng.uniform(0.028, 0.110))
    elif role == "exposure_coherent_bundle":
        amp_fg, amp_bg = float(rng.uniform(0.028, 0.115)), float(rng.uniform(0.020, 0.090))
    else:
        amp_fg, amp_bg = float(rng.uniform(0.018, 0.10)), float(rng.uniform(0.012, 0.075))
    shared_fraction = float(rng.uniform(0.15, 0.65))
    modulation = 1.0 + 0.30 * random_field(rng, canvas, "low_frequency_material_variation")
    foreground_pattern = (shared_fraction * shared + (1.0 - shared_fraction) * foreground_texture) * modulation
    background_pattern = (shared_fraction * shared + (1.0 - shared_fraction) * background_texture) * modulation
    foreground = fg_mean + amp_fg * foreground_pattern
    background = bg_mean + amp_bg * background_pattern
    transition = DESIGN["dataset"]["physical_transition_profile"]
    if holdout:
        boundary_fraction = float(rng.uniform(*transition["holdout_range"]))
    else:
        boundary_fraction = float(np.clip(
            rng.normal(float(transition["development_center"]), float(transition["development_spread"])),
            *transition["boundary_intensity_fraction_range"],
        ))
    alpha_geometry = coverage.astype(np.float32) / 255.0
    epsilon = 1e-5
    clipped_alpha = np.clip(alpha_geometry, epsilon, 1.0 - epsilon)
    transition_bias = math.log(boundary_fraction / (1.0 - boundary_fraction))
    alpha = 1.0 / (1.0 + np.exp(-(np.log(clipped_alpha / (1.0 - clipped_alpha)) + transition_bias)))
    alpha[alpha_geometry <= 0.0] = 0.0
    alpha[alpha_geometry >= 1.0] = 1.0
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
        "local_texture_modulation": True,
        "physical_boundary_intensity_fraction": boundary_fraction,
        "physical_transition_method": transition["method"],
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


def degrade(
    target_u8: np.ndarray,
    mask_u8: np.ndarray,
    family: str,
    parameter_seed: int,
    noise_seed: int,
    *,
    photometric_override: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(parameter_seed)
    noise_rng = np.random.default_rng(noise_seed)
    target = target_u8.astype(np.float32) / 255.0
    image = target.copy()
    meta: dict[str, Any] = {"family": family}
    measured_noise_p10 = float(OPTICAL_AGGREGATE["noise_sigma_normalized"]["p10"])
    measured_noise_p90 = float(OPTICAL_AGGREGATE["noise_sigma_normalized"]["p90"])
    ranges = {
        "identity_and_near_identity": ((0.0, 0.22), (0.0, measured_noise_p10 * 0.25)),
        "standard_blur_and_noise": ((0.35, 1.8), (measured_noise_p10 * 0.35, measured_noise_p90 * 1.55)),
        "defocus_and_motion_blur": ((0.8, 3.0), (measured_noise_p10 * 0.45, measured_noise_p90 * 1.85)),
        "low_contrast_and_uneven_illumination": ((0.45, 2.4), (measured_noise_p10 * 0.45, measured_noise_p90 * 1.95)),
        "halo_ghost_and_banding": ((0.7, 2.7), (measured_noise_p10 * 0.45, measured_noise_p90 * 2.10)),
        "local_boundary_fade": ((0.6, 2.5), (measured_noise_p10 * 0.40, measured_noise_p90 * 1.90)),
        "compound_severe_but_recoverable": ((1.3, 3.6), (measured_noise_p10 * 0.75, measured_noise_p90 * 2.45)),
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
        measured_illumination = float(OPTICAL_AGGREGATE["illumination_std_normalized"]["p50"])
        regular_max = float(np.clip(measured_illumination * 3.2, 0.18, 0.38))
        strength = float(rng.uniform(0.06, regular_max if family != "compound_severe_but_recoverable" else min(0.44, regular_max * 1.2)))
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
        binary = mask_u8 >= 128
        foreground_level = float(np.mean(image[binary])) if np.any(binary) else float(np.mean(image))
        background_level = float(np.mean(image[~binary])) if np.any(~binary) else float(np.mean(image))
        mean = 0.5 * (foreground_level + background_level)
        contrast_scale = float(rng.uniform(0.42, 0.78))
        image = mean + contrast_scale * (image - mean)
        meta["contrast_scale"] = contrast_scale
    if photometric_override is not None:
        exposure = float(photometric_override["exposure"])
        gamma = float(photometric_override["gamma"])
    elif family == "identity_and_near_identity":
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
    measured_column = float(OPTICAL_AGGREGATE["column_pattern_sigma_normalized"]["p90"])
    column_amp = 0.0 if family == "identity_and_near_identity" else float(rng.uniform(0.0, min(0.014, measured_column * 1.8)))
    if column_amp:
        column = rng.normal(0.0, column_amp, (1, image.shape[1])).astype(np.float32)
        image += cv2.GaussianBlur(column, (0, 0), sigmaX=rng.uniform(0.5, 3.0))
    image = np.clip(image, 0.0, 1.0)
    requested_contrast_gray = None if photometric_override is None else photometric_override.get("source_contrast_gray")
    if requested_contrast_gray is not None:
        current_contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
        requested_contrast = float(requested_contrast_gray) / 255.0
        if current_contrast > 1e-6:
            binary = mask_u8 >= 128
            current_foreground = float(np.mean(image[binary])) if np.any(binary) else float(np.mean(image))
            current_background = float(np.mean(image[~binary])) if np.any(~binary) else float(np.mean(image))
            current_center = 0.5 * (current_foreground + current_background)
            target_foreground = float(np.mean(target[binary])) if np.any(binary) else float(np.mean(target))
            target_background = float(np.mean(target[~binary])) if np.any(~binary) else float(np.mean(target))
            target_center = 0.5 * (target_foreground + target_background)
            source_center = float(np.clip(current_center, target_center - 0.08, target_center + 0.08))
            image = source_center + (requested_contrast / current_contrast) * (image - current_center)
            image = np.clip(image, 0.0, 1.0)
    binary = mask_u8 >= 128
    current_foreground = float(np.mean(image[binary])) if np.any(binary) else float(np.mean(image))
    current_background = float(np.mean(image[~binary])) if np.any(~binary) else float(np.mean(image))
    current_center = 0.5 * (current_foreground + current_background)
    target_foreground = float(np.mean(target[binary])) if np.any(binary) else float(np.mean(target))
    target_background = float(np.mean(target[~binary])) if np.any(~binary) else float(np.mean(target))
    target_center = 0.5 * (target_foreground + target_background)
    projected_center = float(np.clip(current_center, target_center - 0.12, target_center + 0.12))
    brightness_center_projection = projected_center - current_center
    if abs(brightness_center_projection) > 1e-8:
        image = np.clip(image + brightness_center_projection, 0.0, 1.0)
    contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
    source_only_contrast_scale = 1.0
    minimum_contrast = float(DESIGN["dataset"]["recoverability_contract"]["minimum_nonidentity_contrast"])
    if family != "identity_and_near_identity" and contrast < minimum_contrast and contrast > 1e-6:
        source_only_contrast_scale = minimum_contrast / contrast
        source_center = float(np.median(image))
        image = np.clip(source_center + source_only_contrast_scale * (image - source_center), 0.0, 1.0)
        contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
    maximum_gap = float(DESIGN["dataset"]["recoverability_contract"]["maximum_source_target_gap"])
    recoverability = DESIGN["dataset"]["recoverability_contract"]
    delta = image - target
    robust_gap = float(np.percentile(np.abs(delta), float(recoverability["robust_gap_percentile"])))
    fraction_above_bound = float(np.mean(np.abs(delta) > maximum_gap))
    global_scale = 1.0
    recoverability_clip_fraction = 0.0
    meta.update(
        read_noise_sigma=noise,
        exposure=exposure,
        gamma=gamma,
        column_pattern_amplitude=column_amp,
        p95_p5_contrast=contrast,
        recoverability_repair_fraction=0.0,
        source_only_contrast_scale=source_only_contrast_scale,
        brightness_center_projection=brightness_center_projection,
        requested_source_contrast_gray=requested_contrast_gray,
        recoverability_robust_gap_before_scale=robust_gap,
        recoverability_global_scale=global_scale,
        recoverability_clip_fraction=recoverability_clip_fraction,
        recoverability_fraction_above_model_bound=fraction_above_bound,
        maximum_required_correction=maximum_gap,
        optical_statistics_sha256=sha256_file(OPTICAL_PATH),
        exposure_coherent_profile=(None if photometric_override is None else str(photometric_override["label"])),
        exposure_path_position=(None if photometric_override is None else float(photometric_override["path_position"])),
    )
    return np.rint(image * 255.0).astype(np.uint8), meta


def coherent_exposure_profiles(scene_seed: int) -> list[dict[str, Any]]:
    """Return four continuous positions on one randomized photometric path."""
    rng = np.random.default_rng(scene_seed + 620003)
    config = DESIGN["dataset"]["continuous_exposure_path"]
    low_exposure = float(rng.uniform(*config["dark_exposure_range"]))
    high_exposure = float(rng.uniform(*config["bright_exposure_range"]))
    low_gamma = float(rng.uniform(*config["dark_gamma_range"]))
    high_gamma = float(rng.uniform(*config["bright_gamma_range"]))
    positions = [0.0]
    positions.extend(float(rng.uniform(*bounds)) for bounds in config["inner_path_position_ranges"])
    positions.append(1.0)
    jitter = float(config["photometric_jitter_fraction"])
    profiles: list[dict[str, Any]] = []
    contrast_bands = list(config["source_contrast_gray_bands"])
    for label, position, contrast_band in zip(config["labels"], positions, contrast_bands):
        exposure = low_exposure + position * (high_exposure - low_exposure)
        gamma = low_gamma + position * (high_gamma - low_gamma)
        exposure *= float(rng.uniform(1.0 - jitter, 1.0 + jitter))
        gamma *= float(rng.uniform(1.0 - jitter, 1.0 + jitter))
        profiles.append({
            "label": str(label),
            "exposure": float(np.clip(exposure, 0.58, 1.38)),
            "gamma": float(np.clip(gamma, 0.76, 1.34)),
            "path_position": float(position),
            "source_contrast_gray": float(rng.uniform(*contrast_band)),
            "source_contrast_gray_band": [float(contrast_band[0]), float(contrast_band[1])],
        })
    # Rotate the order so observation index never becomes a shortcut for one
    # exposure while preserving one instance of every profile in each scene.
    rotation = int(rng.integers(0, len(profiles)))
    return profiles[rotation:] + profiles[:rotation]


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
    grouped_scenes = [scene for scene in plan if scene["role"] in {"exposure_coherent_bundle", "signed_subpixel_motion"}]
    rng.shuffle(grouped_scenes)
    for scene in grouped_scenes:
        role = str(scene["role"])
        names = [name for name, count in remaining.items() if count >= 4 and name != identity_family]
        if not names:
            raise RuntimeError(f"No four-observation quota remains for grouped role {role}")
        weights = np.asarray([remaining[name] * DEGRADATION_WEIGHTS[role].get(name, 0.1) for name in names], dtype=np.float64)
        weights /= weights.sum()
        chosen = str(rng.choice(names, p=weights))
        for obs in range(4):
            assignment[(scene["scene_index"], obs)] = chosen
        remaining[chosen] -= 4
    positions = [(scene["scene_index"], obs, scene["role"]) for scene in plan if scene["role"] not in {"identity_and_detail_guard", "exposure_coherent_bundle", "signed_subpixel_motion"} for obs in range(4)]
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
    return DATA_ROOT / {"smoke": "r92_smoke", "formal": "r92_formal", "holdout": "r92_locked_holdout"}[profile]


def build(profile: str) -> tuple[Path, dict[str, Any]]:
    authorization = str(AUTH.get("authorization_status"))
    if authorization not in {"setup_and_smoke_authorized", "formal_authorized"}:
        raise RuntimeError("R92 setup or formal execution is not authorized")
    if profile == "formal" and not AUTH.get("formal_dataset_generation_authorized"):
        raise RuntimeError("R92 formal dataset generation is not authorized")
    if profile == "holdout" and not AUTH.get("locked_holdout_generation_authorized"):
        raise RuntimeError("R92 locked holdout generation is not authorized")
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
            shared_group_family = str(rng.choice([name for name in families if name != "identity_and_near_identity"])) if scene["role"] in {"exposure_coherent_bundle", "signed_subpixel_motion"} else None
            for obs in range(4):
                family = "identity_and_near_identity" if scene["role"] == "identity_and_detail_guard" else (shared_group_family or str(rng.choice([name for name in families if name != "identity_and_near_identity"])))
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
            if (
                record.get("generator_sha256") != generator_sha
                or record.get("optical_statistics_sha256") != sha256_file(OPTICAL_PATH)
            ):
                raise RuntimeError(f"Refusing to mix generator versions in {scene_meta_path}")
        else:
            high, coverage, geometry_meta = generate_geometry(role, scene_seed, canvas, scale, holdout=holdout)
            target, texture_meta = textured_target(coverage, role, scene_seed + 200003, holdout=holdout)
            sdf = compact_sdf(coverage)
            scene_dir.mkdir(parents=True, exist_ok=True)
            target_path, mask_path, sdf_path = scene_dir / "target.npy", scene_dir / "mask.npy", scene_dir / "sdf_q4.npy"
            save_npy_atomic(target_path, target)
            save_npy_atomic(mask_path, coverage)
            save_npy_atomic(sdf_path, sdf)
            observations = []
            exposure_profiles = coherent_exposure_profiles(scene_seed) if role == "exposure_coherent_bundle" else [None] * 4
            for obs, (dx, dy) in enumerate(motion_offsets(role, local_index, scene_seed)):
                shifted_target = warp_u8(target, dx, dy, interpolation=cv2.INTER_LANCZOS4)
                shifted_mask = warp_u8(coverage, dx, dy, interpolation=cv2.INTER_LINEAR)
                family = degradation_assignment[(scene_index, obs)]
                noise_seed = scene_seed + 500000 + obs * 1009
                parameter_seed = scene_seed + 600000 if role in {"exposure_coherent_bundle", "signed_subpixel_motion"} else scene_seed + 600000 + obs * 1013
                source, degradation_meta = degrade(
                    shifted_target,
                    shifted_mask,
                    family,
                    parameter_seed,
                    noise_seed,
                    photometric_override=exposure_profiles[obs],
                )
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
                "optical_statistics_sha256": sha256_file(OPTICAL_PATH),
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
        expected_splits = {
            "train": int(DESIGN["dataset"]["split_counts"]["train_scenes"]),
            "validation": int(DESIGN["dataset"]["split_counts"]["validation_scenes"]),
            "internal_test": int(DESIGN["dataset"]["split_counts"]["internal_test_scenes"]),
        }
        if dict(split_scenes) != expected_splits:
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
            "real_optical_aggregate_statistics": True,
            "optical_statistics_sha256": sha256_file(OPTICAL_PATH),
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
    exposure_bundle_failures: list[str] = []
    generator_record_failures: list[str] = []
    recoverability_failures: list[str] = []
    recoverability_metadata_failures: list[str] = []
    recoverability_clip_fractions: list[float] = []
    recoverability_global_scales: list[float] = []
    recoverability_robust_gaps: list[float] = []
    recoverability_bound_fractions: list[float] = []
    transition_profile_failures: list[str] = []
    exposure_contrast_failures: list[str] = []
    transition_fractions: list[float] = []
    exposure_contrasts_gray: list[float] = []
    fractional_samples: list[int] = []
    texture_samples: list[float] = []
    for index, record in enumerate(manifest["records"]):
        scene_splits[record["scene_id"]].add(record["split"])
        if (
            record.get("generator_sha256") != manifest.get("generator_sha256")
            or record.get("optical_statistics_sha256") != sha256_file(OPTICAL_PATH)
        ):
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
        target_for_gap = np.asarray(np.load(package / record["target"], mmap_mode="r", allow_pickle=False))
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
            shifted_target = warp_u8(
                target_for_gap,
                float(observation["motion_dx_px"]),
                float(observation["motion_dy_px"]),
                interpolation=cv2.INTER_LANCZOS4,
            )
            recoverability_cfg = DESIGN["dataset"]["recoverability_contract"]
            allowed_gap = float(recoverability_cfg["maximum_source_target_gap"]) + 1.5 / 255.0
            absolute_gap = np.abs(np.asarray(array, dtype=np.float32) - shifted_target.astype(np.float32)) / 255.0
            observed_gap = float(np.percentile(absolute_gap, float(recoverability_cfg["robust_gap_percentile"])))
            observed_fraction = float(np.mean(absolute_gap > float(recoverability_cfg["maximum_source_target_gap"])))
            recoverability_robust_gaps.append(observed_gap)
            recoverability_bound_fractions.append(observed_fraction)
            if observed_gap > allowed_gap or observed_fraction > float(recoverability_cfg["maximum_fraction_above_model_bound"]) + 1e-9:
                recoverability_failures.append(observation["source"])
            degradation = observation.get("degradation", {})
            clip_fraction = float(degradation.get("recoverability_clip_fraction", 1.0))
            global_scale = float(degradation.get("recoverability_global_scale", 0.0))
            recoverability_clip_fractions.append(clip_fraction)
            recoverability_global_scales.append(global_scale)
            if (
                clip_fraction > float(recoverability_cfg["maximum_final_pixelwise_clip_fraction"]) + 1e-9
                or global_scale < float(recoverability_cfg["minimum_global_degradation_scale"]) - 1e-9
                or float(degradation.get("recoverability_repair_fraction", 1.0)) != 0.0
            ):
                recoverability_metadata_failures.append(observation["source"])
        transition_fraction = float(record.get("texture", {}).get("physical_boundary_intensity_fraction", -1.0))
        transition_fractions.append(transition_fraction)
        transition_cfg = DESIGN["dataset"]["physical_transition_profile"]
        transition_range = transition_cfg["holdout_range"] if manifest["profile"] == "holdout" else transition_cfg["boundary_intensity_fraction_range"]
        if not float(transition_range[0]) <= transition_fraction <= float(transition_range[1]):
            transition_profile_failures.append(record["scene_id"])
        if record["role"] == "signed_subpixel_motion":
            offsets = [(round(float(obs["motion_dx_px"]), 7), round(float(obs["motion_dy_px"]), 7)) for obs in record["observations"]]
            families = {obs["degradation_family"] for obs in record["observations"]}
            parameter_seeds = {int(obs["degradation_parameter_seed"]) for obs in record["observations"]}
            noise_seeds = {int(obs["independent_noise_seed"]) for obs in record["observations"]}
            if offsets[0] != (0.0, 0.0) or offsets[3] != (0.0, 0.0) or offsets[2] != (-offsets[1][0], -offsets[1][1]) or len(families) != 1 or len(parameter_seeds) != 1 or len(noise_seeds) != 4:
                motion_failures.append(record["scene_id"])
        if record["role"] == "exposure_coherent_bundle":
            families = {obs["degradation_family"] for obs in record["observations"]}
            parameter_seeds = {int(obs["degradation_parameter_seed"]) for obs in record["observations"]}
            noise_seeds = {int(obs["independent_noise_seed"]) for obs in record["observations"]}
            profile_labels = {str(obs["degradation"].get("exposure_coherent_profile")) for obs in record["observations"]}
            exposure_config = DESIGN["dataset"]["continuous_exposure_path"]
            expected_labels = {str(label) for label in exposure_config["labels"]}
            exposures = [float(obs["degradation"].get("exposure", 1.0)) for obs in record["observations"]]
            positions = {float(obs["degradation"].get("exposure_path_position", -1.0)) for obs in record["observations"]}
            contrast_rows = []
            for obs in record["observations"]:
                measured = 255.0 * float(obs["degradation"].get("p95_p5_contrast", -1.0))
                requested = float(obs["degradation"].get("requested_source_contrast_gray", -1.0))
                contrast_rows.append((measured, requested))
                exposure_contrasts_gray.append(measured)
            span_ok = max(exposures) - min(exposures) >= float(exposure_config["minimum_exposure_span"])
            transition_ok = any(0.82 <= exposure <= 1.16 for exposure in exposures)
            contrast_ok = all(requested > 0.0 and abs(measured - requested) <= 12.0 for measured, requested in contrast_rows)
            if not contrast_ok:
                exposure_contrast_failures.append(record["scene_id"])
            if len(families) != 1 or len(parameter_seeds) != 1 or len(noise_seeds) != 4 or profile_labels != expected_labels or len(positions) != 4 or not span_ok or not transition_ok or not contrast_ok:
                exposure_bundle_failures.append(record["scene_id"])
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
    isolation_pass = bool(
        isolation.get("procedural_only")
        and isolation.get("real_optical_aggregate_statistics")
        and isolation.get("optical_statistics_sha256") == sha256_file(OPTICAL_PATH)
        and not isolation.get("real_microscope_pixels")
        and not isolation.get("sem_pixels_or_structure")
        and not isolation.get("hs100mg_pixels_or_structure")
        and not isolation.get("measured_psf")
        and not isolation.get("legacy_training_pairs")
        and not isolation.get("checkpoint_or_teacher_output")
    )
    generator_hash_pass = manifest.get("generator_sha256") == sha256_file(Path(__file__).resolve())
    report = {
        "passed": not missing and not shape_failures and not hash_failures and not leaked and not motion_failures and not exposure_bundle_failures and not generator_record_failures and not recoverability_failures and not recoverability_metadata_failures and not transition_profile_failures and not exposure_contrast_failures and isolation_pass and generator_hash_pass and (not fractional_samples or min(fractional_samples) > 0) and (not texture_samples or float(np.median(texture_samples)) >= 1.0),
        "profile": manifest["profile"],
        "scene_count": len(manifest["records"]),
        "total_observations": int(manifest["total_observations"]),
        "missing_count": len(missing),
        "shape_failure_count": len(shape_failures),
        "hash_failure_count": len(hash_failures),
        "scene_split_overlap_count": len(leaked),
        "motion_pair_failure_count": len(motion_failures),
        "exposure_bundle_failure_count": len(exposure_bundle_failures),
        "generator_record_failure_count": len(generator_record_failures),
        "recoverability_failure_count": len(recoverability_failures),
        "recoverability_metadata_failure_count": len(recoverability_metadata_failures),
        "physical_transition_profile_failure_count": len(transition_profile_failures),
        "exposure_contrast_failure_count": len(exposure_contrast_failures),
        "recoverability_final_clip_fraction_max": max(recoverability_clip_fractions) if recoverability_clip_fractions else None,
        "recoverability_final_clip_fraction_p99": float(np.percentile(recoverability_clip_fractions, 99)) if recoverability_clip_fractions else None,
        "recoverability_global_scale_min": min(recoverability_global_scales) if recoverability_global_scales else None,
        "recoverability_robust_gap_p99": float(np.percentile(recoverability_robust_gaps, 99)) if recoverability_robust_gaps else None,
        "recoverability_fraction_above_bound_max": max(recoverability_bound_fractions) if recoverability_bound_fractions else None,
        "physical_transition_fraction_min": min(transition_fractions) if transition_fractions else None,
        "physical_transition_fraction_median": float(np.median(transition_fractions)) if transition_fractions else None,
        "physical_transition_fraction_max": max(transition_fractions) if transition_fractions else None,
        "exposure_contrast_gray_min": min(exposure_contrasts_gray) if exposure_contrasts_gray else None,
        "exposure_contrast_gray_median": float(np.median(exposure_contrasts_gray)) if exposure_contrasts_gray else None,
        "exposure_contrast_gray_max": max(exposure_contrasts_gray) if exposure_contrasts_gray else None,
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
