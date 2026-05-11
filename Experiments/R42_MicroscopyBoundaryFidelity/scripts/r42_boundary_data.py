"""R42 microscopy-boundary data package builder."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}
REPO_ROOT = Path(__file__).resolve().parents[3]
R40_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"
if str(R40_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R40_SCRIPT_DIR))

from r40_micro_data import (  # noqa: E402
    MICRO_STAGES,
    SHAPE_STAGES,
    _ring_pairs as r40_ring_pairs,
    _stage_pairs as r40_stage_pairs,
)


DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r42_microscopy_boundary_fidelity"
DEFAULT_CLEAN_ROOT = REPO_ROOT / "Training_Data" / "generated"
DEFAULT_SOURCE_ROOT = REPO_ROOT / "Training_Data" / "generated_convolved"
DEFAULT_GEOM_ROOT = REPO_ROOT / "Training_Data" / "r42_boundary_geometry"


@dataclass(frozen=True)
class BoundaryStageSpec:
    stage_id: int
    name: str
    feature_family: str
    description: str


BOUNDARY_STAGE_SPECS: tuple[BoundaryStageSpec, ...] = (
    BoundaryStageSpec(34, "stage_34_boundary_lines", "thin_lines", "Thin and angled centerline structures."),
    BoundaryStageSpec(35, "stage_35_boundary_grids", "grids", "Periodic grid structures with explicit pitch and phase."),
    BoundaryStageSpec(36, "stage_36_boundary_junctions", "junctions", "T, X, and Y crossings with sharp intersections."),
    BoundaryStageSpec(37, "stage_37_boundary_curves", "curves", "Curved arcs, ellipses, and rounded boundaries."),
    BoundaryStageSpec(38, "stage_38_boundary_regions", "large_regions", "Large IC-like bright and dark regions."),
    BoundaryStageSpec(39, "stage_39_boundary_defects", "defects", "Chips, scratches, dots, and local defects."),
    BoundaryStageSpec(40, "stage_40_boundary_mixed", "mixed_fields", "Mixed microscopy scenes combining all feature types."),
)
BOUNDARY_STAGES = tuple(spec.name for spec in BOUNDARY_STAGE_SPECS)
BOUNDARY_STAGE_FAMILIES = {spec.name: spec.feature_family for spec in BOUNDARY_STAGE_SPECS}


@dataclass(frozen=True)
class GeometryPaths:
    boundary: Path
    centerline: Path
    distance: Path
    meta: Path | None = None


@dataclass(frozen=True)
class R42Profile:
    name: str
    include_ring: bool
    ring_limit: int | None
    shape_total: int
    shape_start_index: int
    micro_total: int
    micro_start_index: int
    boundary_per_stage: int
    boundary_start_index: int
    description: str


@dataclass(frozen=True)
class Pair:
    src: Path
    lbl: Path
    role: str
    stage: str
    rel_dir: Path
    feature_family: str | None = None
    geometry: GeometryPaths | None = None

    @property
    def filename(self) -> str:
        return self.src.name


@dataclass(frozen=True)
class DatasetPlan:
    profile: R42Profile
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


PROFILES: dict[str, R42Profile] = {
    "r42_boundary_research_train": R42Profile(
        name="r42_boundary_research_train",
        include_ring=True,
        ring_limit=500,
        shape_total=250,
        shape_start_index=0,
        micro_total=350,
        micro_start_index=0,
        boundary_per_stage=80,
        boundary_start_index=0,
        description="Research-first mix: legacy replay plus high-ratio R42 boundary structures.",
    ),
    "r42_guarded_kd_probe_train": R42Profile(
        name="r42_guarded_kd_probe_train",
        include_ring=True,
        ring_limit=700,
        shape_total=300,
        shape_start_index=0,
        micro_total=250,
        micro_start_index=0,
        boundary_per_stage=40,
        boundary_start_index=0,
        description="Diagnostic guarded-KD mix: stronger legacy replay while retaining R42 boundary coverage.",
    ),
    "boundary_val_unseen": R42Profile(
        name="boundary_val_unseen",
        include_ring=False,
        ring_limit=None,
        shape_total=0,
        shape_start_index=0,
        micro_total=0,
        micro_start_index=0,
        boundary_per_stage=20,
        boundary_start_index=80,
        description="Held-out unseen R42 boundary validation set.",
    ),
}


def _safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
    shutil.rmtree(resolved)


def _rng_for(spec: BoundaryStageSpec, index: int, base_seed: int) -> np.random.Generator:
    return np.random.default_rng(int(base_seed) + spec.stage_id * 10_000 + int(index))


def _clip_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def _draw_line_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    img[:, :] = int(rng.integers(18, 50))
    for _ in range(int(rng.integers(4, 9))):
        angle = float(rng.uniform(0, np.pi))
        length = int(rng.integers(w // 3, int(w * 0.95)))
        cx = int(rng.integers(w // 6, 5 * w // 6))
        cy = int(rng.integers(h // 6, 5 * h // 6))
        dx = int(np.cos(angle) * length / 2)
        dy = int(np.sin(angle) * length / 2)
        p0 = (int(np.clip(cx - dx, 0, w - 1)), int(np.clip(cy - dy, 0, h - 1)))
        p1 = (int(np.clip(cx + dx, 0, w - 1)), int(np.clip(cy + dy, 0, h - 1)))
        width = int(rng.integers(1, 4))
        color = int(rng.integers(145, 235))
        cv2.line(img, p0, p1, color, width)
        cv2.line(centerline, p0, p1, 255, 1)


def _draw_grid_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> dict:
    h, w = img.shape
    img[:, :] = int(rng.integers(20, 58))
    pitch = int(rng.integers(max(7, w // 40), max(11, w // 9)))
    ox = int(rng.integers(0, pitch))
    oy = int(rng.integers(0, pitch))
    color = int(rng.integers(150, 235))
    width = int(rng.integers(1, 3))
    for x in range(ox, w, pitch):
        cv2.line(img, (x, 0), (x, h - 1), color, width)
        cv2.line(centerline, (x, 0), (x, h - 1), 255, 1)
    for y in range(oy, h, pitch):
        cv2.line(img, (0, y), (w - 1, y), color, width)
        cv2.line(centerline, (0, y), (w - 1, y), 255, 1)
    return {"pitch_px": pitch, "offset_x_px": ox, "offset_y_px": oy}


def _draw_junction_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    img[:, :] = int(rng.integers(15, 45))
    for _ in range(int(rng.integers(3, 7))):
        cx = int(rng.integers(w // 5, 4 * w // 5))
        cy = int(rng.integers(h // 5, 4 * h // 5))
        arms = int(rng.choice([3, 4]))
        base_angle = float(rng.uniform(0, np.pi))
        radius = int(rng.integers(w // 7, w // 3))
        for arm in range(arms):
            angle = base_angle + arm * (2 * np.pi / arms)
            p1 = (
                int(np.clip(cx + np.cos(angle) * radius, 0, w - 1)),
                int(np.clip(cy + np.sin(angle) * radius, 0, h - 1)),
            )
            cv2.line(img, (cx, cy), p1, int(rng.integers(140, 235)), int(rng.integers(1, 4)))
            cv2.line(centerline, (cx, cy), p1, 255, 1)


def _draw_curve_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    img[:, :] = int(rng.integers(12, 42))
    for _ in range(int(rng.integers(3, 7))):
        center = (int(rng.integers(w // 5, 4 * w // 5)), int(rng.integers(h // 5, 4 * h // 5)))
        axes = (int(rng.integers(w // 12, w // 4)), int(rng.integers(h // 16, h // 4)))
        angle = float(rng.uniform(0, 180))
        start = float(rng.uniform(0, 240))
        end = min(360.0, start + float(rng.uniform(80, 220)))
        width = int(rng.integers(1, 4))
        cv2.ellipse(img, center, axes, angle, start, end, int(rng.integers(145, 235)), width)
        cv2.ellipse(centerline, center, axes, angle, start, end, 255, 1)


def _draw_region_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    img[:, :] = int(rng.integers(10, 40))
    for _ in range(int(rng.integers(2, 5))):
        x0 = int(rng.integers(0, w * 2 // 3))
        y0 = int(rng.integers(0, h * 2 // 3))
        x1 = int(rng.integers(max(x0 + 18, w // 3), w))
        y1 = int(rng.integers(max(y0 + 18, h // 3), h))
        value = int(rng.integers(85, 220))
        cv2.rectangle(img, (x0, y0), (x1, y1), value, -1)
        cv2.rectangle(centerline, (x0, y0), (x1, y1), 255, 1)
    if rng.random() < 0.4:
        pts = np.asarray(
            [(int(rng.integers(0, w)), int(rng.integers(0, h))) for _ in range(5)],
            dtype=np.int32,
        )
        cv2.fillPoly(img, [pts], int(rng.integers(80, 190)))
        cv2.polylines(centerline, [pts], True, 255, 1)


def _draw_defect_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> None:
    _draw_region_family(img, centerline, rng)
    h, w = img.shape
    for _ in range(int(rng.integers(10, 25))):
        pt = (int(rng.integers(w // 8, 7 * w // 8)), int(rng.integers(h // 8, 7 * h // 8)))
        radius = int(rng.integers(1, 6))
        val = int(rng.choice([rng.integers(20, 70), rng.integers(185, 245)]))
        cv2.circle(img, pt, radius, val, -1)
        cv2.circle(centerline, pt, max(1, radius // 2), 255, -1)
    for _ in range(int(rng.integers(2, 6))):
        p0 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        p1 = (
            int(np.clip(p0[0] + rng.integers(-w // 4, w // 4), 0, w - 1)),
            int(np.clip(p0[1] + rng.integers(-h // 4, h // 4), 0, h - 1)),
        )
        cv2.line(img, p0, p1, int(rng.integers(20, 80)), int(rng.integers(1, 3)))
        cv2.line(centerline, p0, p1, 255, 1)


def _draw_mixed_family(img: np.ndarray, centerline: np.ndarray, rng: np.random.Generator) -> dict:
    meta = _draw_grid_family(img, centerline, rng)
    overlay = img.copy()
    local_center = np.zeros_like(centerline)
    _draw_region_family(overlay, local_center, rng)
    img[:, :] = cv2.addWeighted(img, 0.55, overlay, 0.45, 0)
    centerline[:, :] = np.maximum(centerline, local_center)
    local_center[:, :] = 0
    _draw_defect_family(img, local_center, rng)
    centerline[:, :] = np.maximum(centerline, local_center)
    return meta


def _boundary_from_label(label: np.ndarray) -> np.ndarray:
    edge = cv2.Canny(label, 40, 120)
    if int(edge.max()) == 0:
        kernel = np.ones((3, 3), np.uint8)
        edge = cv2.morphologyEx(label, cv2.MORPH_GRADIENT, kernel)
    edge = (edge > 0).astype(np.uint8) * 255
    return edge


def _distance_from_boundary(boundary: np.ndarray) -> np.ndarray:
    inv = np.where(boundary > 0, 0, 255).astype(np.uint8)
    return cv2.distanceTransform(inv, cv2.DIST_L2, 5).astype(np.float32)


def _simulate_source(label: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    sigma = float(rng.uniform(0.8, 1.7))
    blurred = cv2.GaussianBlur(label, (0, 0), sigmaX=sigma, sigmaY=sigma)
    noise = rng.normal(0.0, float(rng.uniform(1.0, 4.0)), size=label.shape)
    return _clip_u8(blurred.astype(np.float32) + noise)


def generate_boundary_image(
    spec: BoundaryStageSpec,
    *,
    index: int,
    size: int = 512,
    base_seed: int = 4200,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    rng = _rng_for(spec, index, base_seed)
    label = np.zeros((int(size), int(size)), dtype=np.uint8)
    centerline = np.zeros_like(label)
    meta: dict = {}
    if spec.feature_family == "thin_lines":
        _draw_line_family(label, centerline, rng)
    elif spec.feature_family == "grids":
        meta.update(_draw_grid_family(label, centerline, rng))
    elif spec.feature_family == "junctions":
        _draw_junction_family(label, centerline, rng)
    elif spec.feature_family == "curves":
        _draw_curve_family(label, centerline, rng)
    elif spec.feature_family == "large_regions":
        _draw_region_family(label, centerline, rng)
    elif spec.feature_family == "defects":
        _draw_defect_family(label, centerline, rng)
    elif spec.feature_family == "mixed_fields":
        meta.update(_draw_mixed_family(label, centerline, rng))
    else:
        raise ValueError(f"unsupported feature family: {spec.feature_family}")
    boundary = _boundary_from_label(label)
    distance = _distance_from_boundary(boundary)
    source = _simulate_source(label, rng)
    meta.update({"stage": spec.name, "feature_family": spec.feature_family, "index": int(index)})
    return source, label, boundary, centerline, distance, meta


def generate_boundary_dataset(
    *,
    clean_root: Path | str = DEFAULT_CLEAN_ROOT,
    source_root: Path | str = DEFAULT_SOURCE_ROOT,
    geom_root: Path | str = DEFAULT_GEOM_ROOT,
    count_per_stage: int = 100,
    size: int = 512,
    base_seed: int = 4200,
    force: bool = False,
) -> dict:
    clean_root = Path(clean_root).resolve()
    source_root = Path(source_root).resolve()
    geom_root = Path(geom_root).resolve()
    for root in (clean_root, source_root, geom_root):
        root.mkdir(parents=True, exist_ok=True)

    stages = []
    for spec in BOUNDARY_STAGE_SPECS:
        stage_dirs = [
            clean_root / spec.name,
            source_root / spec.name,
            geom_root / "boundary" / spec.name,
            geom_root / "centerline" / spec.name,
            geom_root / "distance" / spec.name,
            geom_root / "meta" / spec.name,
        ]
        for stage_dir in stage_dirs:
            if stage_dir.exists() and force:
                _safe_remove_tree(stage_dir)
            if stage_dir.exists() and not force and any(stage_dir.iterdir()):
                raise FileExistsError(f"stage directory already exists and is non-empty: {stage_dir}")
            stage_dir.mkdir(parents=True, exist_ok=True)

        for idx in range(int(count_per_stage)):
            source, label, boundary, centerline, distance, meta = generate_boundary_image(
                spec,
                index=idx,
                size=size,
                base_seed=base_seed,
            )
            stem = f"{idx:04d}"
            cv2.imwrite(str(clean_root / spec.name / f"{stem}.bmp"), label)
            cv2.imwrite(str(source_root / spec.name / f"{stem}.bmp"), source)
            cv2.imwrite(str(geom_root / "boundary" / spec.name / f"{stem}.bmp"), boundary)
            cv2.imwrite(str(geom_root / "centerline" / spec.name / f"{stem}.bmp"), centerline)
            np.save(geom_root / "distance" / spec.name / f"{stem}.npy", distance)
            (geom_root / "meta" / spec.name / f"{stem}.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        stages.append(
            {
                "stage": spec.name,
                "stage_id": spec.stage_id,
                "feature_family": spec.feature_family,
                "count": int(count_per_stage),
                "description": spec.description,
            }
        )

    manifest = {
        "generator": "r42_boundary_v1",
        "clean_root": str(clean_root),
        "source_root": str(source_root),
        "geom_root": str(geom_root),
        "image_size": int(size),
        "base_seed": int(base_seed),
        "stages": stages,
    }
    (geom_root / "r42_boundary_geometry_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def collect_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _convert_r40_pair(pair) -> Pair:
    return Pair(
        src=Path(pair.src),
        lbl=Path(pair.lbl),
        role=str(pair.role),
        stage=str(pair.stage),
        rel_dir=Path(pair.rel_dir),
        feature_family=getattr(pair, "feature_family", None),
        geometry=None,
    )


def _balanced_stage_pairs(repo_root: Path, stages: tuple[str, ...], *, role: str, total: int, start_index: int) -> list[Pair]:
    if total <= 0:
        return []
    base = int(total) // len(stages)
    remainder = int(total) % len(stages)
    out: list[Pair] = []
    for idx, stage in enumerate(stages):
        per_stage = base + (1 if idx < remainder else 0)
        out.extend(_convert_r40_pair(p) for p in r40_stage_pairs(repo_root, (stage,), role=role, per_stage=per_stage, start_index=start_index))
    return out


def _boundary_stage_pairs(repo_root: Path, *, per_stage: int, start_index: int) -> list[Pair]:
    if per_stage <= 0:
        return []
    out: list[Pair] = []
    source_root = repo_root / "Training_Data" / "generated_convolved"
    clean_root = repo_root / "Training_Data" / "generated"
    geom_root = repo_root / "Training_Data" / "r42_boundary_geometry"
    for stage in BOUNDARY_STAGES:
        src_dir = source_root / stage
        lbl_dir = clean_root / stage
        src_files = collect_images(src_dir)
        start = int(start_index)
        end = start + int(per_stage)
        if len(src_files) < end:
            raise ValueError(f"{stage} has only {len(src_files)} images; requires index range [{start}, {end}).")
        for src in src_files[start:end]:
            lbl = lbl_dir / src.name
            rel_no_ext = src.with_suffix("").name
            geom = GeometryPaths(
                boundary=geom_root / "boundary" / stage / src.name,
                centerline=geom_root / "centerline" / stage / src.name,
                distance=geom_root / "distance" / stage / f"{rel_no_ext}.npy",
                meta=geom_root / "meta" / stage / f"{rel_no_ext}.json",
            )
            missing = [p for p in (lbl, geom.boundary, geom.centerline, geom.distance) if not p.exists()]
            if missing:
                raise ValueError(f"{stage}/{src.name} has missing label or geometry sidecars: {missing}")
            out.append(
                Pair(
                    src=src,
                    lbl=lbl,
                    role="boundary",
                    stage=stage,
                    rel_dir=Path(stage),
                    feature_family=BOUNDARY_STAGE_FAMILIES.get(stage),
                    geometry=geom,
                )
            )
    return out


def build_plan(repo_root: Path | str, profile: R42Profile) -> DatasetPlan:
    root = Path(repo_root).resolve()
    pairs: list[Pair] = []
    if profile.include_ring:
        pairs.extend(_convert_r40_pair(p) for p in r40_ring_pairs(root, profile.ring_limit))
    pairs.extend(_balanced_stage_pairs(root, SHAPE_STAGES, role="shape", total=profile.shape_total, start_index=profile.shape_start_index))
    pairs.extend(_balanced_stage_pairs(root, MICRO_STAGES, role="micro", total=profile.micro_total, start_index=profile.micro_start_index))
    pairs.extend(_boundary_stage_pairs(root, per_stage=profile.boundary_per_stage, start_index=profile.boundary_start_index))
    if not pairs:
        raise ValueError(f"profile {profile.name} produced no image pairs")
    return DatasetPlan(profile=profile, repo_root=root, pairs=tuple(pairs))


def assert_disjoint_plans(*plans: DatasetPlan) -> None:
    seen: dict[Path, str] = {}
    for plan in plans:
        for src in plan.source_paths:
            resolved = src.resolve()
            if resolved in seen:
                raise ValueError(f"data split overlap: {resolved} appears in both {seen[resolved]} and {plan.profile.name}")
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


def _blank_geometry_for_label(label_path: Path, out_root: Path, rel_path: Path) -> tuple[Path, Path, Path]:
    label = cv2.imread(str(label_path), cv2.IMREAD_GRAYSCALE)
    if label is None:
        raise RuntimeError(f"failed to read label for blank geometry: {label_path}")
    zero = np.zeros_like(label, dtype=np.uint8)
    dist = np.full(label.shape, 999.0, dtype=np.float32)
    boundary_dst = out_root / "geom" / "boundary" / rel_path
    center_dst = out_root / "geom" / "centerline" / rel_path
    dist_dst = out_root / "geom" / "distance" / rel_path.with_suffix(".npy")
    boundary_dst.parent.mkdir(parents=True, exist_ok=True)
    center_dst.parent.mkdir(parents=True, exist_ok=True)
    dist_dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(boundary_dst), zero)
    cv2.imwrite(str(center_dst), zero)
    np.save(dist_dst, dist)
    return boundary_dst, center_dst, dist_dst


def materialize_plan_with_geometry(
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
    for pair in plan.pairs:
        src_rel = Path("src") / pair.rel_dir / pair.filename
        lbl_rel = Path("lbl") / pair.rel_dir / pair.filename
        rel_path = pair.rel_dir / pair.filename
        link_counts[_place_file(pair.src, out / src_rel, link_mode)] += 1
        link_counts[_place_file(pair.lbl, out / lbl_rel, link_mode)] += 1
        if pair.geometry is None:
            boundary_dst, center_dst, dist_dst = _blank_geometry_for_label(pair.lbl, out, rel_path)
            geom_mode = "blank"
        else:
            boundary_rel = Path("geom") / "boundary" / rel_path
            center_rel = Path("geom") / "centerline" / rel_path
            dist_rel = Path("geom") / "distance" / rel_path.with_suffix(".npy")
            meta_rel = Path("geom") / "meta" / rel_path.with_suffix(".json")
            link_counts[_place_file(pair.geometry.boundary, out / boundary_rel, link_mode)] += 1
            link_counts[_place_file(pair.geometry.centerline, out / center_rel, link_mode)] += 1
            link_counts[_place_file(pair.geometry.distance, out / dist_rel, link_mode)] += 1
            if pair.geometry.meta and pair.geometry.meta.exists():
                link_counts[_place_file(pair.geometry.meta, out / meta_rel, link_mode)] += 1
            boundary_dst, center_dst, dist_dst = out / boundary_rel, out / center_rel, out / dist_rel
            geom_mode = "source"
        records.append(
            {
                "role": pair.role,
                "stage": pair.stage,
                "feature_family": pair.feature_family,
                "src": str(pair.src),
                "lbl": str(pair.lbl),
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "package_boundary": boundary_dst.relative_to(out).as_posix(),
                "package_centerline": center_dst.relative_to(out).as_posix(),
                "package_distance": dist_dst.relative_to(out).as_posix(),
                "geometry_mode": geom_mode,
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
        "shape_stages": list(SHAPE_STAGES),
        "micro_stages": list(MICRO_STAGES),
        "boundary_stages": list(BOUNDARY_STAGES),
        "boundary_stage_families": BOUNDARY_STAGE_FAMILIES,
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_data_package(
    profile_name: str,
    output_root: Path = DEFAULT_DATA_ROOT,
    *,
    build_data: bool = False,
    force_data: bool = False,
    link_mode: str = "auto",
) -> tuple[Path, dict]:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown R42 profile: {profile_name}")
    package_dir = Path(output_root).resolve() / profile_name
    plan = build_plan(REPO_ROOT, PROFILES[profile_name])
    if build_data:
        manifest = materialize_plan_with_geometry(plan, package_dir, force=force_data, link_mode=link_mode)
    else:
        manifest = _load_manifest(package_dir / "manifest.json")
    if manifest.get("profile") != profile_name:
        raise RuntimeError(f"manifest profile mismatch in {package_dir}")
    if int(manifest.get("total_pairs", -1)) != len(plan.pairs):
        raise RuntimeError(f"manifest pair count mismatch in {package_dir}")
    return package_dir, manifest


def _profiles_from_cli(profile_name: str) -> Iterable[R42Profile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate R42 boundary-fidelity data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate R42 clean/source/geometry pools.")
    gen.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    gen.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    gen.add_argument("--geom-root", type=Path, default=DEFAULT_GEOM_ROOT)
    gen.add_argument("--count-per-stage", type=int, default=100)
    gen.add_argument("--size", type=int, default=512)
    gen.add_argument("--base-seed", type=int, default=4200)
    gen.add_argument("--force", action="store_true")

    for cmd in ("plan", "build"):
        p = sub.add_parser(cmd)
        p.add_argument("--profile", default="all", choices=[*PROFILES.keys(), "all"])
        p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
        p.add_argument("--output-root", type=Path, default=DEFAULT_DATA_ROOT)
        p.add_argument("--force", action="store_true")
        p.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")

    check = sub.add_parser("validate-splits")
    check.add_argument("--train-profile", default="r42_boundary_research_train", choices=sorted(PROFILES))
    check.add_argument("--val-profile", default="boundary_val_unseen", choices=sorted(PROFILES))
    check.add_argument("--repo-root", type=Path, default=REPO_ROOT)

    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest = generate_boundary_dataset(
            clean_root=args.clean_root,
            source_root=args.source_root,
            geom_root=args.geom_root,
            count_per_stage=args.count_per_stage,
            size=args.size,
            base_seed=args.base_seed,
            force=args.force,
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    if args.command == "validate-splits":
        train = build_plan(args.repo_root, PROFILES[args.train_profile])
        val = build_plan(args.repo_root, PROFILES[args.val_profile])
        assert_disjoint_plans(train, val)
        print(json.dumps({"status": "ok", "train": args.train_profile, "val": args.val_profile}, indent=2, ensure_ascii=False))
        return 0

    summaries = []
    for profile in _profiles_from_cli(args.profile):
        plan = build_plan(args.repo_root, profile)
        summary = {
            "profile": profile.name,
            "total_pairs": len(plan.pairs),
            "count_by_role": plan.count_by_role,
            "count_by_stage": plan.count_by_stage,
        }
        if args.command == "build":
            manifest = materialize_plan_with_geometry(
                plan,
                args.output_root / profile.name,
                force=bool(args.force),
                link_mode=args.link_mode,
            )
            summary["output_dir"] = manifest["output_dir"]
            summary["link_counts"] = manifest["link_counts"]
        summaries.append(summary)
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
