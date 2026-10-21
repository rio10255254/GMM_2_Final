"""Build the R87 large-scene procedural dataset.

The package contains no imported image pixels, measured geometry, measured PSF,
model output, or checkpoint data.  Geometry is rasterized at 8x and reduced by
area averaging before any synthetic optical degradation is applied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
CONFIG = json.loads((EXPERIMENT_DIR / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA_ROOT = EXPERIMENT_DIR / "data"

ROLE_COUNTS = {
    "basic_geometry": 160,
    "noncircular_complex": 200,
    "thin_and_defect": 160,
    "dense_periodic": 200,
    "multiscale_field": 160,
    "cross_tile_large": 240,
    "texture_and_polarity": 80,
    "known_subpixel_motion": 80,
}
DEGRADATION_SCHEDULE = (
    ["standard_recoverable"] * 6
    + ["defocus_and_motion"] * 4
    + ["illumination_and_exposure"] * 3
    + ["halo_ghost_and_banding"] * 3
    + ["severe_but_recoverable"] * 2
    + ["identity_and_near_identity"] * 2
)


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


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(memoryview(np.ascontiguousarray(array)).cast("B")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def polygon_points(cx: float, cy: float, radius: float, sides: int, angle: float, scale: int) -> np.ndarray:
    theta = angle + np.arange(sides, dtype=np.float64) * (2.0 * np.pi / sides)
    points = np.column_stack([cx + radius * np.cos(theta), cy + radius * np.sin(theta)])
    return np.rint(points * scale).astype(np.int32)


def star_points(cx: float, cy: float, outer: float, inner: float, tips: int, angle: float, scale: int) -> np.ndarray:
    radii = np.empty(tips * 2, dtype=np.float64)
    radii[0::2] = outer
    radii[1::2] = inner
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


def draw_basic_objects(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int, count: int, size_range: tuple[float, float]) -> None:
    for _ in range(count):
        cx = float(rng.uniform(-0.05, 1.05) * canvas)
        cy = float(rng.uniform(-0.05, 1.05) * canvas)
        radius = float(rng.uniform(*size_range))
        kind = str(rng.choice(["ellipse", "rectangle", "polygon", "capsule", "annulus", "diamond"]))
        if kind == "ellipse":
            axes = (max(2, int(radius * scale)), max(2, int(radius * rng.uniform(0.45, 1.25) * scale)))
            cv2.ellipse(mask, (int(cx * scale), int(cy * scale)), axes, float(rng.uniform(0, 180)), 0, 360, 255, -1, cv2.LINE_8)
        elif kind == "rectangle":
            draw_rotated_rect(mask, (cx, cy), (2 * radius, 2 * radius * rng.uniform(0.45, 1.2)), float(rng.uniform(0, 180)), scale)
        elif kind == "polygon":
            cv2.fillPoly(mask, [polygon_points(cx, cy, radius, int(rng.integers(3, 9)), float(rng.uniform(0, np.pi)), scale)], 255, lineType=cv2.LINE_8)
        elif kind == "capsule":
            angle = float(rng.uniform(0, 2 * np.pi))
            length = radius * float(rng.uniform(1.2, 3.2))
            dx, dy = math.cos(angle) * length * 0.5, math.sin(angle) * length * 0.5
            draw_capsule(mask, (cx - dx, cy - dy), (cx + dx, cy + dy), radius * rng.uniform(0.25, 0.55), scale)
        elif kind == "annulus":
            outer = max(3, int(radius * scale))
            inner = max(1, int(outer * rng.uniform(0.35, 0.72)))
            center = (int(cx * scale), int(cy * scale))
            cv2.circle(mask, center, outer, 255, -1, cv2.LINE_8)
            cv2.circle(mask, center, inner, 0, -1, cv2.LINE_8)
        else:
            cv2.fillPoly(mask, [polygon_points(cx, cy, radius, 4, np.pi / 4.0, scale)], 255, lineType=cv2.LINE_8)


def draw_noncircular(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int, count: int) -> None:
    for _ in range(count):
        cx = float(rng.uniform(0.04, 0.96) * canvas)
        cy = float(rng.uniform(0.04, 0.96) * canvas)
        radius = float(rng.uniform(24, 190))
        kind = str(rng.choice(["star", "gear", "lobed", "crescent", "notched", "concave"]))
        if kind in {"star", "gear"}:
            tips = int(rng.integers(5, 13))
            inner_ratio = rng.uniform(0.35, 0.62) if kind == "star" else rng.uniform(0.72, 0.88)
            points = star_points(cx, cy, radius, radius * inner_ratio, tips, float(rng.uniform(0, np.pi)), scale)
            cv2.fillPoly(mask, [points], 255, lineType=cv2.LINE_8)
        elif kind == "lobed":
            n = 96
            theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
            lobes = int(rng.integers(3, 9))
            phase = float(rng.uniform(0, 2 * np.pi))
            rr = radius * (1.0 + rng.uniform(0.12, 0.32) * np.cos(lobes * theta + phase))
            rr *= 1.0 + rng.uniform(-0.10, 0.10) * np.sin((lobes + 1) * theta)
            points = np.column_stack([cx + rr * np.cos(theta), cy + rr * np.sin(theta)])
            cv2.fillPoly(mask, [np.rint(points * scale).astype(np.int32)], 255, lineType=cv2.LINE_8)
        elif kind == "crescent":
            center = (int(cx * scale), int(cy * scale))
            outer = max(3, int(radius * scale))
            cv2.circle(mask, center, outer, 255, -1, cv2.LINE_8)
            offset = radius * rng.uniform(0.25, 0.55)
            angle = float(rng.uniform(0, 2 * np.pi))
            hole = (int((cx + offset * math.cos(angle)) * scale), int((cy + offset * math.sin(angle)) * scale))
            cv2.circle(mask, hole, max(2, int(radius * rng.uniform(0.72, 0.95) * scale)), 0, -1, cv2.LINE_8)
        elif kind == "notched":
            cv2.circle(mask, (int(cx * scale), int(cy * scale)), max(3, int(radius * scale)), 255, -1, cv2.LINE_8)
            for _ in range(int(rng.integers(2, 6))):
                angle = float(rng.uniform(0, 2 * np.pi))
                nx, ny = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
                cv2.circle(mask, (int(nx * scale), int(ny * scale)), max(2, int(radius * rng.uniform(0.12, 0.30) * scale)), 0, -1, cv2.LINE_8)
        else:
            sides = int(rng.integers(7, 13))
            theta = np.sort(rng.uniform(0, 2 * np.pi, sides))
            rr = radius * rng.uniform(0.35, 1.0, sides)
            points = np.column_stack([cx + rr * np.cos(theta), cy + rr * np.sin(theta)])
            cv2.fillPoly(mask, [np.rint(points * scale).astype(np.int32)], 255, lineType=cv2.LINE_8)


def draw_thin_defects(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int) -> None:
    for _ in range(int(rng.integers(10, 28))):
        point_count = int(rng.integers(2, 7))
        points = np.column_stack([
            rng.uniform(0.02, 0.98, point_count) * canvas * scale,
            rng.uniform(0.02, 0.98, point_count) * canvas * scale,
        ])
        points = points.astype(np.int32).reshape(-1, 1, 2)
        width = max(2, int(rng.uniform(1.5, 16.0) * scale))
        cv2.polylines(mask, [points], False, 255, width, cv2.LINE_8)
        if rng.random() < 0.35:
            center = tuple(points[int(rng.integers(0, len(points))), 0])
            cv2.circle(mask, center, max(2, int(rng.uniform(3, 18) * scale)), 0, -1, cv2.LINE_8)
    for _ in range(int(rng.integers(3, 10))):
        cx, cy = rng.uniform(0.05, 0.95, 2) * canvas
        radius = float(rng.uniform(12, 70))
        start = float(rng.uniform(0, 300))
        extent = float(rng.uniform(35, 280))
        cv2.ellipse(mask, (int(cx * scale), int(cy * scale)), (int(radius * scale), int(radius * rng.uniform(0.5, 1.2) * scale)), float(rng.uniform(0, 180)), start, start + extent, 255, max(2, int(rng.uniform(2, 10) * scale)), cv2.LINE_8)


def draw_dense(mask: np.ndarray, rng: np.random.Generator, canvas: int, scale: int, region: tuple[int, int, int, int] | None = None) -> None:
    if region is None:
        margin = int(rng.uniform(40, 180))
        region = (margin, margin, canvas - margin, canvas - margin)
    x0, y0, x1, y1 = region
    pitch = float(rng.uniform(10, 84))
    kind = str(rng.choice(["dots", "squares", "grating", "crosshatch", "staggered", "missing_grid"]))
    angle = float(rng.choice([0, 15, 30, 45, 60, 75, 90]))
    if kind in {"grating", "crosshatch"}:
        temporary = np.zeros_like(mask)
        width = max(2, int(pitch * rng.uniform(0.12, 0.38) * scale))
        spacing = max(2, int(pitch * scale))
        for q in range(-mask.shape[0], mask.shape[1] * 2, spacing):
            cv2.line(temporary, (q, 0), (q, mask.shape[0] - 1), 255, width, cv2.LINE_8)
        if kind == "crosshatch":
            for q in range(-mask.shape[0], mask.shape[1] * 2, spacing):
                cv2.line(temporary, (0, q), (mask.shape[1] - 1, q), 255, width, cv2.LINE_8)
        center = (mask.shape[1] / 2.0, mask.shape[0] / 2.0)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        temporary = cv2.warpAffine(temporary, matrix, (mask.shape[1], mask.shape[0]), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
        roi = np.zeros_like(mask)
        roi[y0 * scale:y1 * scale, x0 * scale:x1 * scale] = 255
        np.maximum(mask, cv2.bitwise_and(temporary, roi), out=mask)
        return

    radius = max(1.2, pitch * rng.uniform(0.15, 0.37))
    row = 0
    y = y0 + pitch * 0.5
    while y < y1:
        offset = pitch * 0.5 if kind == "staggered" and row % 2 else 0.0
        x = x0 + pitch * 0.5 + offset
        col = 0
        while x < x1:
            missing = kind == "missing_grid" and ((row * 37 + col * 19) % 23 == 0)
            if not missing:
                center = (int(round(x * scale)), int(round(y * scale)))
                if kind == "squares":
                    half = max(1, int(radius * scale))
                    cv2.rectangle(mask, (center[0] - half, center[1] - half), (center[0] + half, center[1] + half), 255, -1, cv2.LINE_8)
                else:
                    cv2.circle(mask, center, max(1, int(radius * scale)), 255, -1, cv2.LINE_8)
            x += pitch
            col += 1
        y += pitch
        row += 1


def generate_mask(role: str, seed: int, canvas: int, scale: int) -> tuple[np.ndarray, dict[str, Any]]:
    for attempt in range(12):
        rng = np.random.default_rng(seed + attempt * 100003)
        mask = np.zeros((canvas * scale, canvas * scale), dtype=np.uint8)
        if role == "basic_geometry":
            draw_basic_objects(mask, rng, canvas, scale, int(rng.integers(5, 14)), (18, 150))
        elif role == "noncircular_complex":
            draw_noncircular(mask, rng, canvas, scale, int(rng.integers(5, 13)))
        elif role == "thin_and_defect":
            draw_thin_defects(mask, rng, canvas, scale)
        elif role == "dense_periodic":
            draw_dense(mask, rng, canvas, scale)
        elif role == "multiscale_field":
            draw_basic_objects(mask, rng, canvas, scale, int(rng.integers(2, 6)), (90, 360))
            for _ in range(int(rng.integers(2, 5))):
                rw = int(rng.integers(300, 760)); rh = int(rng.integers(300, 760))
                x0 = int(rng.integers(0, max(1, canvas - rw))); y0 = int(rng.integers(0, max(1, canvas - rh)))
                draw_dense(mask, rng, canvas, scale, (x0, y0, min(canvas, x0 + rw), min(canvas, y0 + rh)))
            draw_thin_defects(mask, rng, canvas, scale)
        elif role == "cross_tile_large":
            draw_basic_objects(mask, rng, canvas, scale, int(rng.integers(2, 6)), (280, 760))
            if rng.random() < 0.6:
                draw_noncircular(mask, rng, canvas, scale, int(rng.integers(1, 4)))
        elif role == "texture_and_polarity":
            draw_basic_objects(mask, rng, canvas, scale, int(rng.integers(20, 55)), (5, 65))
            if rng.random() < 0.7:
                draw_dense(mask, rng, canvas, scale)
        elif role == "known_subpixel_motion":
            draw_basic_objects(mask, rng, canvas, scale, int(rng.integers(5, 12)), (25, 170))
            draw_noncircular(mask, rng, canvas, scale, int(rng.integers(2, 7)))
        else:
            raise KeyError(role)

        reduced_probe = cv2.resize(mask, (canvas, canvas), interpolation=cv2.INTER_AREA)
        area = float(np.mean(reduced_probe > 127))
        if 0.025 <= area <= 0.78:
            return mask, {"attempt": attempt, "foreground_area_fraction": area}
    raise RuntimeError(f"Could not generate valid area for role={role}, seed={seed}")


def motion_kernel(length: int, angle: float) -> np.ndarray:
    length = max(1, int(length) | 1)
    kernel = np.zeros((length, length), dtype=np.float32)
    center = length // 2
    radians = math.radians(angle)
    dx = math.cos(radians) * center
    dy = math.sin(radians) * center
    p0 = (int(round(center - dx)), int(round(center - dy)))
    p1 = (int(round(center + dx)), int(round(center + dy)))
    cv2.line(kernel, p0, p1, 1.0, 1, cv2.LINE_AA)
    return kernel / max(float(kernel.sum()), 1e-8)


def add_illumination(image: np.ndarray, rng: np.random.Generator, strength: float) -> np.ndarray:
    h, w = image.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xx = (xx / max(w - 1, 1)) * 2.0 - 1.0
    yy = (yy / max(h - 1, 1)) * 2.0 - 1.0
    angle = float(rng.uniform(0, 2 * np.pi))
    gradient = math.cos(angle) * xx + math.sin(angle) * yy
    cx, cy = rng.uniform(-0.4, 0.4, 2)
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    field = 1.0 + strength * (0.55 * gradient - 0.45 * radius)
    return image * field


def degrade(target: np.ndarray, family: str, seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    image = target.astype(np.float32) / 255.0
    parameters: dict[str, Any] = {"family": family}

    if family == "identity_and_near_identity":
        sigma = float(rng.uniform(0.0, 0.35))
        noise = float(rng.uniform(0.0, 0.0035))
    elif family == "standard_recoverable":
        sigma = float(rng.uniform(0.45, 2.2))
        noise = float(rng.uniform(0.002, 0.020))
    elif family == "defocus_and_motion":
        sigma = float(rng.uniform(0.8, 3.2))
        noise = float(rng.uniform(0.003, 0.025))
    elif family == "illumination_and_exposure":
        sigma = float(rng.uniform(0.4, 2.4))
        noise = float(rng.uniform(0.002, 0.025))
    elif family == "halo_ghost_and_banding":
        sigma = float(rng.uniform(0.7, 2.8))
        noise = float(rng.uniform(0.003, 0.028))
    else:
        sigma = float(rng.uniform(2.0, 4.5))
        noise = float(rng.uniform(0.008, 0.040))

    if sigma > 0.05:
        sigma_y = sigma * float(rng.uniform(0.65, 1.45))
        image = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma_y, borderType=cv2.BORDER_REFLECT_101)
        parameters.update({"blur_sigma_x": sigma, "blur_sigma_y": sigma_y})

    if family in {"defocus_and_motion", "severe_but_recoverable"}:
        length = int(rng.integers(3, 10 if family == "defocus_and_motion" else 14))
        angle = float(rng.uniform(0, 180))
        image = cv2.filter2D(image, -1, motion_kernel(length, angle), borderType=cv2.BORDER_REFLECT_101)
        parameters.update({"motion_length": length, "motion_angle": angle})

    if family in {"illumination_and_exposure", "severe_but_recoverable", "halo_ghost_and_banding"}:
        strength = float(rng.uniform(0.08, 0.34 if family != "severe_but_recoverable" else 0.42))
        image = add_illumination(image, rng, strength)
        parameters["illumination_strength"] = strength

    if family in {"halo_ghost_and_banding", "severe_but_recoverable"}:
        wide_sigma = float(rng.uniform(3.0, 9.0))
        wide = cv2.GaussianBlur(image, (0, 0), wide_sigma, borderType=cv2.BORDER_REFLECT_101)
        halo_amp = float(rng.uniform(-0.12, 0.18))
        image = image + halo_amp * (image - wide)
        shift_x, shift_y = rng.integers(-10, 11, 2)
        ghost_amp = float(rng.uniform(0.01, 0.10))
        ghost = np.roll(np.roll(image, int(shift_y), axis=0), int(shift_x), axis=1)
        image = (1.0 - ghost_amp) * image + ghost_amp * ghost
        period = float(rng.uniform(64, 256))
        phase = float(rng.uniform(0, 2 * np.pi))
        axis = np.arange(image.shape[1], dtype=np.float32)
        band = np.sin(2 * np.pi * axis / period + phase)[None, :]
        band_amp = float(rng.uniform(0.003, 0.035))
        image = image + band_amp * band
        parameters.update({"halo_sigma": wide_sigma, "halo_amplitude": halo_amp, "ghost_amplitude": ghost_amp, "band_period": period, "band_amplitude": band_amp})

    exposure = float(rng.uniform(0.72, 1.32))
    gamma = float(rng.uniform(0.78, 1.28))
    if family == "severe_but_recoverable":
        exposure = float(rng.uniform(0.58, 1.38))
        gamma = float(rng.uniform(0.70, 1.45))
    image = np.power(np.clip(image * exposure, 0.0, 1.0), gamma)
    if noise > 0:
        image = image + rng.normal(0.0, noise, image.shape).astype(np.float32)
    if family != "identity_and_near_identity":
        poisson_peak = float(rng.uniform(80, 700))
        image = rng.poisson(np.clip(image, 0.0, 1.0) * poisson_peak).astype(np.float32) / poisson_peak
        parameters["poisson_peak"] = poisson_peak

    image = np.clip(image, 0.0, 1.0)
    contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
    repair_fraction = 0.0
    if contrast < 0.10:
        repair_fraction = min(0.35, (0.10 - contrast) / 0.10)
        image = (1.0 - repair_fraction) * image + repair_fraction * (target.astype(np.float32) / 255.0)
        contrast = float(np.percentile(image, 95) - np.percentile(image, 5))
    parameters.update({"read_noise_sigma": noise, "exposure": exposure, "gamma": gamma, "p95_p5_contrast": contrast, "recoverability_repair_fraction": repair_fraction})
    return np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8), parameters


def role_split_assignments(role: str, count: int, seed: int) -> dict[int, str]:
    rng = np.random.default_rng(seed + sum(ord(ch) for ch in role) * 1009)
    order = rng.permutation(count)
    train_end = int(count * 0.8)
    val_end = int(count * 0.9)
    result: dict[int, str] = {}
    for position, local_index in enumerate(order.tolist()):
        result[int(local_index)] = "train" if position < train_end else "validation" if position < val_end else "internal_test"
    return result


def build(profile: str = "formal", limit: int | None = None) -> tuple[Path, dict[str, Any]]:
    dataset_cfg = CONFIG["dataset"]
    canvas = int(dataset_cfg["canvas_size"])
    scale = int(dataset_cfg["label_supersample_factor"])
    master_seed = int(dataset_cfg["master_seed"])
    package_name = dataset_cfg["package_name"] if profile == "formal" else "r87_smoke_scene_pairs"
    package = DATA_ROOT / package_name
    manifest_path = package / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return package, manifest

    arrays_dir = package / "arrays"
    arrays_dir.mkdir(parents=True, exist_ok=True)
    plan: list[tuple[str, int, int, str]] = []
    global_index = 0
    for role, formal_count in ROLE_COUNTS.items():
        count = formal_count if profile == "formal" else 3
        if profile == "formal":
            assignments = role_split_assignments(role, count, master_seed)
        else:
            order = np.random.default_rng(master_seed + sum(ord(ch) for ch in role)).permutation(count).tolist()
            assignments = {int(order[0]): "train", int(order[1]): "validation", int(order[2]): "internal_test"}
        for local_index in range(count):
            plan.append((role, local_index, global_index, assignments[local_index]))
            global_index += 1
    if limit is not None:
        plan = plan[: int(limit)]

    records: list[dict[str, Any]] = []
    content_digest = hashlib.sha256()
    split_scenes: Counter[str] = Counter()
    split_views: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    degradation_counts: Counter[str] = Counter()
    preview_rows: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
    total = len(plan)

    for position, (role, local_index, scene_index, split) in enumerate(plan, start=1):
        scene_id = f"{role}:g{local_index:04d}:s{master_seed + scene_index * 10007}"
        scene_seed = master_seed * 100000 + scene_index * 10007
        mask_high, geometry_meta = generate_mask(role, scene_seed, canvas, scale)
        base_coverage = cv2.resize(mask_high, (canvas, canvas), interpolation=cv2.INTER_AREA)
        split_scenes[split] += 1
        role_counts[role] += 1

        motion_dx = 0.0
        motion_dy = 0.0
        shifted_coverage = None
        if role == "known_subpixel_motion":
            motion_rng = np.random.default_rng(scene_seed + 7001)
            motion_dx = float(motion_rng.choice([-1, 1]) * motion_rng.uniform(0.125, 2.0))
            motion_dy = float(motion_rng.choice([-1, 1]) * motion_rng.uniform(0.125, 2.0))
            matrix = np.array([[1.0, 0.0, motion_dx * scale], [0.0, 1.0, motion_dy * scale]], dtype=np.float32)
            shifted_high = cv2.warpAffine(mask_high, matrix, (canvas * scale, canvas * scale), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            shifted_coverage = cv2.resize(shifted_high, (canvas, canvas), interpolation=cv2.INTER_AREA)
            del shifted_high

        scene_dir = arrays_dir / f"scene_{scene_index:04d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        for rendering in range(2):
            render_seed = scene_seed + 500000 + rendering * 1009
            rng = np.random.default_rng(render_seed)
            coverage = shifted_coverage if rendering == 1 and shifted_coverage is not None else base_coverage
            bright_foreground = bool((scene_index + rendering) % 2 == 0)
            if bright_foreground:
                background = float(rng.uniform(0.04, 0.34)); foreground = float(rng.uniform(0.66, 0.97))
            else:
                background = float(rng.uniform(0.66, 0.97)); foreground = float(rng.uniform(0.04, 0.34))
            target_f = background + (coverage.astype(np.float32) / 255.0) * (foreground - background)
            target = np.rint(np.clip(target_f, 0.0, 1.0) * 255.0).astype(np.uint8)
            schedule_index = (scene_index * 2 + rendering) % len(DEGRADATION_SCHEDULE)
            degradation_family = DEGRADATION_SCHEDULE[schedule_index]
            source, degradation_meta = degrade(target, degradation_family, render_seed + 91001)
            degradation_counts[degradation_family] += 1

            source_path = scene_dir / f"source_r{rendering}.npy"
            target_path = scene_dir / f"target_r{rendering}.npy"
            save_npy_atomic(source_path, source)
            save_npy_atomic(target_path, target)
            source_hash = array_sha256(source)
            target_hash = array_sha256(target)
            content_digest.update(scene_id.encode("utf-8"))
            content_digest.update(source_hash.encode("ascii"))
            content_digest.update(target_hash.encode("ascii"))
            split_views[split] += 2
            record = {
                "scene_id": scene_id,
                "scene_index": scene_index,
                "role": role,
                "split": split,
                "rendering": rendering,
                "source": source_path.relative_to(package).as_posix(),
                "target": target_path.relative_to(package).as_posix(),
                "source_sha256": source_hash,
                "target_sha256": target_hash,
                "views": 2,
                "canvas_size": canvas,
                "supersample_factor": scale,
                "bright_foreground": bright_foreground,
                "target_background": background,
                "target_foreground": foreground,
                "degradation_family": degradation_family,
                "motion_dx_px": motion_dx if rendering == 1 else 0.0,
                "motion_dy_px": motion_dy if rendering == 1 else 0.0,
                "procedural_only": True,
                "real_pixels_used": False,
                "checkpoint_data_used": False,
                "teacher_output_used": False,
                "geometry": geometry_meta,
                "degradation": degradation_meta,
            }
            records.append(record)
            if len(preview_rows) < 24 and rendering == 0:
                preview_rows.append((role, source.copy(), target.copy(), coverage.copy()))

        del mask_high, base_coverage
        if shifted_coverage is not None:
            del shifted_coverage
        if position == 1 or position % 20 == 0 or position == total:
            progress = {"status": "building", "completed_scenes": position, "total_scenes": total, "records": len(records)}
            json_dump(package / "build_progress.json", progress)
            print(json.dumps(progress), flush=True)

    expected_formal = profile == "formal" and limit is None
    if expected_formal:
        if len(records) != 2560 or sum(split_views.values()) != 5120:
            raise RuntimeError(f"Formal count mismatch: records={len(records)}, views={dict(split_views)}")
        if dict(split_scenes) != {"train": 1024, "validation": 128, "internal_test": 128}:
            raise RuntimeError(f"Formal scene split mismatch: {dict(split_scenes)}")
        expected_degradation = dataset_cfg["degradation_quota_per_2560_renderings"]
        if dict(degradation_counts) != expected_degradation:
            raise RuntimeError(f"Degradation quota mismatch: {dict(degradation_counts)} vs {expected_degradation}")

    preview_dir = package / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    for role, source, target, coverage in preview_rows:
        y0 = (canvas - 384) // 2; x0 = (canvas - 384) // 2
        crop = np.concatenate([source[y0:y0 + 384, x0:x0 + 384], target[y0:y0 + 384, x0:x0 + 384], coverage[y0:y0 + 384, x0:x0 + 384]], axis=1)
        crop = cv2.resize(crop, (576, 192), interpolation=cv2.INTER_AREA)
        cv2.putText(crop, role[:24], (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, 255, 1, cv2.LINE_AA)
        tiles.append(crop)
    if tiles:
        columns = 3
        rows = []
        blank = np.zeros_like(tiles[0])
        for index in range(0, len(tiles), columns):
            group = tiles[index:index + columns]
            rows.append(np.concatenate(group + [blank] * (columns - len(group)), axis=1))
        cv2.imwrite(str(preview_dir / "dataset_preview.png"), np.concatenate(rows, axis=0))

    manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "profile": profile,
        "generator_version": dataset_cfg["generator_version"],
        "master_seed": master_seed,
        "canvas_size": canvas,
        "label_supersample_factor": scale,
        "label_downsample_method": dataset_cfg["label_downsample_method"],
        "scene_count": len(plan),
        "rendering_pair_count": len(records),
        "total_views": sum(split_views.values()),
        "split_unit": "scene_id",
        "split_scene_counts": dict(sorted(split_scenes.items())),
        "split_view_counts": dict(sorted(split_views.items())),
        "role_scene_counts": dict(role_counts),
        "degradation_counts": dict(degradation_counts),
        "content_sha256": content_digest.hexdigest(),
        "source_isolation": {
            "procedural_only": True,
            "real_microscope_pixels": False,
            "sem_pixels": False,
            "hs100mg_structure": False,
            "measured_psf": False,
            "legacy_pairs": False,
            "checkpoint_or_teacher_output": False,
        },
        "records": records,
    }
    json_dump(manifest_path, manifest)
    json_dump(package / "build_progress.json", {"status": "complete", "completed_scenes": len(plan), "total_scenes": len(plan), "records": len(records)})
    return package, manifest


def audit(package: Path, manifest: dict[str, Any], full_hash: bool = False) -> dict[str, Any]:
    records = manifest["records"]
    scene_splits: dict[str, set[str]] = defaultdict(set)
    missing: list[str] = []
    hash_failures: list[str] = []
    shape_failures: list[str] = []
    for index, record in enumerate(records):
        scene_splits[record["scene_id"]].add(record["split"])
        for kind in ("source", "target"):
            path = package / record[kind]
            if not path.is_file():
                missing.append(str(path))
                continue
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            if tuple(array.shape) != (manifest["canvas_size"], manifest["canvas_size"]) or array.dtype != np.uint8:
                shape_failures.append(record[kind])
            if full_hash or index < 24 or index >= len(records) - 24:
                if file_sha256(path) != hashlib.sha256(path.read_bytes()).hexdigest():
                    hash_failures.append(record[kind])
                if array_sha256(np.asarray(array)) != record[f"{kind}_sha256"]:
                    hash_failures.append(record[kind] + ":array")
    leaked = [scene for scene, splits in scene_splits.items() if len(splits) != 1]
    report = {
        "passed": not missing and not hash_failures and not shape_failures and not leaked,
        "record_count": len(records),
        "scene_count": len(scene_splits),
        "total_views": int(manifest["total_views"]),
        "missing_count": len(missing),
        "hash_failure_count": len(hash_failures),
        "shape_failure_count": len(shape_failures),
        "scene_split_overlap_count": len(leaked),
        "sampled_file_hash_audit": not full_hash,
        "source_isolation": manifest["source_isolation"],
    }
    json_dump(package / "audit.json", report)
    if not report["passed"]:
        raise RuntimeError(json.dumps(report, indent=2))

    selected: dict[str, dict[str, Any]] = {}
    for record in records:
        if int(record["rendering"]) == 0 and record["role"] not in selected:
            selected[record["role"]] = record
    overview_rows = []
    crop_size = 512
    start = (int(manifest["canvas_size"]) - crop_size) // 2
    for role in ROLE_COUNTS:
        if role not in selected:
            continue
        record = selected[role]
        source = np.load(package / record["source"], mmap_mode="r", allow_pickle=False)
        target = np.load(package / record["target"], mmap_mode="r", allow_pickle=False)
        src_crop = np.asarray(source[start:start + crop_size, start:start + crop_size])
        tgt_crop = np.asarray(target[start:start + crop_size, start:start + crop_size])
        residual = cv2.absdiff(src_crop, tgt_crop)
        row = np.concatenate([src_crop, tgt_crop, residual], axis=1)
        cv2.putText(row, role, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, 255, 2, cv2.LINE_AA)
        overview_rows.append(cv2.resize(row, (768, 256), interpolation=cv2.INTER_AREA))
    if overview_rows:
        preview_dir = package / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(preview_dir / "dataset_role_overview.png"), np.concatenate(overview_rows, axis=0))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("smoke", "formal"), default="formal")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--full-hash-audit", action="store_true")
    args = parser.parse_args()
    package, manifest = build(args.profile, args.limit)
    report = audit(package, manifest, full_hash=args.full_hash_audit)
    print(json.dumps({"package": str(package), "manifest": str(package / "manifest.json"), "audit": report}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
