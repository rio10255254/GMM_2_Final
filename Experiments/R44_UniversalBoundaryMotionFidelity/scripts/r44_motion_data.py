"""R44 universal boundary-motion data package builder."""
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
R42_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "scripts"
if str(R42_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R42_SCRIPT_DIR))

from r42_boundary_data import (  # noqa: E402
    BOUNDARY_STAGE_SPECS,
    BoundaryStageSpec,
    _boundary_from_label,
    _distance_from_boundary,
    _rng_for,
    _simulate_source,
    generate_boundary_image,
)


DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
DEFAULT_CLEAN_ROOT = REPO_ROOT / "Training_Data" / "generated"
DEFAULT_SOURCE_ROOT = REPO_ROOT / "Training_Data" / "generated_convolved"
DEFAULT_GEOM_ROOT = REPO_ROOT / "Training_Data" / "r44_motion_geometry"

MOTION_SHIFT_STEPS: tuple[float, ...] = (0.0, 0.08, 0.16, 0.4, 0.8, 2.0, 8.0)


@dataclass(frozen=True)
class MotionStageSpec:
    stage_id: int
    name: str
    feature_family: str
    description: str
    base_spec: BoundaryStageSpec


def _base_spec_by_family() -> dict[str, BoundaryStageSpec]:
    return {spec.feature_family: spec for spec in BOUNDARY_STAGE_SPECS}


_BASE = _base_spec_by_family()
MOTION_STAGE_SPECS: tuple[MotionStageSpec, ...] = (
    MotionStageSpec(41, "stage_41_motion_lines", "thin_lines", "Thin-line motion sequences.", _BASE["thin_lines"]),
    MotionStageSpec(42, "stage_42_motion_grids", "grids", "Grid phase and pitch motion sequences.", _BASE["grids"]),
    MotionStageSpec(43, "stage_43_motion_junctions", "junctions", "Crossing-line motion sequences.", _BASE["junctions"]),
    MotionStageSpec(44, "stage_44_motion_curves", "curves", "Curved-boundary motion sequences.", _BASE["curves"]),
    MotionStageSpec(45, "stage_45_motion_regions", "large_regions", "Large-region boundary motion sequences.", _BASE["large_regions"]),
    MotionStageSpec(46, "stage_46_motion_defects", "defects", "Small-defect motion sequences.", _BASE["defects"]),
    MotionStageSpec(47, "stage_47_motion_mixed", "mixed_fields", "Mixed microscopy motion sequences.", _BASE["mixed_fields"]),
)
MOTION_STAGES = tuple(spec.name for spec in MOTION_STAGE_SPECS)
MOTION_STAGE_FAMILIES = {spec.name: spec.feature_family for spec in MOTION_STAGE_SPECS}


@dataclass(frozen=True)
class GeometryPaths:
    boundary: Path
    centerline: Path
    distance: Path
    meta: Path


@dataclass(frozen=True)
class MotionFrame:
    src: Path
    lbl: Path
    stage: str
    rel_dir: Path
    feature_family: str
    sequence_id: int
    frame_index: int
    cumulative_dx: float
    cumulative_dy: float
    delta_dx: float
    delta_dy: float
    geometry: GeometryPaths

    @property
    def filename(self) -> str:
        return self.src.name


@dataclass(frozen=True)
class R44MotionProfile:
    name: str
    motion_per_stage: int
    motion_start_index: int
    description: str


@dataclass(frozen=True)
class MotionDatasetPlan:
    profile: R44MotionProfile
    repo_root: Path
    frames: tuple[MotionFrame, ...]

    @property
    def source_paths(self) -> tuple[Path, ...]:
        return tuple(frame.src for frame in self.frames)

    @property
    def count_by_stage(self) -> dict[str, int]:
        return dict(Counter(frame.stage for frame in self.frames))

    @property
    def count_by_family(self) -> dict[str, int]:
        return dict(Counter(frame.feature_family for frame in self.frames))


PROFILES: dict[str, R44MotionProfile] = {
    "r44_motion_research_train": R44MotionProfile(
        name="r44_motion_research_train",
        motion_per_stage=80,
        motion_start_index=0,
        description="R44B train motion package: all seven microscopy feature families with known subpixel-to-large shifts.",
    ),
    "motion_val_unseen": R44MotionProfile(
        name="motion_val_unseen",
        motion_per_stage=20,
        motion_start_index=80,
        description="R44A/R44B held-out motion validation package.",
    ),
}


