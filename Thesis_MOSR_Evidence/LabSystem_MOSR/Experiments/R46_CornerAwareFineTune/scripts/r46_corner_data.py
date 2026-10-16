"""R46 Lab checkboard/corner data package builder.

This is a Lab-system extension of the main-project R46 lesson: improve
corner/right-angle coverage without directly reusing the failed high-frequency
fine-tune recipe. Image payloads live under Training_Data/ and stay out of Git.
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
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r46_corner_aware_finetune"
DEFAULT_CLEAN_ROOT = REPO_ROOT / "Training_Data" / "generated"
DEFAULT_PREVIEW_PATH = REPO_ROOT / "Training_Data" / "reports" / "r46_checkboard_corner_preview.png"

SHAPE_STAGES = (
    "stage_01_triangles",
    "stage_02_circles",
    "stage_03_rectangles",
    "stage_04_ellipses",
    "stage_05_polygons",
    "stage_06_mixed_simple",
    "stage_07_mixed_complex",
)

MICRO_STAGES = (
    "stage_29_micro_lines_grid",
    "stage_30_micro_large_regions",
    "stage_31_micro_textures",
    "stage_32_micro_edge_defects",
    "stage_33_micro_mixed_fields",
)

MICRO_STAGE_FAMILIES = {
    "stage_29_micro_lines_grid": "lines_grid",
    "stage_30_micro_large_regions": "large_regions",
    "stage_31_micro_textures": "textures",
    "stage_32_micro_edge_defects": "edge_defects",
    "stage_33_micro_mixed_fields": "mixed_fields",
}

CORNER_STAGES = ("stage_48_checkboard_corners",)
CORNER_STAGE_FAMILIES = {
    "stage_48_checkboard_corners": "checkboard_corners",
}


@dataclass(frozen=True)
class Profile:
    name: str
    include_ring: bool
    ring_limit: int | None
    shape_per_stage: int
    shape_start_index: int
    micro_per_stage: int
    micro_start_index: int
    corner_per_stage: int
    corner_start_index: int
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
    "r46_checkboard_corner_train": Profile(
        name="r46_checkboard_corner_train",
        include_ring=True,
        ring_limit=550,
        shape_per_stage=50,
        shape_start_index=0,
        micro_per_stage=50,
        micro_start_index=0,
        corner_per_stage=400,
        corner_start_index=0,
        description=(
            "Lab corner-aware mix: ring replay plus R39 shape, R40 micro, and "
            "Lab checkboard/right-angle corner data."
        ),
    ),
    "checkboard_corner_val_unseen": Profile(
        name="checkboard_corner_val_unseen",
        include_ring=False,
        ring_limit=None,
        shape_per_stage=0,
        shape_start_index=0,
        micro_per_stage=0,
        micro_start_index=0,
        corner_per_stage=100,
        corner_start_index=400,
        description="Held-out Lab checkboard/right-angle corner validation set.",
    ),
}


def _rng_for(index: int, base_seed: int) -> np.random.Generator:
    return np.random.default_rng(int(base_seed) + 48_000 + int(index))


def _clip_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def generate_checkboard_corner_image(
    *,
    index: int,
    size: int = 512,
    base_seed: int = 4648,
) -> np.ndarray:
    """Generate one clean GT image with many right-angle checkerboard corners."""
    rng = _rng_for(index, base_seed)
    size = int(size)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = (size - 1) / 2.0
    cy = (size - 1) / 2.0

    theta = float(rng.uniform(-0.075, 0.075))
    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))
    x = xx - cx
    y = yy - cy
    u = cos_t * x + sin_t * y
    v = -sin_t * x + cos_t * y

    pitch = float(rng.uniform(max(18, size / 18.0), max(34, size / 5.0)))
    phase_u = float(rng.uniform(-pitch, pitch))
    phase_v = float(rng.uniform(-pitch, pitch))
    cells = (np.floor((u + phase_u) / pitch) + np.floor((v + phase_v) / pitch)).astype(np.int32)
    pattern = (cells & 1).astype(np.float32)

    dark = float(rng.uniform(8, 42))
    bright = float(rng.uniform(178, 245))
    if rng.random() < 0.5:
        dark, bright = 255.0 - bright, 255.0 - dark
    img = dark + pattern * (bright - dark)

    # Mild illumination and camera-like variation, kept in the clean GT so the
    # model sees realistic large-field contrast without losing the true corners.
    gx = float(rng.uniform(-0.12, 0.12))
    gy = float(rng.uniform(-0.12, 0.12))
    illum = 1.0 + gx * (xx / max(1, size - 1) - 0.5) + gy * (yy / max(1, size - 1) - 0.5)
    img *= illum

    if rng.random() < 0.45:
        # Add one partial large region so some samples resemble cropped
        # checkboard corners near an FOV boundary.
        x0 = int(rng.integers(0, max(1, size // 3)))
        y0 = int(rng.integers(0, max(1, size // 3)))
        x1 = int(rng.integers(max(x0 + 16, size // 2), size))
        y1 = int(rng.integers(max(y0 + 16, size // 2), size))
        value = float(rng.uniform(15, 70) if rng.random() < 0.5 else rng.uniform(185, 248))
        alpha = float(rng.uniform(0.08, 0.22))
        mask = np.zeros((size, size), dtype=np.float32)
        cv2.rectangle(mask, (x0, y0), (x1, y1), 1.0, -1)
        img = img * (1.0 - alpha * mask) + value * (alpha * mask)

    if rng.random() < 0.35:
        # Tiny scratches/dust-like marks test robustness without making the
        # checkboard itself a texture task.
        for _ in range(int(rng.integers(2, 7))):
            p0 = (int(rng.integers(0, size)), int(rng.integers(0, size)))
            p1 = (
                int(np.clip(p0[0] + rng.integers(-size // 8, size // 8 + 1), 0, size - 1)),
                int(np.clip(p0[1] + rng.integers(-size // 8, size // 8 + 1), 0, size - 1)),
            )
            cv2.line(img, p0, p1, float(rng.uniform(70, 170)), 1)

    return _clip_u8(img)


def estimate_corner_count(img: np.ndarray) -> int:
    """Small guard metric used by tests and reports to ensure corners exist."""
    gray = img
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.uint8, copy=False)
    corners = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=512,
        qualityLevel=0.01,
        minDistance=4,
        blockSize=5,
        useHarrisDetector=True,
        k=0.04,
    )
    return 0 if corners is None else int(len(corners))


def generate_clean_dataset(
    output_root: Path | str,
    *,
    count_per_stage: int = 500,
    size: int = 512,
    base_seed: int = 4648,
    force: bool = False,
) -> dict:
    out_root = Path(output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    stages = []
    for stage in CORNER_STAGES:
        stage_dir = out_root / stage
        if stage_dir.exists():
            if not force and any(stage_dir.iterdir()):
                raise FileExistsError(f"stage directory already exists and is non-empty: {stage_dir}")
            if force:
                _safe_remove_tree(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)
        corner_counts = []
        for idx in range(int(count_per_stage)):
            img = generate_checkboard_corner_image(index=idx, size=size, base_seed=base_seed)
            corner_counts.append(estimate_corner_count(img))
            out_path = stage_dir / f"{idx:04d}.bmp"
            ok = cv2.imwrite(str(out_path), img)
            if not ok:
                raise RuntimeError(f"failed to write image: {out_path}")
        stages.append(
            {
                "stage": stage,
                "stage_id": 48,
                "feature_family": CORNER_STAGE_FAMILIES[stage],
                "count": int(count_per_stage),
                "corner_count_min": int(min(corner_counts)),
                "corner_count_median": float(np.median(corner_counts)),
                "corner_count_max": int(max(corner_counts)),
                "description": "Dense checkerboard/right-angle corner scenes for Lab checkboard reconstruction.",
            }
        )
    manifest = {
        "generator": "r46_lab_checkboard_corner_v1",
        "output_root": str(out_root),
        "image_size": int(size),
        "base_seed": int(base_seed),
        "stages": stages,
        "psf_next_step": (
            "Run LabSystem_MOSR/Training_Data/PSF_Convolution.py with "
            "LAB_RUN_STAGE_IDS=48 before building train/validation packages."
        ),
    }
    (out_root / "r46_corner_clean_manifest.json").write_text(
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
        family = MICRO_STAGE_FAMILIES.get(stage) or CORNER_STAGE_FAMILIES.get(stage)
        rel_dir = Path("stage_40_boundary_mixed") / stage if role == "corner" else Path(stage)
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
    pairs.extend(
        _stage_pairs(
            root,
            CORNER_STAGES,
            role="corner",
            per_stage=profile.corner_per_stage,
            start_index=profile.corner_start_index,
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
        "corner_stages": list(CORNER_STAGES),
        "micro_stage_families": MICRO_STAGE_FAMILIES,
        "corner_stage_families": CORNER_STAGE_FAMILIES,
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def create_preview(
    image_root: Path | str,
    output_path: Path | str = DEFAULT_PREVIEW_PATH,
    *,
    max_images: int = 12,
    tile_size: int = 160,
) -> dict:
    stage_dir = Path(image_root).resolve() / CORNER_STAGES[0]
    paths = collect_images(stage_dir)[: int(max_images)]
    if not paths:
        raise FileNotFoundError(f"no preview images found under {stage_dir}")

    tiles = []
    corner_counts = []
    for path in paths:
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError(f"failed to read preview image: {path}")
        corner_counts.append(estimate_corner_count(img))
        tile = cv2.resize(img, (tile_size, tile_size), interpolation=cv2.INTER_AREA)
        tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
        cv2.putText(
            tile,
            path.stem,
            (6, tile_size - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)

    cols = min(4, len(tiles))
    rows = int(np.ceil(len(tiles) / cols))
    sheet = np.full((rows * tile_size, cols * tile_size, 3), 245, dtype=np.uint8)
    for idx, tile in enumerate(tiles):
        r = idx // cols
        c = idx % cols
        sheet[r * tile_size : (r + 1) * tile_size, c * tile_size : (c + 1) * tile_size] = tile

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(out), sheet)
    if not ok:
        raise RuntimeError(f"failed to write preview: {out}")
    return {
        "preview": str(out),
        "image_count": len(paths),
        "corner_count_min": int(min(corner_counts)),
        "corner_count_median": float(np.median(corner_counts)),
        "corner_count_max": int(max(corner_counts)),
    }


def _profiles_from_cli(profile_name: str) -> Iterable[Profile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate Lab R46 checkboard/corner data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-clean", help="Generate clean Lab checkboard/corner labels.")
    gen.add_argument("--output-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    gen.add_argument("--count-per-stage", type=int, default=500)
    gen.add_argument("--size", type=int, default=512)
    gen.add_argument("--base-seed", type=int, default=4648)
    gen.add_argument("--force", action="store_true")

    preview = sub.add_parser("preview", help="Create a contact-sheet preview for generated clean images.")
    preview.add_argument("--image-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    preview.add_argument("--output-path", type=Path, default=DEFAULT_PREVIEW_PATH)
    preview.add_argument("--max-images", type=int, default=12)

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

    if args.command == "preview":
        summary = create_preview(
            args.image_root,
            args.output_path,
            max_images=args.max_images,
        )
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
        summaries.append(summary)

    if args.command == "validate-splits":
        assert_disjoint_plans(*plans)
        summaries.append({"split_validation": "disjoint"})

    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
