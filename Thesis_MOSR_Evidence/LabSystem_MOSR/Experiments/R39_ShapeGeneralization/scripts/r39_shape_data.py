"""R39 shape-generalization data package builder.

The generated image payloads live under Training_Data/ and stay out of Git.
This script only defines deterministic selection, pairing, and validation.
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


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r39_shape_generalization"

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
class Profile:
    name: str
    include_ring: bool
    shape_train_per_stage: int
    shape_start_index: int
    description: str


@dataclass(frozen=True)
class Pair:
    src: Path
    lbl: Path
    role: str
    stage: str
    rel_dir: Path

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
    "r39_shape_mix_safe": Profile(
        name="r39_shape_mix_safe",
        include_ring=True,
        shape_train_per_stage=20,
        shape_start_index=0,
        description="Conservative mix: existing ring data plus 20 images per shape stage.",
    ),
    "r39_shape_mix_strong": Profile(
        name="r39_shape_mix_strong",
        include_ring=True,
        shape_train_per_stage=70,
        shape_start_index=0,
        description="Stronger mix: existing ring data plus 70 images per shape stage.",
    ),
    "shape_val_unseen": Profile(
        name="shape_val_unseen",
        include_ring=False,
        shape_train_per_stage=30,
        shape_start_index=70,
        description="Unseen multi-shape validation set: final 30 images per shape stage.",
    ),
}


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


def _ring_pairs(repo_root: Path) -> list[Pair]:
    src_dir = repo_root / "Training_Data" / "tra_src_ring"
    lbl_dir = repo_root / "Training_Data" / "tra_lbl_ring"
    src_files = collect_images(src_dir)
    missing = [p for p in src_files if not (lbl_dir / p.name).exists()]
    if missing:
        examples = ", ".join(p.name for p in missing[:5])
        raise ValueError(f"ring data has missing labels: {examples}")
    return [
        Pair(src=p, lbl=lbl_dir / p.name, role="ring", stage="ring", rel_dir=Path("ring"))
        for p in src_files
    ]


def build_plan(repo_root: Path | str, profile: Profile) -> DatasetPlan:
    root = Path(repo_root).resolve()
    pairs: list[Pair] = []
    if profile.include_ring:
        pairs.extend(_ring_pairs(root))

    for stage in SHAPE_STAGES:
        src_files = _require_complete_stage_pairs(root, stage)
        start = int(profile.shape_start_index)
        end = start + int(profile.shape_train_per_stage)
        if len(src_files) < end:
            raise ValueError(
                f"{stage} has only {len(src_files)} images; "
                f"profile {profile.name} requires index range [{start}, {end})."
            )
        lbl_dir = root / "Training_Data" / "generated" / stage
        for src in src_files[start:end]:
            pairs.append(
                Pair(
                    src=src,
                    lbl=lbl_dir / src.name,
                    role="shape",
                    stage=stage,
                    rel_dir=Path(stage),
                )
            )

    if not pairs:
        raise ValueError(f"profile {profile.name} produced no image pairs")
    return DatasetPlan(profile=profile, repo_root=root, pairs=tuple(pairs))


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
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _profiles_from_cli(profile_name: str) -> Iterable[Profile]:
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate R39 shape-generalization data packages.")
    parser.add_argument("command", choices=["plan", "build"])
    parser.add_argument("--profile", default="all", choices=[*PROFILES.keys(), "all"])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--link-mode", default="auto", choices=["auto", "hardlink", "copy"])
    args = parser.parse_args(argv)

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
            output_dir = args.output_root / profile.name
            manifest = materialize_plan(plan, output_dir, force=args.force, link_mode=args.link_mode)
            summary["output_dir"] = manifest["output_dir"]
            summary["link_counts"] = manifest["link_counts"]
        summaries.append(summary)

    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
