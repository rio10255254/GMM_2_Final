"""R52 Lab corner-stability training package builder.

R52 keeps the R51 mixed-PSF checkboard-corner core and adds R48 real-corner
stability sources plus geometry sidecars for every packaged pair.
"""
from __future__ import annotations

import argparse
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
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r52_corner_stability_guard"
DEFAULT_LABEL_ROOT = REPO_ROOT / "Training_Data" / "generated"
DEFAULT_FORMAL_BADS_ROOT = REPO_ROOT / "Training_Data" / "generated_convolved"
DEFAULT_GAUSSIAN_ROOT = REPO_ROOT / "Training_Data" / "generated_convolved_gaussian_control"
DEFAULT_WEAK_BADS_ROOT = (
    REPO_ROOT
    / "Experiments"
    / "R50_PSFControlDiagnosis"
    / "results"
    / "psf_control_diagnosis"
    / "generated_controls"
    / "weak_bads_alpha050"
)

R48_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R48_RealCornerTransfer" / "scripts"
sys.path.insert(0, str(R48_SCRIPT_DIR))
from r48_real_corner_data import compute_geometry_from_label  # noqa: E402


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

CORNER_STAGE = "stage_48_checkboard_corners"
CORNER_STAGE_FAMILY = "checkboard_corners"
STAGE_53_REAL_CORNER = "stage_53_real_corner_anchor"
STAGE_54_LATTICE_INTERSECTIONS = "stage_54_lattice_intersection_anchor"
STAGE_55_REAL_TEXTURE = "stage_55_real_texture_corner"
STAGE_56_CORNER_PSF_STRESS = "stage_56_corner_psf_stress"

NEW_STAGE_FAMILIES = {
    STAGE_53_REAL_CORNER: "real_corner_anchor",
    STAGE_54_LATTICE_INTERSECTIONS: "lattice_intersection_anchor",
    STAGE_55_REAL_TEXTURE: "real_texture_corner",
    STAGE_56_CORNER_PSF_STRESS: "corner_psf_stress",
}

TRAIN_COMMON = {
    "include_ring": True,
    "ring_limit": 550,
    "shape_per_stage": 50,
    "shape_start_index": 0,
    "micro_per_stage": 50,
    "micro_start_index": 0,
    "corner_per_stage": 400,
    "corner_start_index": 0,
}

VAL_COMMON = {
    "include_ring": False,
    "ring_limit": None,
    "shape_per_stage": 0,
    "shape_start_index": 0,
    "micro_per_stage": 0,
    "micro_start_index": 0,
    "corner_per_stage": 100,
    "corner_start_index": 400,
}

TRAIN_BOUNDARY_QUOTAS = {
    STAGE_53_REAL_CORNER: 950,
    STAGE_54_LATTICE_INTERSECTIONS: 550,
    STAGE_56_CORNER_PSF_STRESS: 300,
}
TRAIN_REAL_BG_QUOTAS = {STAGE_55_REAL_TEXTURE: 650}
VAL_BOUNDARY_QUOTAS = {
    STAGE_53_REAL_CORNER: 200,
    STAGE_54_LATTICE_INTERSECTIONS: 150,
    STAGE_56_CORNER_PSF_STRESS: 100,
}
VAL_REAL_BG_QUOTAS = {STAGE_55_REAL_TEXTURE: 150}
VAL_OFFSETS = {
    STAGE_53_REAL_CORNER: TRAIN_BOUNDARY_QUOTAS[STAGE_53_REAL_CORNER],
    STAGE_54_LATTICE_INTERSECTIONS: TRAIN_BOUNDARY_QUOTAS[STAGE_54_LATTICE_INTERSECTIONS],
    STAGE_56_CORNER_PSF_STRESS: TRAIN_BOUNDARY_QUOTAS[STAGE_56_CORNER_PSF_STRESS],
    STAGE_55_REAL_TEXTURE: TRAIN_REAL_BG_QUOTAS[STAGE_55_REAL_TEXTURE],
}


@dataclass(frozen=True)
class Profile:
    name: str
    corner_source_mode: str
    include_ring: bool
    ring_limit: int | None
    shape_per_stage: int
    shape_start_index: int
    micro_per_stage: int
    micro_start_index: int
    corner_per_stage: int
    corner_start_index: int
    boundary_quotas: dict[str, int] = field(default_factory=dict)
    real_bg_quotas: dict[str, int] = field(default_factory=dict)
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
    corner_source: str | None = None

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

    @property
    def count_by_corner_source(self) -> dict[str, int]:
        return dict(Counter(pair.corner_source for pair in self.pairs if pair.corner_source))


