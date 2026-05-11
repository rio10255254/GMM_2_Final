"""Run R41 microscopy-feature reconstruction checks stage by stage."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from launch_r41 import COMBO_CHECKPOINT, R39_A030_CHECKPOINT, R40_A045_CHECKPOINT, R40_ENDPOINT_CHECKPOINT
from r41_data import DEFAULT_OUTPUT_ROOT, PROFILES


DEFAULT_RECON_ROOT = _REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "micro_recon"


def _sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def _load_manifest(profile_dir: Path) -> dict:
    manifest_path = profile_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing data package manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _stage_names(profile_dir: Path, requested: str) -> list[str]:
    src_root = profile_dir / "src"
    lbl_root = profile_dir / "lbl"
    if not src_root.is_dir() or not lbl_root.is_dir():
        raise RuntimeError(f"data package is incomplete: {profile_dir}")
    available = sorted(p.name for p in src_root.iterdir() if p.is_dir())
    if requested == "all":
        return available
    wanted = [_sanitize(x) for x in requested.split(",") if x.strip()]
    missing = sorted(set(wanted) - set(available))
    if missing:
        raise ValueError(f"requested stages are not in package: {missing}")
    return wanted


def _run_stage(
    *,
    weights: Path,
    input_dir: Path,
    gt_dir: Path,
    recon_root: Path,
    output_name: str,
    device: str,
) -> None:
    model_dir = _REPO_ROOT / "Model"
    sys.path.insert(0, str(model_dir))
    import GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest as infer

    infer.MANUAL_SELECT_MODE = None
    infer.MANUAL_WEIGHTS_PATH = None
    sys.argv = [
        "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py",
        "--weights",
        str(weights),
        "--input-dir",
        str(input_dir),
        "--gt-dir",
        str(gt_dir),
        "--recon-root",
        str(recon_root),
        "--output-name",
        output_name,
        "--device",
        device,
        "--select-mode",
        "all",
    ]
    infer.main()


def _default_weights(alias: str) -> Path:
    if alias == "combo":
        return COMBO_CHECKPOINT
    if alias == "a030":
        return R39_A030_CHECKPOINT
    if alias == "r40_endpoint":
        return R40_ENDPOINT_CHECKPOINT
    if alias == "r40_a045":
        return R40_A045_CHECKPOINT
    return Path(alias)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R41 microscopy-feature validation reconstructions.")
    parser.add_argument("--profile", default="micro_val_unseen", choices=sorted(PROFILES))
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--weights", default="combo", help="'combo', 'a030', or a checkpoint path")
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--stages", default="all", help="all or comma-separated stage folder names")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    profile_dir = args.data_root / args.profile
    manifest = _load_manifest(profile_dir)
    weights = _default_weights(args.weights).resolve()
    if not weights.exists():
        raise FileNotFoundError(f"weights not found: {weights}")

    stages = _stage_names(profile_dir, args.stages)
    jobs = []
    for stage in stages:
        input_dir = profile_dir / "src" / stage
        gt_dir = profile_dir / "lbl" / stage
        output_name = _sanitize(f"{args.profile}_{stage}_{weights.stem}")
        jobs.append(
            {
                "stage": stage,
                "input_dir": str(input_dir),
                "gt_dir": str(gt_dir),
                "recon_root": str(args.recon_root),
                "output_name": output_name,
                "image_pairs": manifest["count_by_stage"].get(stage, 0),
            }
        )

    print(json.dumps({"profile": args.profile, "weights": str(weights), "jobs": jobs}, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("[R41] dry run complete; reconstruction was not started.")
        return 0

    for job in jobs:
        _run_stage(
            weights=weights,
            input_dir=Path(job["input_dir"]),
            gt_dir=Path(job["gt_dir"]),
            recon_root=args.recon_root,
            output_name=job["output_name"],
            device=args.device,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
