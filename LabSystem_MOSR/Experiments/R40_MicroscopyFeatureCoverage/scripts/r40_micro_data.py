"""R40 microscopy-feature data package builder.

The clean synthetic labels and materialized training packages live under
Training_Data/ and stay out of Git. This module keeps the repeatable recipe,
source/label pairing checks, and train/validation split rules in source.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r40_microscopy_feature_coverage"
DEFAULT_CLEAN_ROOT = REPO_ROOT / "Training_Data" / "generated"

SHAPE_STAGES = (
    "stage_01_triangles",
    "stage_02_circles",
    "stage_03_rectangles",
    "stage_04_ellipses",
    "stage_05_polygons",
    "stage_06_mixed_simple",
    "stage_07_mixed_complex",
)


@dataclass(frozen=True)
class MicroStageSpec:
    stage_id: int
    name: str
    feature_family: str
    description: str


MICRO_STAGE_SPECS: tuple[MicroStageSpec, ...] = (
    MicroStageSpec(
        29,
        "stage_29_micro_lines_grid",
        "lines_grid",
        "Thin lines, grids, crossed lines, multiple pitch/orientation settings.",
    ),
    MicroStageSpec(
        30,
        "stage_30_micro_large_regions",
        "large_regions",
        "Large bright/dark IC-like regions, plateaus, rectangular boundaries.",
    ),
    MicroStageSpec(
        31,
        "stage_31_micro_textures",
        "textures",
        "Granular and low-contrast surface textures with mild periodic content.",
    ),
    MicroStageSpec(
        32,
        "stage_32_micro_edge_defects",
        "edge_defects",
        "Jagged edges, chips, scratches, dark/bright defects.",
    ),
    MicroStageSpec(
        33,
        "stage_33_micro_mixed_fields",
        "mixed_fields",
        "Combined grid, texture, region, marker, and defect scenes.",
    ),
)
MICRO_STAGES = tuple(spec.name for spec in MICRO_STAGE_SPECS)
MICRO_STAGE_FAMILIES = {spec.name: spec.feature_family for spec in MICRO_STAGE_SPECS}


@dataclass(frozen=True)
class Profile:
    name: str
    include_ring: bool
    ring_limit: int | None
    shape_per_stage: int
    shape_start_index: int
    micro_per_stage: int
    micro_start_index: int
    description: str


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


PROFILES: dict[str, Profile] = {
    "r40_micro_capacity_train": Profile(
        name="r40_micro_capacity_train",
        include_ring=True,
        ring_limit=550,
        shape_per_stage=50,
        shape_start_index=0,
        micro_per_stage=80,
        micro_start_index=0,
        description=(
            "Capacity mix: partial ring replay, R39 shape replay, and a high-ratio "
            "microscopy-feature synthetic set."
        ),
    ),
    "micro_val_unseen": Profile(
        name="micro_val_unseen",
        include_ring=False,
        ring_limit=None,
        shape_per_stage=0,
        shape_start_index=0,
        micro_per_stage=20,
        micro_start_index=80,
        description="Held-out unseen microscopy-feature validation set.",
    ),
}


# ---------------------------------------------------------------------------
# synthetic clean-image generation
# ---------------------------------------------------------------------------


def _rng_for(spec: MicroStageSpec, index: int, base_seed: int) -> np.random.Generator:
    return np.random.default_rng(int(base_seed) + spec.stage_id * 10_000 + int(index))


def _clip_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def _draw_lines_grid(img: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    bg = int(rng.integers(20, 55))
    img[:, :] = bg
    if rng.random() < 0.75:
        x0 = int(rng.integers(w // 10, w // 3))
        y0 = int(rng.integers(h // 10, h // 3))
        x1 = int(rng.integers(2 * w // 3, 9 * w // 10))
        y1 = int(rng.integers(2 * h // 3, 9 * h // 10))
        cv2.rectangle(img, (x0, y0), (x1, y1), int(rng.integers(65, 120)), -1)
    pitch = int(rng.integers(max(6, w // 36), max(12, w // 8)))
    offset = int(rng.integers(0, pitch))
    width = int(rng.integers(1, 4))
    color = int(rng.integers(155, 235))
    mode = int(rng.integers(0, 5))
    if mode in {0, 2, 4}:
        for x in range(offset, w, pitch):
            cv2.line(img, (x, 0), (x, h - 1), color, width)
    if mode in {1, 2, 4}:
        for y in range(offset, h, pitch):
            cv2.line(img, (0, y), (w - 1, y), color, width)
    if mode in {3, 4}:
        for k in range(-h, w + h, pitch):
            cv2.line(img, (k, 0), (k + h, h - 1), color, width)
        if rng.random() < 0.5:
            for k in range(0, w + h, pitch):
                cv2.line(img, (k, 0), (k - h, h - 1), color, width)


def _draw_large_regions(img: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    img[:, :] = int(rng.integers(10, 45))
    for _ in range(int(rng.integers(2, 5))):
        x0 = int(rng.integers(0, w * 2 // 3))
        y0 = int(rng.integers(0, h * 2 // 3))
        x1 = int(rng.integers(max(x0 + 20, w // 3), w))
        y1 = int(rng.integers(max(y0 + 20, h // 3), h))
        value = int(rng.integers(80, 220))
        cv2.rectangle(img, (x0, y0), (x1, y1), value, -1)
        cv2.rectangle(img, (x0, y0), (x1, y1), int(min(255, value + rng.integers(10, 35))), 2)
    if rng.random() < 0.6:
        center = (int(rng.integers(w // 4, 3 * w // 4)), int(rng.integers(h // 4, 3 * h // 4)))
        axes = (int(rng.integers(w // 8, w // 3)), int(rng.integers(h // 10, h // 3)))
        cv2.ellipse(img, center, axes, float(rng.uniform(0, 180)), 0, 360, int(rng.integers(70, 180)), -1)


def _draw_textures(img: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    base = np.full((h, w), float(rng.integers(40, 100)), dtype=np.float32)
    small = rng.normal(0, 1, size=(max(8, h // 16), max(8, w // 16))).astype(np.float32)
    texture = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    texture = cv2.GaussianBlur(texture, (0, 0), sigmaX=float(rng.uniform(0.8, 2.0)))
    texture = texture / (float(np.std(texture)) + 1e-6)
    img_f = base + texture * float(rng.uniform(8, 24))
    yy, xx = np.mgrid[0:h, 0:w]
    period = float(rng.uniform(max(8, w // 40), max(18, w // 12)))
    angle = float(rng.uniform(0, np.pi))
    phase = float(rng.uniform(0, np.pi * 2))
    wave = np.sin((np.cos(angle) * xx + np.sin(angle) * yy) / period * np.pi * 2 + phase)
    img_f += wave * float(rng.uniform(4, 18))
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(
        mask,
        (int(w * 0.08), int(h * 0.08)),
        (int(w * 0.92), int(h * 0.92)),
        255,
        -1,
    )
    img_f = np.where(mask > 0, img_f, rng.integers(12, 35))
    img[:, :] = _clip_u8(img_f)


def _jagged_rect_points(
    x0: int, y0: int, x1: int, y1: int, rng: np.random.Generator, n: int = 12
) -> np.ndarray:
    pts: list[tuple[int, int]] = [(x0, y0), (x1, y0)]
    for i in range(n + 1):
        t = i / max(1, n)
        y = int(y0 + t * (y1 - y0))
        jitter = int(rng.integers(-10, 16))
        pts.append((x1 + jitter, y))
    pts += [(x0, y1)]
    return np.asarray(pts, dtype=np.int32)


def _draw_edge_defects(img: np.ndarray, rng: np.random.Generator) -> None:
    h, w = img.shape
    img[:, :] = int(rng.integers(15, 45))
    x0, y0 = int(w * 0.16), int(h * 0.16)
    x1, y1 = int(w * 0.82), int(h * 0.84)
    poly = _jagged_rect_points(x0, y0, x1, y1, rng)
    body = int(rng.integers(95, 185))
    cv2.fillPoly(img, [poly], body)
    cv2.polylines(img, [poly], True, int(min(255, body + 35)), 2)
    for _ in range(int(rng.integers(10, 24))):
        x = int(rng.integers(x0, x1))
        y = int(rng.integers(y0, y1))
        radius = int(rng.integers(2, 8))
        value = int(rng.choice([rng.integers(20, 65), rng.integers(190, 245)]))
        cv2.circle(img, (x, y), radius, value, -1)
    for _ in range(int(rng.integers(3, 8))):
        p0 = (int(rng.integers(x0, x1)), int(rng.integers(y0, y1)))
        p1 = (int(np.clip(p0[0] + rng.integers(-50, 50), x0, x1)), int(np.clip(p0[1] + rng.integers(-50, 50), y0, y1)))
        cv2.line(img, p0, p1, int(rng.integers(25, 80)), int(rng.integers(1, 3)))


def _draw_mixed_fields(img: np.ndarray, rng: np.random.Generator) -> None:
    _draw_large_regions(img, rng)
    h, w = img.shape
    overlay = img.copy()
    pitch = int(rng.integers(max(8, w // 34), max(14, w // 13)))
    grid_value = int(rng.integers(160, 235))
    for x in range(int(rng.integers(0, pitch)), w, pitch):
        cv2.line(overlay, (x, int(h * 0.18)), (x, int(h * 0.82)), grid_value, 1)
    for y in range(int(rng.integers(0, pitch)), h, pitch):
        cv2.line(overlay, (int(w * 0.18), y), (int(w * 0.82), y), grid_value, 1)
    img[:, :] = cv2.addWeighted(img, 0.68, overlay, 0.32, 0)
    noise = rng.normal(0, float(rng.uniform(4, 15)), size=img.shape)
    img[:, :] = _clip_u8(img.astype(np.float32) + noise)
    tri = np.asarray(
        [
            (int(w * 0.12), int(h * 0.72)),
            (int(w * 0.24), int(h * 0.55)),
            (int(w * 0.34), int(h * 0.78)),
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(img, [tri], int(rng.integers(140, 230)))
    for _ in range(int(rng.integers(8, 20))):
        cv2.circle(
            img,
            (int(rng.integers(w // 5, 4 * w // 5)), int(rng.integers(h // 5, 4 * h // 5))),
            int(rng.integers(1, 5)),
            int(rng.integers(15, 80)),
            -1,
        )


def generate_micro_image(
    spec: MicroStageSpec,
    *,
    index: int,
    size: int = 512,
    base_seed: int = 4040,
) -> np.ndarray:
    rng = _rng_for(spec, index, base_seed)
    img = np.zeros((int(size), int(size)), dtype=np.uint8)
    drawers = {
        "lines_grid": _draw_lines_grid,
        "large_regions": _draw_large_regions,
        "textures": _draw_textures,
        "edge_defects": _draw_edge_defects,
        "mixed_fields": _draw_mixed_fields,
    }
    drawers[spec.feature_family](img, rng)
    if rng.random() < 0.35:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def generate_clean_dataset(
    output_root: Path | str,
    *,
    count_per_stage: int = 100,
    size: int = 512,
    base_seed: int = 4040,
    force: bool = False,
) -> dict:
    out_root = Path(output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    stages = []
    for spec in MICRO_STAGE_SPECS:
        stage_dir = out_root / spec.name
        if stage_dir.exists():
            if not force and any(stage_dir.iterdir()):
                raise FileExistsError(f"stage directory already exists and is non-empty: {stage_dir}")
            if force:
                _safe_remove_tree(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(int(count_per_stage)):
            img = generate_micro_image(spec, index=idx, size=size, base_seed=base_seed)
            out_path = stage_dir / f"{idx:04d}.bmp"
            ok = cv2.imwrite(str(out_path), img)
            if not ok:
                raise RuntimeError(f"failed to write image: {out_path}")
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
        "generator": "r40_micro_v1",
        "output_root": str(out_root),
        "image_size": int(size),
        "base_seed": int(base_seed),
        "stages": stages,
        "psf_next_step": (
            "Run Training_Data/PSF_Convolution.py with RUN_STAGE_IDS=[29, 30, 31, 32, 33] "
            "before building train/validation packages."
        ),
    }
    (out_root / "r40_micro_clean_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


# ---------------------------------------------------------------------------
# pairing and packaging
# ---------------------------------------------------------------------------


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


def _stage_pairs(
    repo_root: Path,
    stages: Iterable[str],
    *,
    role: str,
    per_stage: int,
    start_index: int,
) -> list[Pair]:
    pairs: list[Pair] = []
    if per_stage <= 0:
        return pairs
    for stage in stages:
        src_files = _require_complete_stage_pairs(repo_root, stage)
        start = int(start_index)
        end = start + int(per_stage)
        if len(src_files) < end:
            raise ValueError(
                f"{stage} has only {len(src_files)} images; requires index range [{start}, {end})."
            )
        lbl_dir = repo_root / "Training_Data" / "generated" / stage
        family = MICRO_STAGE_FAMILIES.get(stage)
        for src in src_files[start:end]:
            pairs.append(
                Pair(
                    src=src,
                    lbl=lbl_dir / src.name,
                    role=role,
                    stage=stage,
                    rel_dir=Path(stage),
                    feature_family=family,
                )
            )
    return pairs


def build_plan(repo_root: Path | str, profile: Profile) -> DatasetPlan:
    root = Path(repo_root).resolve()
    pairs: list[Pair] = []
    if profile.include_ring:
        pairs.extend(_ring_pairs(root, profile.ring_limit))
    pairs.extend(
        _stage_pairs(
            root,
            SHAPE_STAGES,
            role="shape",
            per_stage=profile.shape_per_stage,
            start_index=profile.shape_start_index,
        )
    )
    pairs.extend(
        _stage_pairs(
            root,
            MICRO_STAGES,
            role="micro",
            per_stage=profile.micro_per_stage,
            start_index=profile.micro_start_index,
        )
    )
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


def _safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspiciously shallow path: {resolved}")
    shutil.rmtree(resolved)


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
    for pair in plan.pairs:
        src_rel = Path("src") / pair.rel_dir / pair.filename
        lbl_rel = Path("lbl") / pair.rel_dir / pair.filename
        link_counts[_place_file(pair.src, out / src_rel, link_mode)] += 1
        link_counts[_place_file(pair.lbl, out / lbl_rel, link_mode)] += 1
        records.append(
            {
                "role": pair.role,
                "stage": pair.stage,
                "feature_family": pair.feature_family,
                "src": str(pair.src),
                "lbl": str(pair.lbl),
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
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
        "micro_stage_families": MICRO_STAGE_FAMILIES,
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _profiles_from_cli(profile_name: str) -> Iterable[Profile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate R40 microscopy-feature data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-clean", help="Generate clean R40 microscopy labels under Training_Data/generated.")
    gen.add_argument("--output-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    gen.add_argument("--count-per-stage", type=int, default=100)
    gen.add_argument("--size", type=int, default=512)
    gen.add_argument("--base-seed", type=int, default=4040)
    gen.add_argument("--force", action="store_true")

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
            count_per_stage=args.count_per_stage,
            size=args.size,
            base_seed=args.base_seed,
            force=args.force,
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
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
        summaries.append(summary)

    if args.command == "validate-splits":
        assert_disjoint_plans(*plans)
        summaries.append({"split_validation": "disjoint"})

    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