PROFILES: dict[str, Profile] = {
    "r52_corner_stability_train_4000": Profile(
        name="r52_corner_stability_train_4000",
        corner_source_mode="mixed_psf",
        boundary_quotas=TRAIN_BOUNDARY_QUOTAS,
        real_bg_quotas=TRAIN_REAL_BG_QUOTAS,
        description=(
            "R52 formal train package: R51 mixed-PSF 1550-pair core plus "
            "2450 R48 real-corner stability pairs with geometry sidecars."
        ),
        **TRAIN_COMMON,
    ),
    "r52_corner_stability_val": Profile(
        name="r52_corner_stability_val",
        corner_source_mode="mixed_psf",
        boundary_quotas=VAL_BOUNDARY_QUOTAS,
        real_bg_quotas=VAL_REAL_BG_QUOTAS,
        start_offsets=VAL_OFFSETS,
        description="Held-out R52 mixed-PSF and real-corner stability validation package.",
        **VAL_COMMON,
    ),
}


def collect_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _label_root(repo_root: Path) -> Path:
    return repo_root / "Training_Data" / "generated"


def _formal_bads_root(repo_root: Path) -> Path:
    return repo_root / "Training_Data" / "generated_convolved"


def _gaussian_root(repo_root: Path) -> Path:
    return repo_root / "Training_Data" / "generated_convolved_gaussian_control"


def _weak_bads_root(repo_root: Path) -> Path:
    return (
        repo_root
        / "Experiments"
        / "R50_PSFControlDiagnosis"
        / "results"
        / "psf_control_diagnosis"
        / "generated_controls"
        / "weak_bads_alpha050"
    )


def _corner_root_by_source(repo_root: Path, source: str) -> Path:
    if source == "formal_bads":
        return _formal_bads_root(repo_root)
    if source == "gaussian":
        return _gaussian_root(repo_root)
    if source == "weak_bads_alpha050":
        return _weak_bads_root(repo_root)
    raise ValueError(f"unsupported corner source: {source}")


def _mixed_corner_source(local_index: int) -> str:
    rem = int(local_index) % 3
    if rem == 0:
        return "formal_bads"
    if rem == 1:
        return "gaussian"
    return "weak_bads_alpha050"


def _corner_source_for(profile: Profile, local_index: int) -> str:
    if profile.corner_source_mode == "mixed_psf":
        return _mixed_corner_source(local_index)
    return profile.corner_source_mode


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
    return [Pair(src=p, lbl=lbl_dir / p.name, role="ring", stage="ring", rel_dir=Path("ring")) for p in src_files]


def _require_complete_stage_pairs(repo_root: Path, stage: str, src_root: Path) -> list[Path]:
    src_dir = src_root / stage
    lbl_dir = _label_root(repo_root) / stage
    src_files = collect_images(src_dir)
    missing = [p for p in src_files if not (lbl_dir / p.name).exists()]
    if missing:
        examples = ", ".join(p.name for p in missing[:5])
        raise ValueError(f"{stage} has missing labels: {examples}")
    return src_files


def _stage_pairs(
    repo_root: Path,
    stages: Iterable[str],
    *,
    role: str,
    per_stage: int,
    start_index: int,
) -> list[Pair]:
    if per_stage <= 0:
        return []
    pairs: list[Pair] = []
    for stage in stages:
        src_files = _require_complete_stage_pairs(repo_root, stage, _formal_bads_root(repo_root))
        start = int(start_index)
        end = start + int(per_stage)
        if len(src_files) < end:
            raise ValueError(f"{stage} has only {len(src_files)} images; requires index range [{start}, {end}).")
        lbl_dir = _label_root(repo_root) / stage
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


