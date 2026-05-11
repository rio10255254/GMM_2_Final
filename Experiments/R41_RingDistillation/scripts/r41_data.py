"""R41 ring-distillation data package builder.

R41 reuses the existing R39 shape and R40 microscopy synthetic pools. The
recipe is intentionally exact at the role level: 700 ring, 250 shape, 250
microscopy samples for the first recovery run.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
R40_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"
if str(R40_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R40_SCRIPT_DIR))

from r40_micro_data import (  # noqa: E402
    MICRO_STAGES,
    SHAPE_STAGES,
    DatasetPlan,
    Profile as R40Profile,
    _ring_pairs,
    _stage_pairs,
    assert_disjoint_plans,
    materialize_plan,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "Training_Data" / "r41_ring_distillation"


@dataclass(frozen=True)
class R41Profile:
    name: str
    include_ring: bool
    ring_limit: int | None
    shape_total: int
    shape_start_index: int
    micro_total: int
    micro_start_index: int
    description: str


PROFILES: dict[str, R41Profile | R40Profile] = {
    "r41_ring_recover_train": R41Profile(
        name="r41_ring_recover_train",
        include_ring=True,
        ring_limit=700,
        shape_total=250,
        shape_start_index=0,
        micro_total=250,
        micro_start_index=0,
        description=(
            "R41 recovery mix: stronger ring replay plus a smaller R39 shape and "
            "R40 microscopy replay set."
        ),
    ),
    "micro_val_unseen": R40Profile(
        name="micro_val_unseen",
        include_ring=False,
        ring_limit=None,
        shape_per_stage=0,
        shape_start_index=0,
        micro_per_stage=20,
        micro_start_index=80,
        description="Held-out unseen microscopy-feature validation set reused from R40.",
    ),
}


def _balanced_stage_pairs(
    repo_root: Path,
    stages: tuple[str, ...],
    *,
    role: str,
    total: int,
    start_index: int,
) -> list:
    if total <= 0:
        return []
    base = int(total) // len(stages)
    remainder = int(total) % len(stages)
    pairs = []
    for idx, stage in enumerate(stages):
        per_stage = base + (1 if idx < remainder else 0)
        pairs.extend(
            _stage_pairs(
                repo_root,
                (stage,),
                role=role,
                per_stage=per_stage,
                start_index=start_index,
            )
        )
    return pairs


def build_plan(repo_root: Path | str, profile: R41Profile | R40Profile) -> DatasetPlan:
    root = Path(repo_root).resolve()
    if isinstance(profile, R40Profile):
        from r40_micro_data import build_plan as build_r40_plan

        return build_r40_plan(root, profile)

    pairs = []
    if profile.include_ring:
        pairs.extend(_ring_pairs(root, profile.ring_limit))
    pairs.extend(
        _balanced_stage_pairs(
            root,
            SHAPE_STAGES,
            role="shape",
            total=profile.shape_total,
            start_index=profile.shape_start_index,
        )
    )
    pairs.extend(
        _balanced_stage_pairs(
            root,
            MICRO_STAGES,
            role="micro",
            total=profile.micro_total,
            start_index=profile.micro_start_index,
        )
    )
    if not pairs:
        raise ValueError(f"profile {profile.name} produced no image pairs")
    return DatasetPlan(profile=profile, repo_root=root, pairs=tuple(pairs))


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_data_package(
    profile_name: str,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    build_data: bool = False,
    force_data: bool = False,
    link_mode: str = "auto",
) -> tuple[Path, dict]:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown R41 data profile: {profile_name}")
    package_dir = Path(output_root).resolve() / profile_name
    plan = build_plan(REPO_ROOT, PROFILES[profile_name])
    if build_data:
        manifest = materialize_plan(plan, package_dir, force=force_data, link_mode=link_mode)
    else:
        manifest = _load_manifest(package_dir / "manifest.json")
    if manifest.get("profile") != profile_name:
        raise RuntimeError(f"manifest profile mismatch in {package_dir}")
    if int(manifest.get("total_pairs", -1)) != len(plan.pairs):
        raise RuntimeError(f"manifest pair count mismatch in {package_dir}")
    return package_dir, manifest


def _profiles_from_cli(profile_name: str):
    if profile_name == "all":
        return PROFILES.values()
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    return (PROFILES[profile_name],)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate R41 data packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_p = sub.add_parser("plan", help="Print the selected package plan.")
    plan_p.add_argument("--profile", default="r41_ring_recover_train", choices=sorted(PROFILES) + ["all"])

    build_p = sub.add_parser("build", help="Materialize selected R41 data packages.")
    build_p.add_argument("--profile", default="r41_ring_recover_train", choices=sorted(PROFILES) + ["all"])
    build_p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    build_p.add_argument("--force", action="store_true")
    build_p.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")

    check_p = sub.add_parser("validate-splits", help="Check train/validation split disjointness.")
    check_p.add_argument("--train-profile", default="r41_ring_recover_train", choices=sorted(PROFILES))
    check_p.add_argument("--val-profile", default="micro_val_unseen", choices=sorted(PROFILES))

    args = parser.parse_args(argv)
    if args.command == "plan":
        payload = []
        for profile in _profiles_from_cli(args.profile):
            p = build_plan(REPO_ROOT, profile)
            payload.append(
                {
                    "profile": profile.name,
                    "description": profile.description,
                    "total_pairs": len(p.pairs),
                    "count_by_role": p.count_by_role,
                    "count_by_stage": p.count_by_stage,
                }
            )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build":
        built = []
        for profile in _profiles_from_cli(args.profile):
            plan = build_plan(REPO_ROOT, profile)
            manifest = materialize_plan(
                plan,
                Path(args.output_root) / profile.name,
                force=bool(args.force),
                link_mode=args.link_mode,
            )
            built.append({"profile": profile.name, "output_dir": manifest["output_dir"], "total_pairs": manifest["total_pairs"]})
        print(json.dumps(built, indent=2, ensure_ascii=False))
        return 0

    if args.command == "validate-splits":
        train = build_plan(REPO_ROOT, PROFILES[args.train_profile])
        val = build_plan(REPO_ROOT, PROFILES[args.val_profile])
        assert_disjoint_plans(train, val)
        print(json.dumps({"status": "ok", "train": args.train_profile, "val": args.val_profile}, indent=2))
        return 0

    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