def _safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
    shutil.rmtree(resolved)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _clip_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def _warp_image(img: np.ndarray, *, dx: float, dy: float, interp: int) -> np.ndarray:
    h, w = img.shape[:2]
    mat = np.asarray([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
    return cv2.warpAffine(
        img,
        mat,
        (w, h),
        flags=interp,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _frame_stem(index: int, frame_index: int) -> str:
    return f"{index:04d}_seq{index:04d}_f{frame_index:02d}"


def _frame_meta(
    spec: MotionStageSpec,
    *,
    index: int,
    frame_index: int,
    cumulative_dx: float,
    cumulative_dy: float,
    prev_dx: float,
    prev_dy: float,
    base_meta: dict,
) -> dict:
    return {
        "stage": spec.name,
        "feature_family": spec.feature_family,
        "sequence_id": int(index),
        "frame_index": int(frame_index),
        "cumulative_shift_px": {"dx": float(cumulative_dx), "dy": float(cumulative_dy)},
        "delta_from_prev_px": {
            "dx": float(round(cumulative_dx - prev_dx, 6)),
            "dy": float(round(cumulative_dy - prev_dy, 6)),
        },
        "base_stage": spec.base_spec.name,
        "base_meta": base_meta,
    }


def generate_motion_sequence(
    spec: MotionStageSpec,
    *,
    index: int,
    size: int = 512,
    base_seed: int = 4400,
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]]:
    rng = _rng_for(spec.base_spec, index=index, base_seed=base_seed)
    _source0, base_label, _boundary0, base_centerline, _distance0, base_meta = generate_boundary_image(
        spec.base_spec,
        index=index,
        size=size,
        base_seed=base_seed,
    )
    frames = []
    prev_dx = 0.0
    prev_dy = 0.0
    for frame_index, cumulative_dx in enumerate(MOTION_SHIFT_STEPS):
        cumulative_dy = 0.0
        label = _clip_u8(_warp_image(base_label, dx=cumulative_dx, dy=cumulative_dy, interp=cv2.INTER_LINEAR))
        centerline = _clip_u8(_warp_image(base_centerline, dx=cumulative_dx, dy=cumulative_dy, interp=cv2.INTER_LINEAR))
        boundary = _boundary_from_label(label)
        distance = _distance_from_boundary(boundary)
        frame_rng = np.random.default_rng(int(rng.integers(0, 2**31 - 1)) + frame_index * 9973)
        source = _simulate_source(label, frame_rng)
        meta = _frame_meta(
            spec,
            index=index,
            frame_index=frame_index,
            cumulative_dx=float(cumulative_dx),
            cumulative_dy=float(cumulative_dy),
            prev_dx=float(prev_dx),
            prev_dy=float(prev_dy),
            base_meta=base_meta,
        )
        frames.append((source, label, boundary, centerline, distance, meta))
        prev_dx = float(cumulative_dx)
        prev_dy = float(cumulative_dy)
    return frames


def generate_motion_dataset(
    *,
    clean_root: Path | str = DEFAULT_CLEAN_ROOT,
    source_root: Path | str = DEFAULT_SOURCE_ROOT,
    geom_root: Path | str = DEFAULT_GEOM_ROOT,
    count_per_stage: int = 100,
    size: int = 512,
    base_seed: int = 4400,
    force: bool = False,
) -> dict:
    clean_root = Path(clean_root).resolve()
    source_root = Path(source_root).resolve()
    geom_root = Path(geom_root).resolve()
    for root in (clean_root, source_root, geom_root):
        root.mkdir(parents=True, exist_ok=True)

    stages = []
    for spec in MOTION_STAGE_SPECS:
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
            for frame_index, (source, label, boundary, centerline, distance, meta) in enumerate(
                generate_motion_sequence(spec, index=idx, size=size, base_seed=base_seed)
            ):
                stem = _frame_stem(idx, frame_index)
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
                "count_sequences": int(count_per_stage),
                "frames_per_sequence": len(MOTION_SHIFT_STEPS),
                "description": spec.description,
            }
        )

    manifest = {
        "generator": "r44_motion_v1",
        "clean_root": str(clean_root),
        "source_root": str(source_root),
        "geom_root": str(geom_root),
        "image_size": int(size),
        "base_seed": int(base_seed),
        "motion_shift_steps_px": list(MOTION_SHIFT_STEPS),
        "stages": stages,
    }
    (geom_root / "r44_motion_geometry_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def collect_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _frame_from_path(repo_root: Path, spec: MotionStageSpec, src: Path) -> MotionFrame:
    clean_root = repo_root / "Training_Data" / "generated"
    geom_root = repo_root / "Training_Data" / "r44_motion_geometry"
    stage = spec.name
    stem = src.with_suffix("").name
    meta_path = geom_root / "meta" / stage / f"{stem}.json"
    meta = _load_json(meta_path)
    geom = GeometryPaths(
        boundary=geom_root / "boundary" / stage / src.name,
        centerline=geom_root / "centerline" / stage / src.name,
        distance=geom_root / "distance" / stage / f"{stem}.npy",
        meta=meta_path,
    )
    lbl = clean_root / stage / src.name
    missing = [p for p in (lbl, geom.boundary, geom.centerline, geom.distance, geom.meta) if not p.exists()]
    if missing:
        raise ValueError(f"{stage}/{src.name} has missing label or geometry sidecars: {missing}")
    delta = meta["delta_from_prev_px"]
    cumulative = meta["cumulative_shift_px"]
    return MotionFrame(
        src=src,
        lbl=lbl,
        stage=stage,
        rel_dir=Path(stage),
        feature_family=spec.feature_family,
        sequence_id=int(meta["sequence_id"]),
        frame_index=int(meta["frame_index"]),
        cumulative_dx=float(cumulative["dx"]),
        cumulative_dy=float(cumulative["dy"]),
        delta_dx=float(delta["dx"]),
        delta_dy=float(delta["dy"]),
        geometry=geom,
    )


def build_motion_plan(repo_root: Path | str, profile: R44MotionProfile) -> MotionDatasetPlan:
    root = Path(repo_root).resolve()
    source_root = root / "Training_Data" / "generated_convolved"
    frames: list[MotionFrame] = []
    for spec in MOTION_STAGE_SPECS:
        src_files = collect_images(source_root / spec.name)
        sequence_ids = sorted({int(p.name.split("_seq", 1)[1].split("_f", 1)[0]) for p in src_files})
        start = int(profile.motion_start_index)
        end = start + int(profile.motion_per_stage)
        selected = set(sequence_ids[start:end])
        if len(selected) < int(profile.motion_per_stage):
            raise ValueError(f"{spec.name} has only {len(sequence_ids)} sequences; requires index range [{start}, {end}).")
        for src in src_files:
            seq_id = int(src.name.split("_seq", 1)[1].split("_f", 1)[0])
            if seq_id in selected:
                frames.append(_frame_from_path(root, spec, src))
    if not frames:
        raise ValueError(f"profile {profile.name} produced no motion frames")
    return MotionDatasetPlan(profile=profile, repo_root=root, frames=tuple(frames))


def assert_disjoint_motion_plans(*plans: MotionDatasetPlan) -> None:
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


def materialize_motion_plan(
    plan: MotionDatasetPlan,
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
    for frame in plan.frames:
        rel_path = frame.rel_dir / frame.filename
        src_rel = Path("src") / rel_path
        lbl_rel = Path("lbl") / rel_path
        boundary_rel = Path("geom") / "boundary" / rel_path
        center_rel = Path("geom") / "centerline" / rel_path
        dist_rel = Path("geom") / "distance" / rel_path.with_suffix(".npy")
        meta_rel = Path("geom") / "meta" / rel_path.with_suffix(".json")

        link_counts[_place_file(frame.src, out / src_rel, link_mode)] += 1
        link_counts[_place_file(frame.lbl, out / lbl_rel, link_mode)] += 1
        link_counts[_place_file(frame.geometry.boundary, out / boundary_rel, link_mode)] += 1
        link_counts[_place_file(frame.geometry.centerline, out / center_rel, link_mode)] += 1
        link_counts[_place_file(frame.geometry.distance, out / dist_rel, link_mode)] += 1
        link_counts[_place_file(frame.geometry.meta, out / meta_rel, link_mode)] += 1
        records.append(
            {
                "stage": frame.stage,
                "feature_family": frame.feature_family,
                "sequence_id": frame.sequence_id,
                "frame_index": frame.frame_index,
                "cumulative_shift_px": {"dx": frame.cumulative_dx, "dy": frame.cumulative_dy},
                "delta_from_prev_px": {"dx": frame.delta_dx, "dy": frame.delta_dy},
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "package_boundary": boundary_rel.as_posix(),
                "package_centerline": center_rel.as_posix(),
                "package_distance": dist_rel.as_posix(),
                "package_meta": meta_rel.as_posix(),
            }
        )

    manifest = {
        "profile": plan.profile.name,
        "description": plan.profile.description,
        "repo_root": str(plan.repo_root),
        "output_dir": str(out),
        "motion_shift_steps_px": list(MOTION_SHIFT_STEPS),
        "total_frames": len(plan.frames),
        "count_by_stage": plan.count_by_stage,
        "count_by_family": plan.count_by_family,
        "link_counts": dict(link_counts),
        "motion_stages": list(MOTION_STAGES),
        "motion_stage_families": MOTION_STAGE_FAMILIES,
        "frames": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _profiles_from_cli(profile_name: str) -> Iterable[R44MotionProfile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def ensure_motion_package(
    profile_name: str,
    output_root: Path = DEFAULT_DATA_ROOT,
    *,
    build_data: bool = False,
    force_data: bool = False,
    link_mode: str = "auto",
) -> tuple[Path, dict]:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown R44 profile: {profile_name}")
    package_dir = Path(output_root).resolve() / profile_name
    plan = build_motion_plan(REPO_ROOT, PROFILES[profile_name])
    if build_data:
        manifest = materialize_motion_plan(plan, package_dir, force=force_data, link_mode=link_mode)
    else:
        manifest = _load_json(package_dir / "manifest.json")
    if manifest.get("profile") != profile_name:
        raise RuntimeError(f"manifest profile mismatch in {package_dir}")
    if int(manifest.get("total_frames", -1)) != len(plan.frames):
        raise RuntimeError(f"manifest frame count mismatch in {package_dir}")
    return package_dir, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate R44 boundary-motion data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate R44 clean/source/geometry motion pools.")
    gen.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    gen.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    gen.add_argument("--geom-root", type=Path, default=DEFAULT_GEOM_ROOT)
    gen.add_argument("--count-per-stage", type=int, default=100)
    gen.add_argument("--size", type=int, default=512)
    gen.add_argument("--base-seed", type=int, default=4400)
    gen.add_argument("--force", action="store_true")

    for cmd in ("plan", "build"):
        p = sub.add_parser(cmd)
        p.add_argument("--profile", default="all", choices=[*PROFILES.keys(), "all"])
        p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
        p.add_argument("--output-root", type=Path, default=DEFAULT_DATA_ROOT)
        p.add_argument("--force", action="store_true")
        p.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")

    check = sub.add_parser("validate-splits")
    check.add_argument("--train-profile", default="r44_motion_research_train", choices=sorted(PROFILES))
    check.add_argument("--val-profile", default="motion_val_unseen", choices=sorted(PROFILES))
    check.add_argument("--repo-root", type=Path, default=REPO_ROOT)

    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest = generate_motion_dataset(
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
        train = build_motion_plan(args.repo_root, PROFILES[args.train_profile])
        val = build_motion_plan(args.repo_root, PROFILES[args.val_profile])
        assert_disjoint_motion_plans(train, val)
        print(json.dumps({"status": "ok", "train": args.train_profile, "val": args.val_profile}, indent=2, ensure_ascii=False))
        return 0

    summaries = []
    for profile in _profiles_from_cli(args.profile):
        plan = build_motion_plan(args.repo_root, profile)
        summary = {
            "profile": profile.name,
            "total_frames": len(plan.frames),
            "count_by_stage": plan.count_by_stage,
            "count_by_family": plan.count_by_family,
        }
        if args.command == "build":
            manifest = materialize_motion_plan(plan, args.output_root / profile.name, force=args.force, link_mode=args.link_mode)
            summary["output_dir"] = manifest["output_dir"]
            summary["link_counts"] = manifest["link_counts"]
        summaries.append(summary)
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
