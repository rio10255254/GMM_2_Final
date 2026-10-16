"""R48 Lab real-corner transfer data package builder.

This round keeps the standard Lab Training_Data/generated ->
generated_convolved -> package flow, but anchors the synthetic labels to the
real 20250605 checkboard failure mode and writes geometry sidecars for every
packaged training pair.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}
REPO_ROOT = Path(__file__).resolve().parents[3]
THESIS_ROOT = REPO_ROOT.parent
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r48_real_corner_transfer"
DEFAULT_CLEAN_ROOT = REPO_ROOT / "Training_Data" / "generated"
DEFAULT_REAL_IMAGE_ROOT = THESIS_ROOT / "20250605_checkboard"
DEFAULT_PREVIEW_PATH = REPO_ROOT / "Training_Data" / "reports" / "r48_real_corner_preview.png"

STAGE_53_REAL_CORNER = "stage_53_real_corner_anchor"
STAGE_54_LATTICE_INTERSECTIONS = "stage_54_lattice_intersection_anchor"
STAGE_55_REAL_TEXTURE = "stage_55_real_texture_corner"
STAGE_56_CORNER_PSF_STRESS = "stage_56_corner_psf_stress"

SHAPE_STAGES = (
    "stage_01_triangles",
    "stage_02_circles",
    "stage_03_rectangles",
    "stage_04_ellipses",
    "stage_05_polygons",
    "stage_06_mixed_simple",
    "stage_07_mixed_complex",
)

TRAIN_SHAPE_QUOTAS = {stage: 100 for stage in SHAPE_STAGES}
TRAIN_MICRO_QUOTAS = {
    "stage_29_micro_lines_grid": 100,
    "stage_30_micro_large_regions": 100,
    "stage_31_micro_textures": 100,
    "stage_32_micro_edge_defects": 100,
    "stage_33_micro_mixed_fields": 100,
    "stage_11_surface_defect_non_overlap": 50,
    "stage_12_surface_defect_overlap": 50,
    "stage_14_annulus_edge_defect_focus": 50,
    "stage_16_annulus_sparse_defect_clean": 50,
}
TRAIN_BOUNDARY_QUOTAS = {
    STAGE_53_REAL_CORNER: 1600,
    STAGE_54_LATTICE_INTERSECTIONS: 900,
    STAGE_56_CORNER_PSF_STRESS: 500,
}
TRAIN_REAL_BG_QUOTAS = {STAGE_55_REAL_TEXTURE: 800}
VAL_BOUNDARY_QUOTAS = {
    STAGE_53_REAL_CORNER: 300,
    STAGE_54_LATTICE_INTERSECTIONS: 200,
    STAGE_56_CORNER_PSF_STRESS: 200,
}
VAL_REAL_BG_QUOTAS = {STAGE_55_REAL_TEXTURE: 500}

NEW_STAGE_COUNTS = {
    STAGE_53_REAL_CORNER: 1900,
    STAGE_54_LATTICE_INTERSECTIONS: 1100,
    STAGE_55_REAL_TEXTURE: 1300,
    STAGE_56_CORNER_PSF_STRESS: 700,
}

NEW_STAGE_FAMILIES = {
    STAGE_53_REAL_CORNER: "real_corner_anchor",
    STAGE_54_LATTICE_INTERSECTIONS: "lattice_intersection_anchor",
    STAGE_55_REAL_TEXTURE: "real_texture_corner",
    STAGE_56_CORNER_PSF_STRESS: "corner_psf_stress",
}

MICRO_STAGE_FAMILIES = {
    "stage_29_micro_lines_grid": "lines_grid",
    "stage_30_micro_large_regions": "large_regions",
    "stage_31_micro_textures": "textures",
    "stage_32_micro_edge_defects": "edge_defects",
    "stage_33_micro_mixed_fields": "mixed_fields",
    "stage_11_surface_defect_non_overlap": "surface_defects",
    "stage_12_surface_defect_overlap": "surface_defects",
    "stage_14_annulus_edge_defect_focus": "annulus_edge_defects",
    "stage_16_annulus_sparse_defect_clean": "annulus_edge_defects",
}
TRAINER_MICRO_STAGE_PREFIXES = tuple(f"stage_{idx:02d}" for idx in range(29, 34))
LEGACY_MICRO_WRAPPER = Path("stage_33_micro_mixed_fields")


@dataclass(frozen=True)
class Profile:
    name: str
    include_ring: bool
    ring_limit: int | None
    shape_quotas: dict[str, int]
    micro_quotas: dict[str, int]
    boundary_quotas: dict[str, int]
    real_bg_quotas: dict[str, int]
    start_offsets: dict[str, int] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class Pair:
    src: Path
    lbl: Path
    role: str
    stage: str
    rel_dir: Path
    feature_family: str | None = None

    @property
    def filename(self) -> str:
        return self.src.name


@dataclass(frozen=True)
class DatasetPlan:
    profile: Profile
    repo_root: Path
    pairs: tuple[Pair, ...]

    @property
    def source_paths(self) -> tuple[Path, ...]:
        return tuple(pair.src for pair in self.pairs)

    @property
    def count_by_role(self) -> dict[str, int]:
        return dict(Counter(pair.role for pair in self.pairs))

    @property
    def count_by_stage(self) -> dict[str, int]:
        return dict(Counter(pair.stage for pair in self.pairs))


@dataclass(frozen=True)
class GeneratedSample:
    clean: np.ndarray
    boundary: np.ndarray
    centerline: np.ndarray
    distance: np.ndarray
    metadata: dict[str, object]


PROFILES: dict[str, Profile] = {
    "r48_real_corner_train_6000": Profile(
        name="r48_real_corner_train_6000",
        include_ring=True,
        ring_limit=800,
        shape_quotas=TRAIN_SHAPE_QUOTAS,
        micro_quotas=TRAIN_MICRO_QUOTAS,
        boundary_quotas=TRAIN_BOUNDARY_QUOTAS,
        real_bg_quotas=TRAIN_REAL_BG_QUOTAS,
        description=(
            "Lab R48 real-corner transfer package: 800 ring, 700 shape, "
            "700 micro/defect, 3000 real-corner boundary pairs, and "
            "800 real-texture corner pairs with geometry sidecars."
        ),
    ),
    "real_corner_val_unseen": Profile(
        name="real_corner_val_unseen",
        include_ring=False,
        ring_limit=None,
        shape_quotas={},
        micro_quotas={},
        boundary_quotas=VAL_BOUNDARY_QUOTAS,
        real_bg_quotas=VAL_REAL_BG_QUOTAS,
        start_offsets={
            STAGE_53_REAL_CORNER: TRAIN_BOUNDARY_QUOTAS[STAGE_53_REAL_CORNER],
            STAGE_54_LATTICE_INTERSECTIONS: TRAIN_BOUNDARY_QUOTAS[STAGE_54_LATTICE_INTERSECTIONS],
            STAGE_56_CORNER_PSF_STRESS: TRAIN_BOUNDARY_QUOTAS[STAGE_56_CORNER_PSF_STRESS],
            STAGE_55_REAL_TEXTURE: TRAIN_REAL_BG_QUOTAS[STAGE_55_REAL_TEXTURE],
        },
        description="Held-out R48 real-corner validation package.",
    ),
}


def _rng_for(index: int, stage: str, base_seed: int) -> np.random.Generator:
    stage_id = int(stage.split("_")[1])
    return np.random.default_rng(int(base_seed) + stage_id * 100_000 + int(index))


def _clip_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def _read_gray_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"failed to read image: {path}")
    return image


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _smooth_background(rng: np.random.Generator, size: int, *, low: int = 18, high: int = 185) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    base = float(rng.uniform(low, high))
    gx = float(rng.uniform(-55, 55))
    gy = float(rng.uniform(-55, 55))
    bg = base + gx * (xx / max(1, size - 1) - 0.5) + gy * (yy / max(1, size - 1) - 0.5)
    lowfreq = rng.normal(0.0, float(rng.uniform(2.0, 8.0)), (size, size)).astype(np.float32)
    lowfreq = cv2.GaussianBlur(lowfreq, (0, 0), sigmaX=float(rng.uniform(10, 35)))
    return np.clip(bg + lowfreq, 0, 255).astype(np.float32)


def _real_image_paths(real_image_root: Path | str | None) -> list[Path]:
    if real_image_root is None:
        return []
    root = Path(real_image_root)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _real_style_background(
    rng: np.random.Generator,
    size: int,
    *,
    index: int,
    real_image_root: Path | str | None,
) -> np.ndarray:
    paths = _real_image_paths(real_image_root)
    if not paths:
        return _smooth_background(rng, size, low=55, high=175)
    path = paths[index % len(paths)]
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return _smooth_background(rng, size, low=55, high=175)
    h, w = img.shape
    max_crop = min(h, w)
    min_crop = min(max_crop, max(size, min(640, max_crop)))
    crop_size = int(rng.integers(min_crop, max_crop + 1)) if min_crop < max_crop else int(max_crop)
    y0 = int(rng.integers(0, max(1, h - crop_size + 1)))
    x0 = int(rng.integers(0, max(1, w - crop_size + 1)))
    crop = img[y0 : y0 + crop_size, x0 : x0 + crop_size]
    crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    blur = cv2.GaussianBlur(crop, (0, 0), sigmaX=float(rng.uniform(18, 42)))
    blur = blur - float(np.mean(blur))
    target_mean = float(rng.uniform(72, 156))
    target_std = float(rng.uniform(8, 28))
    std = float(np.std(blur)) or 1.0
    bg = target_mean + blur * (target_std / std)
    return np.clip(bg, 0, 255).astype(np.float32)


def _draw_checkboard(img: np.ndarray, rng: np.random.Generator) -> None:
    size = img.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = (size - 1) / 2.0 + float(rng.uniform(-0.08, 0.08) * size)
    cy = (size - 1) / 2.0 + float(rng.uniform(-0.08, 0.08) * size)
    theta = float(rng.uniform(-0.23, 0.23))
    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))
    u = cos_t * (xx - cx) + sin_t * (yy - cy)
    v = -sin_t * (xx - cx) + cos_t * (yy - cy)
    pitch = float(rng.uniform(max(10, size / 34.0), max(28, size / 6.0)))
    phase_u = float(rng.uniform(-pitch, pitch))
    phase_v = float(rng.uniform(-pitch, pitch))
    cells = np.floor((u + phase_u) / pitch) + np.floor((v + phase_v) / pitch)
    pattern = (cells.astype(np.int32) & 1).astype(np.float32)
    dark = float(rng.uniform(8, 62))
    bright = float(rng.uniform(178, 248))
    if rng.random() < 0.35:
        dark, bright = 255.0 - bright, 255.0 - dark
    alpha = float(rng.uniform(0.82, 1.0))
    field = dark + pattern * (bright - dark)
    img[:] = img * (1.0 - alpha) + field * alpha


def _draw_axis_boundary_shapes(img: np.ndarray, rng: np.random.Generator, *, dense: bool = False) -> None:
    size = img.shape[0]
    n = int(rng.integers(6 if dense else 3, 14 if dense else 8))
    for _ in range(n):
        value = float(rng.uniform(10, 68) if rng.random() < 0.5 else rng.uniform(182, 248))
        x0 = int(rng.integers(-size // 8, size - 8))
        y0 = int(rng.integers(-size // 8, size - 8))
        w = int(rng.integers(max(8, size // 28), max(12, size // (5 if dense else 3))))
        h = int(rng.integers(max(8, size // 28), max(12, size // (5 if dense else 3))))
        if rng.random() < 0.45:
            if rng.random() < 0.5:
                w = int(rng.integers(max(2, size // 120), max(4, size // 32)))
            else:
                h = int(rng.integers(max(2, size // 120), max(4, size // 32)))
        cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), value, -1, lineType=cv2.LINE_AA)
    for _ in range(int(rng.integers(2, 7 if dense else 5))):
        value = float(rng.uniform(20, 235))
        p0 = (int(rng.integers(0, size)), int(rng.integers(0, size)))
        p1 = (
            int(np.clip(p0[0] + rng.integers(-size // 2, size // 2 + 1), 0, size - 1)),
            int(np.clip(p0[1] + rng.integers(-size // 2, size // 2 + 1), 0, size - 1)),
        )
        cv2.line(img, p0, p1, value, int(rng.integers(1, 4 if dense else 7)), lineType=cv2.LINE_AA)


def _draw_real_corner_anchors(img: np.ndarray, rng: np.random.Generator, *, dense: bool = False) -> None:
    size = img.shape[0]
    n = int(rng.integers(5 if dense else 3, 13 if dense else 8))
    for _ in range(n):
        value = float(rng.uniform(8, 50) if rng.random() < 0.52 else rng.uniform(205, 252))
        x = int(rng.integers(-size // 12, size - 6))
        y = int(rng.integers(-size // 12, size - 6))
        arm_x = int(rng.integers(max(16, size // 12), max(20, size // 2)))
        arm_y = int(rng.integers(max(16, size // 12), max(20, size // 2)))
        thick = int(rng.integers(max(2, size // 180), max(4, size // 28 if dense else size // 42)))
        sx = int(rng.choice([-1, 1]))
        sy = int(rng.choice([-1, 1]))
        p0 = (x, y)
        px = (x + sx * arm_x, y)
        py = (x, y + sy * arm_y)
        cv2.line(img, p0, px, value, thick, lineType=cv2.LINE_AA)
        cv2.line(img, p0, py, value, thick, lineType=cv2.LINE_AA)
        if rng.random() < 0.55:
            block = int(rng.integers(max(6, size // 35), max(10, size // 9)))
            x1 = x + sx * block
            y1 = y + sy * block
            cv2.rectangle(
                img,
                (min(x, x1), min(y, y1)),
                (max(x, x1), max(y, y1)),
                value,
                -1,
                lineType=cv2.LINE_AA,
            )
    if rng.random() < 0.65:
        pitch = float(rng.uniform(max(24, size / 12.0), max(36, size / 5.0)))
        theta = float(rng.uniform(-0.08, 0.08))
        cos_t = float(np.cos(theta))
        sin_t = float(np.sin(theta))
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        cx = (size - 1) / 2.0 + float(rng.uniform(-0.12, 0.12) * size)
        cy = (size - 1) / 2.0 + float(rng.uniform(-0.12, 0.12) * size)
        u = cos_t * (xx - cx) + sin_t * (yy - cy)
        v = -sin_t * (xx - cx) + cos_t * (yy - cy)
        line_mask = (np.abs(((u + pitch / 2) % pitch) - pitch / 2) < rng.uniform(1.2, 3.4)) | (
            np.abs(((v + pitch / 2) % pitch) - pitch / 2) < rng.uniform(1.2, 3.4)
        )
        value = float(rng.uniform(12, 54) if rng.random() < 0.55 else rng.uniform(202, 248))
        alpha = float(rng.uniform(0.65, 0.95))
        img[line_mask] = img[line_mask] * (1.0 - alpha) + value * alpha


def _draw_intersections(img: np.ndarray, rng: np.random.Generator) -> None:
    size = img.shape[0]
    _draw_axis_boundary_shapes(img, rng, dense=False)
    for _ in range(int(rng.integers(4, 9))):
        cx = int(rng.integers(0, size))
        cy = int(rng.integers(0, size))
        length = int(rng.integers(max(20, size // 10), max(24, size // 3)))
        thick = int(rng.integers(max(1, size // 180), max(3, size // 45)))
        value = float(rng.uniform(12, 55) if rng.random() < 0.5 else rng.uniform(200, 250))
        cv2.line(img, (cx - length, cy), (cx + length, cy), value, thick, lineType=cv2.LINE_AA)
        if rng.random() < 0.75:
            cv2.line(img, (cx, cy - length), (cx, cy + length), value, thick, lineType=cv2.LINE_AA)
        else:
            cv2.line(img, (cx, cy), (cx, cy + length), value, thick, lineType=cv2.LINE_AA)


def _draw_psf_stress(img: np.ndarray, rng: np.random.Generator) -> None:
    size = img.shape[0]
    if rng.random() < 0.55:
        _draw_checkboard(img, rng)
    _draw_axis_boundary_shapes(img, rng, dense=True)
    _draw_real_corner_anchors(img, rng, dense=True)
    for _ in range(int(rng.integers(8, 18))):
        value = float(rng.uniform(5, 40) if rng.random() < 0.5 else rng.uniform(210, 252))
        x = int(rng.integers(0, size))
        y = int(rng.integers(0, size))
        length = int(rng.integers(size // 12, size // 2))
        angle = float(rng.choice([0.0, np.pi / 2, np.pi / 4, -np.pi / 4]) + rng.uniform(-0.04, 0.04))
        dx = int(np.cos(angle) * length)
        dy = int(np.sin(angle) * length)
        cv2.line(img, (x - dx, y - dy), (x + dx, y + dy), value, 1, lineType=cv2.LINE_AA)


def compute_geometry_from_label(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = img
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=0.65)
    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    threshold = max(8.0, float(np.percentile(mag, 84.0)))
    centerline = (mag >= threshold).astype(np.uint8) * 255
    centerline = cv2.morphologyEx(centerline, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(centerline) == 0:
        centerline = cv2.Canny(gray, 40, 120)
    boundary = cv2.dilate(centerline, np.ones((3, 3), np.uint8), iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def generate_real_corner_sample(
    *,
    index: int,
    stage: str,
    size: int = 512,
    base_seed: int = 4848,
    real_image_root: Path | str | None = DEFAULT_REAL_IMAGE_ROOT,
) -> GeneratedSample:
    """Generate one clean GT image and geometry sidecars for the R48 stages."""
    if stage not in NEW_STAGE_COUNTS:
        raise ValueError(f"unsupported R48 stage: {stage}")
    size = int(size)
    rng = _rng_for(index, stage, base_seed)
    if stage == STAGE_55_REAL_TEXTURE:
        img = _real_style_background(rng, size, index=index, real_image_root=real_image_root)
    else:
        img = _smooth_background(rng, size, low=12, high=170)

    if stage == STAGE_53_REAL_CORNER:
        _draw_checkboard(img, rng)
        _draw_real_corner_anchors(img, rng, dense=True)
        if rng.random() < 0.45:
            _draw_axis_boundary_shapes(img, rng, dense=False)
    elif stage == STAGE_54_LATTICE_INTERSECTIONS:
        _draw_intersections(img, rng)
        _draw_real_corner_anchors(img, rng, dense=False)
    elif stage == STAGE_55_REAL_TEXTURE:
        if rng.random() < 0.45:
            _draw_checkboard(img, rng)
        _draw_intersections(img, rng)
        _draw_real_corner_anchors(img, rng, dense=False)
    elif stage == STAGE_56_CORNER_PSF_STRESS:
        _draw_psf_stress(img, rng)

    if rng.random() < 0.5:
        gain = float(rng.uniform(0.86, 1.14))
        bias = float(rng.uniform(-12, 12))
        img = img * gain + bias
    clean = _clip_u8(img)
    boundary, centerline, distance = compute_geometry_from_label(clean)
    return GeneratedSample(
        clean=clean,
        boundary=boundary,
        centerline=centerline,
        distance=distance,
        metadata={
            "stage": stage,
            "index": int(index),
            "family": NEW_STAGE_FAMILIES[stage],
            "base_seed": int(base_seed),
        },
    )


def generate_realistic_boundary_image(
    *,
    index: int,
    stage: str,
    size: int = 512,
    base_seed: int = 4848,
    real_image_root: Path | str | None = DEFAULT_REAL_IMAGE_ROOT,
) -> np.ndarray:
    """Compatibility wrapper returning only the clean R48 label image."""
    return generate_real_corner_sample(
        index=index,
        stage=stage,
        size=size,
        base_seed=base_seed,
        real_image_root=real_image_root,
    ).clean


def estimate_corner_count(img: np.ndarray) -> int:
    gray = img
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.uint8, copy=False)
    corners = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=768,
        qualityLevel=0.01,
        minDistance=4,
        blockSize=5,
        useHarrisDetector=True,
        k=0.04,
    )
    return 0 if corners is None else int(len(corners))


def estimate_edge_density(img: np.ndarray) -> float:
    gray = img
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.uint8, copy=False)
    edges = cv2.Canny(gray, 48, 128)
    return float(np.count_nonzero(edges)) / float(edges.size)


def _safe_remove_tree(path: Path, root: Path | None = None) -> None:
    resolved = path.resolve()
    if root is not None:
        root_resolved = root.resolve()
        if not str(resolved).lower().startswith(str(root_resolved).lower()):
            raise ValueError(f"refusing to remove outside root: {resolved}")
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
    shutil.rmtree(resolved)


def generate_clean_dataset(
    output_root: Path | str = DEFAULT_CLEAN_ROOT,
    *,
    count_by_stage: dict[str, int] | None = None,
    size: int = 512,
    base_seed: int = 4848,
    real_image_root: Path | str | None = DEFAULT_REAL_IMAGE_ROOT,
    force: bool = False,
) -> dict:
    out_root = Path(output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    counts = dict(NEW_STAGE_COUNTS if count_by_stage is None else count_by_stage)
    stages = []
    for stage, count in counts.items():
        if stage not in NEW_STAGE_COUNTS:
            raise ValueError(f"unsupported R48 stage: {stage}")
        stage_dir = out_root / stage
        if stage_dir.exists():
            if not force and any(stage_dir.iterdir()):
                raise FileExistsError(f"stage directory already exists and is non-empty: {stage_dir}")
            if force:
                _safe_remove_tree(stage_dir, out_root)
        stage_dir.mkdir(parents=True, exist_ok=True)
        corner_counts: list[int] = []
        edge_densities: list[float] = []
        for idx in range(int(count)):
            sample = generate_real_corner_sample(
                index=idx,
                stage=stage,
                size=size,
                base_seed=base_seed,
                real_image_root=real_image_root,
            )
            img = sample.clean
            corner_counts.append(estimate_corner_count(img))
            edge_densities.append(estimate_edge_density(img))
            out_path = stage_dir / f"{idx:04d}.bmp"
            _write_image(out_path, img)
        stages.append(
            {
                "stage": stage,
                "count": int(count),
                "family": NEW_STAGE_FAMILIES[stage],
                "corner_count_min": int(min(corner_counts)),
                "corner_count_median": float(np.median(corner_counts)),
                "corner_count_max": int(max(corner_counts)),
                "edge_density_median": float(np.median(edge_densities)),
            }
        )
    manifest = {
        "generator": "r48_lab_real_corner_transfer_v1",
        "output_root": str(out_root),
        "image_size": int(size),
        "base_seed": int(base_seed),
        "real_image_root": str(real_image_root) if real_image_root is not None else None,
        "total_images": int(sum(stage["count"] for stage in stages)),
        "stages": stages,
    }
    (out_root / "r48_real_corner_clean_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def collect_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _require_complete_stage_pairs(repo_root: Path, stage: str) -> list[Path]:
    src_dir = repo_root / "Training_Data" / "generated_convolved" / stage
    lbl_dir = repo_root / "Training_Data" / "generated" / stage
    src_files = collect_images(src_dir)
    missing = [p for p in src_files if not (lbl_dir / p.name).exists()]
    if missing:
        examples = ", ".join(p.name for p in missing[:5])
        raise ValueError(f"{stage} has missing labels: {examples}")
    return src_files


def _ring_pairs(repo_root: Path, limit: int | None) -> list[Pair]:
    src_dir = repo_root / "Training_Data" / "tra_src_ring"
    lbl_dir = repo_root / "Training_Data" / "tra_lbl_ring"
    src_files = collect_images(src_dir)
    missing = [p for p in src_files if not (lbl_dir / p.name).exists()]
    if missing:
        examples = ", ".join(p.name for p in missing[:5])
        raise ValueError(f"ring data has missing labels: {examples}")
    if limit is not None:
        src_files = src_files[: max(0, int(limit))]
    return [
        Pair(src=p, lbl=lbl_dir / p.name, role="ring", stage="ring", rel_dir=Path("ring"))
        for p in src_files
    ]


def _quota_stage_pairs(
    repo_root: Path,
    quotas: dict[str, int],
    *,
    role: str,
    start_offsets: dict[str, int],
) -> list[Pair]:
    pairs: list[Pair] = []
    for stage, quota in quotas.items():
        if int(quota) <= 0:
            continue
        src_files = _require_complete_stage_pairs(repo_root, stage)
        start = int(start_offsets.get(stage, 0))
        end = start + int(quota)
        if len(src_files) < end:
            raise ValueError(
                f"{stage} has only {len(src_files)} images; requires index range [{start}, {end})."
            )
        lbl_dir = repo_root / "Training_Data" / "generated" / stage
        family = NEW_STAGE_FAMILIES.get(stage) or MICRO_STAGE_FAMILIES.get(stage)
        if role in {"boundary", "real_bg"}:
            rel_dir = Path("stage_40_boundary_mixed") / stage
        elif role == "micro" and not stage.startswith(TRAINER_MICRO_STAGE_PREFIXES):
            rel_dir = LEGACY_MICRO_WRAPPER / stage
        else:
            rel_dir = Path(stage)
        for src in src_files[start:end]:
            pairs.append(
                Pair(
                    src=src,
                    lbl=lbl_dir / src.name,
                    role=role,
                    stage=stage,
                    rel_dir=rel_dir,
                    feature_family=family,
                )
            )
    return pairs


def build_plan(repo_root: Path | str, profile: Profile) -> DatasetPlan:
    root = Path(repo_root).resolve()
    pairs: list[Pair] = []
    if profile.include_ring:
        pairs.extend(_ring_pairs(root, profile.ring_limit))
    pairs.extend(_quota_stage_pairs(root, profile.shape_quotas, role="shape", start_offsets=profile.start_offsets))
    pairs.extend(_quota_stage_pairs(root, profile.micro_quotas, role="micro", start_offsets=profile.start_offsets))
    pairs.extend(_quota_stage_pairs(root, profile.boundary_quotas, role="boundary", start_offsets=profile.start_offsets))
    pairs.extend(_quota_stage_pairs(root, profile.real_bg_quotas, role="real_bg", start_offsets=profile.start_offsets))
    if not pairs:
        raise ValueError(f"profile {profile.name} produced no image pairs")
    return DatasetPlan(profile=profile, repo_root=root, pairs=tuple(pairs))


def assert_disjoint_plans(*plans: DatasetPlan) -> None:
    seen: dict[Path, str] = {}
    for plan in plans:
        for src in plan.source_paths:
            resolved = src.resolve()
            if resolved in seen:
                raise ValueError(
                    f"data split overlap: {resolved} appears in both {seen[resolved]} and {plan.profile.name}"
                )
            seen[resolved] = plan.profile.name


def _place_file(src: Path, dst: Path, link_mode: str) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if link_mode not in {"auto", "hardlink", "copy"}:
        raise ValueError(f"unsupported link mode: {link_mode}")
    if link_mode in {"auto", "hardlink"}:
        try:
            os.link(src, dst)
            return "hardlink"
        except OSError:
            if link_mode == "hardlink":
                raise
    shutil.copy2(src, dst)
    return "copy"


def _write_geometry_sidecars(lbl_path: Path, geom_dir: Path, rel_path: Path) -> None:
    img = _read_gray_image(lbl_path)
    boundary, centerline, distance = compute_geometry_from_label(img)
    boundary_path = geom_dir / "boundary" / rel_path
    centerline_path = geom_dir / "centerline" / rel_path
    distance_path = geom_dir / "distance" / rel_path.with_suffix(".npy")
    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    centerline_path.parent.mkdir(parents=True, exist_ok=True)
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    _write_image(boundary_path, boundary)
    _write_image(centerline_path, centerline)
    np.save(distance_path, distance.astype(np.float32, copy=False))


def materialize_plan(
    plan: DatasetPlan,
    output_dir: Path | str,
    *,
    force: bool = False,
    link_mode: str = "auto",
) -> dict:
    out = Path(output_dir).resolve()
    if out.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {out}")
        _safe_remove_tree(out)
    out.mkdir(parents=True, exist_ok=True)

    link_counts: Counter[str] = Counter()
    records = []
    geometry_count = 0
    geom_dir = out / "geom"
    for pair in plan.pairs:
        src_rel = Path("src") / pair.rel_dir / pair.filename
        lbl_rel = Path("lbl") / pair.rel_dir / pair.filename
        link_counts[_place_file(pair.src, out / src_rel, link_mode)] += 1
        link_counts[_place_file(pair.lbl, out / lbl_rel, link_mode)] += 1
        geom_rel = src_rel.relative_to("src")
        _write_geometry_sidecars(out / lbl_rel, geom_dir, geom_rel)
        geometry_count += 1
        records.append(
            {
                "role": pair.role,
                "stage": pair.stage,
                "feature_family": pair.feature_family,
                "src": str(pair.src),
                "lbl": str(pair.lbl),
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "geometry_boundary": (Path("geom") / "boundary" / geom_rel).as_posix(),
                "geometry_centerline": (Path("geom") / "centerline" / geom_rel).as_posix(),
                "geometry_distance": (Path("geom") / "distance" / geom_rel.with_suffix(".npy")).as_posix(),
            }
        )

    manifest = {
        "profile": plan.profile.name,
        "description": plan.profile.description,
        "repo_root": str(plan.repo_root),
        "output_dir": str(out),
        "total_pairs": len(plan.pairs),
        "count_by_role": plan.count_by_role,
        "count_by_stage": plan.count_by_stage,
        "link_counts": dict(link_counts),
        "geometry_sidecars": True,
        "geom_dir": str(geom_dir),
        "geometry_count": int(geometry_count),
        "new_stage_counts": NEW_STAGE_COUNTS,
        "new_stage_families": NEW_STAGE_FAMILIES,
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def create_preview(
    image_root: Path | str = DEFAULT_CLEAN_ROOT,
    output_path: Path | str = DEFAULT_PREVIEW_PATH,
    *,
    max_per_stage: int = 4,
    tile_size: int = 160,
) -> dict:
    root = Path(image_root)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tiles = []
    stats = []
    for stage in NEW_STAGE_COUNTS:
        paths = collect_images(root / stage)[: int(max_per_stage)]
        if not paths:
            continue
        stage_edges = []
        stage_corners = []
        for path in paths:
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise RuntimeError(f"failed to read preview image: {path}")
            stage_edges.append(estimate_edge_density(img))
            stage_corners.append(estimate_corner_count(img))
            tile = cv2.resize(img, (tile_size, tile_size), interpolation=cv2.INTER_AREA)
            tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
            cv2.putText(
                tile,
                stage.split("_", 2)[1],
                (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            tiles.append(tile)
        stats.append(
            {
                "stage": stage,
                "preview_count": len(paths),
                "edge_density_median": float(np.median(stage_edges)),
                "corner_count_median": float(np.median(stage_corners)),
            }
        )
    if not tiles:
        raise FileNotFoundError(f"no preview images found under {root}")
    cols = min(4, len(tiles))
    rows = int(np.ceil(len(tiles) / cols))
    sheet = np.full((rows * tile_size, cols * tile_size, 3), 245, dtype=np.uint8)
    for idx, tile in enumerate(tiles):
        r, c = divmod(idx, cols)
        sheet[r * tile_size : (r + 1) * tile_size, c * tile_size : (c + 1) * tile_size] = tile
    ok = cv2.imwrite(str(out), sheet)
    if not ok:
        raise RuntimeError(f"failed to write preview: {out}")
    return {"preview": str(out), "image_count": len(tiles), "stage_stats": stats}


def _profiles_from_cli(profile_name: str) -> Iterable[Profile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate Lab R48 real-corner transfer data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-clean", help="Generate clean R48 real-corner labels.")
    gen.add_argument("--output-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    gen.add_argument("--real-image-root", type=Path, default=DEFAULT_REAL_IMAGE_ROOT)
    gen.add_argument("--size", type=int, default=512)
    gen.add_argument("--base-seed", type=int, default=4848)
    gen.add_argument("--force", action="store_true")

    preview = sub.add_parser("preview", help="Create a contact-sheet preview for R48 clean images.")
    preview.add_argument("--image-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    preview.add_argument("--output-path", type=Path, default=DEFAULT_PREVIEW_PATH)
    preview.add_argument("--max-per-stage", type=int, default=4)

    for cmd in ("plan", "build", "validate-splits"):
        p = sub.add_parser(cmd)
        p.add_argument("--profile", default="all", choices=[*PROFILES.keys(), "all"])
        p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
        p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
        p.add_argument("--force", action="store_true")
        p.add_argument("--link-mode", default="auto", choices=["auto", "hardlink", "copy"])

    args = parser.parse_args(argv)

    if args.command == "generate-clean":
        manifest = generate_clean_dataset(
            args.output_root,
            size=args.size,
            base_seed=args.base_seed,
            real_image_root=args.real_image_root,
            force=args.force,
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    if args.command == "preview":
        summary = create_preview(args.image_root, args.output_path, max_per_stage=args.max_per_stage)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    summaries = []
    plans = []
    for profile in _profiles_from_cli(args.profile):
        plan = build_plan(args.repo_root, profile)
        plans.append(plan)
        summary = {
            "profile": profile.name,
            "total_pairs": len(plan.pairs),
            "count_by_role": plan.count_by_role,
            "count_by_stage": plan.count_by_stage,
        }
        if args.command == "build":
            output_dir = args.output_root / profile.name
            manifest = materialize_plan(plan, output_dir, force=args.force, link_mode=args.link_mode)
            summary["output_dir"] = manifest["output_dir"]
            summary["link_counts"] = manifest["link_counts"]
            summary["geometry_count"] = manifest["geometry_count"]
        summaries.append(summary)

    if args.command == "validate-splits":
        assert_disjoint_plans(*plans)
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