def _corner_pairs(repo_root: Path, profile: Profile) -> list[Pair]:
    lbl_dir = _label_root(repo_root) / CORNER_STAGE
    start = int(profile.corner_start_index)
    end = start + int(profile.corner_per_stage)
    label_files = collect_images(lbl_dir)
    if len(label_files) < end:
        raise ValueError(f"{CORNER_STAGE} labels have only {len(label_files)} images; requires index range [{start}, {end}).")

    pairs: list[Pair] = []
    for local_index, lbl in enumerate(label_files[start:end]):
        corner_source = _corner_source_for(profile, local_index)
        src = _corner_root_by_source(repo_root, corner_source) / CORNER_STAGE / lbl.name
        if not src.exists():
            raise ValueError(f"missing corner source for {corner_source}: {src}")
        pairs.append(
            Pair(
                src=src,
                lbl=lbl,
                role="corner",
                stage=CORNER_STAGE,
                rel_dir=Path("stage_40_boundary_mixed") / CORNER_STAGE,
                feature_family=CORNER_STAGE_FAMILY,
                corner_source=corner_source,
            )
        )
    return pairs


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
        src_files = _require_complete_stage_pairs(repo_root, stage, _formal_bads_root(repo_root))
        start = int(start_offsets.get(stage, 0))
        end = start + int(quota)
        if len(src_files) < end:
            raise ValueError(f"{stage} has only {len(src_files)} images; requires index range [{start}, {end}).")
        lbl_dir = _label_root(repo_root) / stage
        rel_dir = Path("stage_40_boundary_mixed") / stage
        for src in src_files[start:end]:
            pairs.append(
                Pair(
                    src=src,
                    lbl=lbl_dir / src.name,
                    role=role,
                    stage=stage,
                    rel_dir=rel_dir,
                    feature_family=NEW_STAGE_FAMILIES.get(stage),
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
    pairs.extend(_corner_pairs(root, profile))
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
                raise ValueError(f"data split overlap: {resolved} appears in both {seen[resolved]} and {plan.profile.name}")
            seen[resolved] = plan.profile.name


def _safe_remove_tree(path: Path, root: Path | None = None) -> None:
    resolved = path.resolve()
    if root is not None:
        root_resolved = root.resolve()
        if not str(resolved).lower().startswith(str(root_resolved).lower()):
            raise ValueError(f"refusing to remove outside root: {resolved}")
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
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


def _write_geometry_sidecars(lbl_path: Path, geom_dir: Path, rel_path: Path) -> None:
    img = _read_gray_image(lbl_path)
    boundary, centerline, distance = compute_geometry_from_label(img)
    boundary_path = geom_dir / "boundary" / rel_path
    centerline_path = geom_dir / "centerline" / rel_path
    distance_path = geom_dir / "distance" / rel_path.with_suffix(".npy")
    _write_image(boundary_path, boundary)
    _write_image(centerline_path, centerline)
    distance_path.parent.mkdir(parents=True, exist_ok=True)
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
        remove_root = DEFAULT_OUTPUT_ROOT if str(out).lower().startswith(str(DEFAULT_OUTPUT_ROOT.resolve()).lower()) else out.parent
        _safe_remove_tree(out, root=remove_root)
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
                "corner_source": pair.corner_source,
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
        "count_by_corner_source": plan.count_by_corner_source,
        "link_counts": dict(link_counts),
        "geometry_sidecars": True,
        "geom_dir": str(geom_dir),
        "geometry_count": int(geometry_count),
        "shape_stages": list(SHAPE_STAGES),
        "micro_stages": list(MICRO_STAGES),
        "corner_stage": CORNER_STAGE,
        "new_stage_families": NEW_STAGE_FAMILIES,
        "source_roots": {
            "formal_bads": str(_formal_bads_root(plan.repo_root)),
            "gaussian": str(_gaussian_root(plan.repo_root)),
            "weak_bads_alpha050": str(_weak_bads_root(plan.repo_root)),
            "labels": str(_label_root(plan.repo_root)),
        },
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _print_plan(plan: DatasetPlan) -> None:
    print(
        json.dumps(
            {
                "profile": plan.profile.name,
                "description": plan.profile.description,
                "total_pairs": len(plan.pairs),
                "count_by_role": plan.count_by_role,
                "count_by_stage": plan.count_by_stage,
                "count_by_corner_source": plan.count_by_corner_source,
                "geometry_sidecars": True,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate Lab R52 corner-stability packages.")
    parser.add_argument("command", choices=["plan", "build", "validate-splits"])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="r52_corner_stability_train_4000")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    args = parser.parse_args(argv)

    profile = PROFILES[args.profile]
    plan = build_plan(args.repo_root, profile)

    if args.command == "plan":
        _print_plan(plan)
        return 0

    if args.command == "build":
        out_dir = args.output_root / args.profile
        manifest = materialize_plan(plan, out_dir, force=args.force, link_mode=args.link_mode)
        print(
            json.dumps(
                {
                    "profile": manifest["profile"],
                    "total_pairs": manifest["total_pairs"],
                    "count_by_role": manifest["count_by_role"],
                    "count_by_corner_source": manifest["count_by_corner_source"],
                    "geometry_count": manifest["geometry_count"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "validate-splits":
        train = build_plan(args.repo_root, PROFILES["r52_corner_stability_train_4000"])
        val = build_plan(args.repo_root, PROFILES["r52_corner_stability_val"])
        assert_disjoint_plans(train, val)
        manifests = {}
        for profile_name in ("r52_corner_stability_train_4000", "r52_corner_stability_val"):
            manifest_path = args.output_root / profile_name / "manifest.json"
            if manifest_path.exists():
                manifests[profile_name] = _load_manifest(manifest_path)
        print(
            json.dumps(
                {
                    "status": "splits_valid",
                    "training_profile": train.profile.name,
                    "validation_profile": val.profile.name,
                    "loaded_manifests": sorted(manifests),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
