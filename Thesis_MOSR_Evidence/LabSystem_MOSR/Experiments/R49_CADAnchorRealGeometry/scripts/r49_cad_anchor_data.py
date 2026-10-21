"""R49 Lab CAD-anchor real-geometry data package builder.

R49 keeps the R48 package mechanics, but replaces the oversized synthetic
corner emphasis with a small set of real CAD-reference checkboard anchors.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}
REPO_ROOT = Path(__file__).resolve().parents[3]
THESIS_ROOT = REPO_ROOT.parent
EXPERIMENTS_ROOT = Path(__file__).resolve().parents[2]
R48_SCRIPT_DIR = EXPERIMENTS_ROOT / "R48_RealCornerTransfer" / "scripts"
if str(R48_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R48_SCRIPT_DIR))

from r48_real_corner_data import (  # noqa: E402
    STAGE_53_REAL_CORNER,
    STAGE_54_LATTICE_INTERSECTIONS,
    STAGE_55_REAL_TEXTURE,
    STAGE_56_CORNER_PSF_STRESS,
    compute_geometry_from_label,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r49_cad_anchor_real_geometry"
DEFAULT_ANCHOR_ROOT = REPO_ROOT / "Training_Data" / "r49_cad_anchor_source"
DEFAULT_CAD_PAIRS_CSV = (
    REPO_ROOT
    / "Reconstruct_Progress"
    / "20260613_checkboard_cad_reference_strict_rect"
    / "data_pairs_valid.csv"
)
DEFAULT_PREVIEW_PATH = REPO_ROOT / "Training_Data" / "reports" / "r49_cad_anchor_preview.png"

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
TRAIN_R48_BOUNDARY_QUOTAS = {
    STAGE_53_REAL_CORNER: 500,
    STAGE_54_LATTICE_INTERSECTIONS: 300,
    STAGE_56_CORNER_PSF_STRESS: 200,
}
TRAIN_R48_REAL_BG_QUOTAS = {STAGE_55_REAL_TEXTURE: 500}

NEW_STAGE_FAMILIES = {
    STAGE_53_REAL_CORNER: "r48_real_corner_replay_reduced",
    STAGE_54_LATTICE_INTERSECTIONS: "r48_lattice_replay_reduced",
    STAGE_55_REAL_TEXTURE: "r48_real_texture_replay_reduced",
    STAGE_56_CORNER_PSF_STRESS: "r48_psf_stress_replay_reduced",
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
    cad_anchor_quota: int
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
    source_cad_pair_id: str | None = None

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


PROFILES: dict[str, Profile] = {
    "r49_cad_anchor_train_4000": Profile(
        name="r49_cad_anchor_train_4000",
        include_ring=True,
        ring_limit=700,
        shape_quotas=TRAIN_SHAPE_QUOTAS,
        micro_quotas=TRAIN_MICRO_QUOTAS,
        boundary_quotas=TRAIN_R48_BOUNDARY_QUOTAS,
        real_bg_quotas=TRAIN_R48_REAL_BG_QUOTAS,
        cad_anchor_quota=400,
        description=(
            "Lab R49 CAD-anchor package: 700 ring, 700 shape, 700 micro, "
            "1000 reduced R48 synthetic boundary replay, 500 reduced real-texture "
            "replay, and 400 real CAD checkboard anchor patches."
        ),
    ),
    "cad_anchor_val_real": Profile(
        name="cad_anchor_val_real",
        include_ring=False,
        ring_limit=None,
        shape_quotas={},
        micro_quotas={},
        boundary_quotas={},
        real_bg_quotas={},
        cad_anchor_quota=120,
        description="Held-out real CAD checkboard anchor validation patches.",
    ),
}


def _safe_remove_tree(path: Path, root: Path | None = None) -> None:
    resolved = path.resolve()
    if root is not None:
        root_resolved = root.resolve()
        if not str(resolved).lower().startswith(str(root_resolved).lower()):
            raise ValueError(f"refusing to remove outside root: {resolved}")
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
    shutil.rmtree(resolved)


def _read_gray(path: Path) -> np.ndarray:
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


def collect_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _write_geometry_sidecars(lbl_path: Path, geom_dir: Path, rel_path: Path) -> None:
    img = _read_gray(lbl_path)
    boundary, centerline, distance = compute_geometry_from_label(img)
    boundary_path = geom_dir / "boundary" / rel_path
    centerline_path = geom_dir / "centerline" / rel_path
    distance_path = geom_dir / "distance" / rel_path.with_suffix(".npy")
    _write_image(boundary_path, boundary)
    _write_image(centerline_path, centerline)
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))


def load_cad_rows(csv_path: Path | str) -> list[dict[str, str]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [dict(row) for row in csv.DictReader(f)]
    valid = [row for row in rows if str(row.get("valid_for_training", "")).strip().lower() == "yes"]
    for row in valid:
        for key in ("pair_id", "source_image", "gt_image", "reliable_mask"):
            if not str(row.get(key, "")).strip():
                raise ValueError(f"CAD pair row missing {key}: {row}")
    return valid


def split_cad_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    ordered = sorted(rows, key=lambda row: str(row["pair_id"]))
    n = len(ordered)
    if n < 3:
        raise ValueError("at least 3 valid CAD rows are required")
    val_count = max(1, n // 6)
    test_count = max(1, n // 6)
    train_count = n - val_count - test_count
    if train_count <= 0:
        raise ValueError(f"not enough CAD rows for train/val/test split: {n}")
    return {
        "train": ordered[:train_count],
        "val": ordered[train_count : train_count + val_count],
        "test": ordered[train_count + val_count :],
    }


def _crop_patch(image: np.ndarray, x0: int, y0: int, size: int) -> np.ndarray:
    return image[y0 : y0 + size, x0 : x0 + size]


def _choose_patch_origin(
    mask: np.ndarray,
    patch_size: int,
    rng: np.random.Generator,
    *,
    max_attempts: int = 80,
    min_trusted_ratio: float = 0.035,
) -> tuple[int, int, float]:
    h, w = mask.shape
    if patch_size > h or patch_size > w:
        raise ValueError(f"patch_size={patch_size} exceeds image shape={mask.shape}")
    coords = np.column_stack(np.nonzero(mask > 0))
    if coords.size == 0:
        raise ValueError("CAD reliable mask has no trusted pixels")
    best: tuple[int, int, float] | None = None
    for _ in range(max_attempts):
        cy, cx = coords[int(rng.integers(0, len(coords)))]
        jitter = int(max(2, patch_size // 7))
        cx = int(cx + rng.integers(-jitter, jitter + 1))
        cy = int(cy + rng.integers(-jitter, jitter + 1))
        x0 = int(np.clip(cx - patch_size // 2, 0, w - patch_size))
        y0 = int(np.clip(cy - patch_size // 2, 0, h - patch_size))
        ratio = float(np.count_nonzero(_crop_patch(mask, x0, y0, patch_size))) / float(patch_size * patch_size)
        if best is None or ratio > best[2]:
            best = (x0, y0, ratio)
        if ratio >= min_trusted_ratio:
            return x0, y0, ratio
    assert best is not None
    return best


def _make_anchor_label(src_patch: np.ndarray, gt_patch: np.ndarray, mask_patch: np.ndarray) -> np.ndarray:
    trusted = mask_patch > 0
    label = src_patch.copy()
    label[trusted] = gt_patch[trusted]
    return label


def generate_cad_anchor_dataset(
    csv_path: Path | str = DEFAULT_CAD_PAIRS_CSV,
    output_root: Path | str = DEFAULT_ANCHOR_ROOT,
    *,
    patch_size: int = 512,
    train_patches_per_pair: int = 17,
    val_patches_per_pair: int = 20,
    test_patches_per_pair: int = 8,
    base_seed: int = 4949,
    force: bool = False,
) -> dict:
    out = Path(output_root).resolve()
    if out.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {out}")
        _safe_remove_tree(out)
    out.mkdir(parents=True, exist_ok=True)

    rows = load_cad_rows(csv_path)
    splits = split_cad_rows(rows)
    per_split = {
        "train": int(train_patches_per_pair),
        "val": int(val_patches_per_pair),
        "test": int(test_patches_per_pair),
    }
    records = []
    for split, split_rows in splits.items():
        for row_idx, row in enumerate(split_rows):
            source = _read_gray(Path(row["source_image"]))
            gt = _read_gray(Path(row["gt_image"]))
            mask = _read_gray(Path(row["reliable_mask"]))
            if source.shape != gt.shape or source.shape != mask.shape:
                raise ValueError(f"CAD shape mismatch for {row['pair_id']}")
            actual_patch_size = int(min(int(patch_size), source.shape[0], source.shape[1]))
            for patch_idx in range(per_split[split]):
                rng = np.random.default_rng(
                    int(base_seed) + row_idx * 10_000 + patch_idx * 101 + {"train": 1, "val": 2, "test": 3}[split]
                )
                x0, y0, trusted_ratio = _choose_patch_origin(mask, actual_patch_size, rng)
                src_patch = _crop_patch(source, x0, y0, actual_patch_size)
                gt_patch = _crop_patch(gt, x0, y0, actual_patch_size)
                mask_patch = _crop_patch(mask, x0, y0, actual_patch_size)
                lbl_patch = _make_anchor_label(src_patch, gt_patch, mask_patch)
                name = f"{row['pair_id']}_{split}_{patch_idx:03d}.bmp"
                src_rel = Path(split) / "src" / "cad_anchor" / name
                lbl_rel = Path(split) / "lbl" / "cad_anchor" / name
                mask_rel = Path(split) / "mask" / "cad_anchor" / name
                _write_image(out / src_rel, src_patch)
                _write_image(out / lbl_rel, lbl_patch)
                _write_image(out / mask_rel, mask_patch)
                records.append(
                    {
                        "split": split,
                        "pair_id": row["pair_id"],
                        "patch_index": int(patch_idx),
                        "src": src_rel.as_posix(),
                        "lbl": lbl_rel.as_posix(),
                        "mask": mask_rel.as_posix(),
                        "source_image": row["source_image"],
                        "gt_image": row["gt_image"],
                        "reliable_mask": row["reliable_mask"],
                        "x0": int(x0),
                        "y0": int(y0),
                        "patch_size": int(actual_patch_size),
                        "trusted_ratio": float(trusted_ratio),
                        "component_count": int(float(row.get("component_count", 0) or 0)),
                        "edge_p95_px": float(row.get("edge_p95_px", 0) or 0),
                    }
                )

    manifest = {
        "generator": "r49_cad_anchor_real_geometry_v1",
        "csv_path": str(Path(csv_path).resolve()),
        "output_root": str(out),
        "patch_size": int(patch_size),
        "base_seed": int(base_seed),
        "valid_pair_count": len(rows),
        "split_pair_counts": {split: len(split_rows) for split, split_rows in splits.items()},
        "split_patch_counts": dict(Counter(record["split"] for record in records)),
        "label_policy": "label equals CAD GT inside reliable_mask; label equals source outside reliable_mask",
        "records": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


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
            pairs.append(Pair(src=src, lbl=lbl_dir / src.name, role=role, stage=stage, rel_dir=rel_dir, feature_family=family))
    return pairs


def _cad_anchor_pairs(anchor_root: Path, split: str, quota: int) -> list[Pair]:
    manifest_path = anchor_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"CAD anchor manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = [record for record in manifest.get("records", []) if record.get("split") == split]
    if len(records) < int(quota):
        raise ValueError(f"CAD anchor split {split} has {len(records)} patches; requires {quota}")
    pairs = []
    for record in records[: int(quota)]:
        pairs.append(
            Pair(
                src=anchor_root / record["src"],
                lbl=anchor_root / record["lbl"],
                role="cad_anchor",
                stage=f"cad_anchor_{split}",
                rel_dir=Path("stage_40_boundary_mixed") / "stage_57_cad_anchor_real" / split,
                feature_family="real_cad_checkboard_anchor",
                source_cad_pair_id=str(record["pair_id"]),
            )
        )
    return pairs


def build_plan(
    repo_root: Path | str,
    profile: Profile,
    *,
    anchor_root: Path | str = DEFAULT_ANCHOR_ROOT,
) -> DatasetPlan:
    root = Path(repo_root).resolve()
    pairs: list[Pair] = []
    if profile.include_ring:
        pairs.extend(_ring_pairs(root, profile.ring_limit))
    pairs.extend(_quota_stage_pairs(root, profile.shape_quotas, role="shape", start_offsets=profile.start_offsets))
    pairs.extend(_quota_stage_pairs(root, profile.micro_quotas, role="micro", start_offsets=profile.start_offsets))
    pairs.extend(_quota_stage_pairs(root, profile.boundary_quotas, role="boundary", start_offsets=profile.start_offsets))
    pairs.extend(_quota_stage_pairs(root, profile.real_bg_quotas, role="real_bg", start_offsets=profile.start_offsets))
    if int(profile.cad_anchor_quota) > 0:
        split = "train" if profile.name == "r49_cad_anchor_train_4000" else "val"
        pairs.extend(_cad_anchor_pairs(Path(anchor_root), split, profile.cad_anchor_quota))
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
        record = {
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
        if pair.source_cad_pair_id is not None:
            record["source_cad_pair_id"] = pair.source_cad_pair_id
        records.append(record)

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
        "cad_anchor_policy": "small-ratio real CAD checkboard anchors, masked by label blending before packaging",
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def create_preview(
    anchor_root: Path | str = DEFAULT_ANCHOR_ROOT,
    output_path: Path | str = DEFAULT_PREVIEW_PATH,
    *,
    max_items: int = 12,
    tile_size: int = 160,
) -> dict:
    root = Path(anchor_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    records = [r for r in manifest["records"] if r["split"] == "train"][: int(max_items)]
    if not records:
        raise FileNotFoundError(f"no train CAD anchor records under {root}")
    tiles = []
    for record in records:
        src = _read_gray(root / record["src"])
        lbl = _read_gray(root / record["lbl"])
        mask = _read_gray(root / record["mask"])
        tile = np.concatenate([src, lbl, mask], axis=1)
        tile = cv2.resize(tile, (tile_size * 3, tile_size), interpolation=cv2.INTER_AREA)
        tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
        cv2.putText(tile, str(record["pair_id"]), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    cols = 2
    rows = int(np.ceil(len(tiles) / cols))
    sheet = np.full((rows * tile_size, cols * tile_size * 3, 3), 245, dtype=np.uint8)
    for idx, tile in enumerate(tiles):
        r, c = divmod(idx, cols)
        sheet[r * tile_size : (r + 1) * tile_size, c * tile_size * 3 : (c + 1) * tile_size * 3] = tile
    out = Path(output_path)
    _write_image(out, sheet)
    return {"preview": str(out), "tiles": len(tiles)}


def _profiles_from_cli(profile_name: str) -> Iterable[Profile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate Lab R49 CAD-anchor real-geometry data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    cad = sub.add_parser("generate-cad-anchors", help="Generate masked real CAD checkboard anchor patches.")
    cad.add_argument("--csv-path", type=Path, default=DEFAULT_CAD_PAIRS_CSV)
    cad.add_argument("--output-root", type=Path, default=DEFAULT_ANCHOR_ROOT)
    cad.add_argument("--patch-size", type=int, default=512)
    cad.add_argument("--train-patches-per-pair", type=int, default=17)
    cad.add_argument("--val-patches-per-pair", type=int, default=20)
    cad.add_argument("--test-patches-per-pair", type=int, default=8)
    cad.add_argument("--base-seed", type=int, default=4949)
    cad.add_argument("--force", action="store_true")

    preview = sub.add_parser("preview", help="Create a CAD-anchor preview contact sheet.")
    preview.add_argument("--anchor-root", type=Path, default=DEFAULT_ANCHOR_ROOT)
    preview.add_argument("--output-path", type=Path, default=DEFAULT_PREVIEW_PATH)

    for cmd in ("plan", "build", "validate-splits"):
        p = sub.add_parser(cmd)
        p.add_argument("--profile", default="all", choices=[*PROFILES.keys(), "all"])
        p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
        p.add_argument("--anchor-root", type=Path, default=DEFAULT_ANCHOR_ROOT)
        p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
        p.add_argument("--force", action="store_true")
        p.add_argument("--link-mode", default="auto", choices=["auto", "hardlink", "copy"])

    args = parser.parse_args(argv)

    if args.command == "generate-cad-anchors":
        manifest = generate_cad_anchor_dataset(
            args.csv_path,
            args.output_root,
            patch_size=args.patch_size,
            train_patches_per_pair=args.train_patches_per_pair,
            val_patches_per_pair=args.val_patches_per_pair,
            test_patches_per_pair=args.test_patches_per_pair,
            base_seed=args.base_seed,
            force=args.force,
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    if args.command == "preview":
        summary = create_preview(args.anchor_root, args.output_path)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    summaries = []
    plans = []
    for profile in _profiles_from_cli(args.profile):
        plan = build_plan(args.repo_root, profile, anchor_root=args.anchor_root)
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
