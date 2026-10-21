"""對 R46 best_tradeoff checkpoint 跑 R39 shape_val_unseen + R40 micro_val_unseen 重建。

輸出 BMP 到 R46/results/shape_recon/r46/ 跟 R46/results/micro_recon/r46/,
layout 跟 a025 sweep 對齊(`reconstruct_progress_best_tradeoff_in_<stage>_<timestamp>/<profile>_<stage>_best_tradeoff.pth/<frame>.bmp`)。

跑完後再用 r46_capability_eval.py 算 per-pair metrics 跟現有 a025 capability eval csv 合併。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Model"))


R39_VAL_PROFILE = REPO_ROOT / "Training_Data/r39_shape_generalization/shape_val_unseen"
R40_VAL_PROFILE = REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/micro_val_unseen"

R46_EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
R46_SHAPE_RECON_ROOT = R46_EXPERIMENT_ROOT / "results" / "shape_recon" / "r46"
R46_MICRO_RECON_ROOT = R46_EXPERIMENT_ROOT / "results" / "micro_recon" / "r46"


def _sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def _resolve_stages(profile_dir: Path, requested: str = "all") -> list[str]:
    src_root = profile_dir / "src"
    if not src_root.is_dir():
        raise RuntimeError(f"profile src missing: {src_root}")
    available = sorted(p.name for p in src_root.iterdir() if p.is_dir())
    if requested == "all":
        return available
    wanted = [_sanitize(x) for x in requested.split(",") if x.strip()]
    missing = sorted(set(wanted) - set(available))
    if missing:
        raise ValueError(f"requested stages not in {profile_dir.name}: {missing}")
    return wanted


def _run_recon(
    *,
    weights: Path,
    input_dir: Path,
    gt_dir: Path,
    recon_root: Path,
    output_name: str,
    device: str,
) -> None:
    import GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest as infer

    infer.MANUAL_SELECT_MODE = None
    infer.MANUAL_WEIGHTS_PATH = None
    sys.argv = [
        "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py",
        "--weights", str(weights),
        "--input-dir", str(input_dir),
        "--gt-dir", str(gt_dir),
        "--recon-root", str(recon_root),
        "--output-name", output_name,
        "--device", device,
        "--select-mode", "all",
    ]
    infer.main()


def recon_one_profile(
    *,
    weights: Path,
    profile_dir: Path,
    recon_root: Path,
    output_name: str,
    stages: Iterable[str],
    device: str,
) -> list[Path]:
    src_root = profile_dir / "src"
    lbl_root = profile_dir / "lbl"
    output_paths: list[Path] = []
    for stage in stages:
        input_dir = src_root / stage
        gt_dir = lbl_root / stage
        if not input_dir.is_dir() or not gt_dir.is_dir():
            print(f"  [SKIP] {stage}: missing src or lbl directory")
            continue
        print(f"  [RUN] {stage}", flush=True)
        _run_recon(
            weights=weights,
            input_dir=input_dir,
            gt_dir=gt_dir,
            recon_root=recon_root,
            output_name=output_name,
            device=device,
        )
        output_paths.append(recon_root)
    return output_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R46 reconstruction wrapper")
    parser.add_argument("--weights", type=Path, required=True,
                        help="R46 best_tradeoff.pth.tar path")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--stages-r39", default="all",
                        help="逗號分隔 R39 stage list,預設 all")
    parser.add_argument("--stages-r40", default="all",
                        help="逗號分隔 R40 stage list,預設 all")
    parser.add_argument("--output-name", default="r46_a025_corner_finetune",
                        help="模型輸出標籤")
    parser.add_argument("--skip-r39", action="store_true")
    parser.add_argument("--skip-r40", action="store_true")
    args = parser.parse_args(argv)

    weights = args.weights.resolve()
    if not weights.exists():
        raise FileNotFoundError(f"R46 checkpoint not found: {weights}")

    print(f"[R46 recon] weights = {weights}", flush=True)
    print(f"[R46 recon] device = {args.device}", flush=True)

    if not args.skip_r39:
        r39_stages = _resolve_stages(R39_VAL_PROFILE, args.stages_r39)
        print(f"\n[R46 recon] R39 shape_val_unseen stages: {r39_stages}", flush=True)
        R46_SHAPE_RECON_ROOT.mkdir(parents=True, exist_ok=True)
        recon_one_profile(
            weights=weights,
            profile_dir=R39_VAL_PROFILE,
            recon_root=R46_SHAPE_RECON_ROOT,
            output_name=args.output_name,
            stages=r39_stages,
            device=args.device,
        )

    if not args.skip_r40:
        r40_stages = _resolve_stages(R40_VAL_PROFILE, args.stages_r40)
        print(f"\n[R46 recon] R40 micro_val_unseen stages: {r40_stages}", flush=True)
        R46_MICRO_RECON_ROOT.mkdir(parents=True, exist_ok=True)
        recon_one_profile(
            weights=weights,
            profile_dir=R40_VAL_PROFILE,
            recon_root=R46_MICRO_RECON_ROOT,
            output_name=args.output_name,
            stages=r40_stages,
            device=args.device,
        )

    print(f"\n[R46 recon] done.")
    print(f"  shape recon -> {R46_SHAPE_RECON_ROOT}")
    print(f"  micro recon -> {R46_MICRO_RECON_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
